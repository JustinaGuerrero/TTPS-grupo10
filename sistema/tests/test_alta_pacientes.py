"""Alta de pacientes, familiares y familiograma (E06, E09)."""

import io

import sqlalchemy as sa
from conftest import codigo_de_verificacion

from src.core.auditoria import Entidad, RegistroDeCambio
from src.core.database import db
from src.core.pacientes import Familiar, Paciente
from src.core.usuarios import Usuario, roles
from src.integraciones.base import ErrorDeIntegracion
from src.integraciones.mail import mail


def _login_medico(client, crear_medico):
    email = crear_medico()
    with mail.record_messages() as enviados:
        respuesta = client.post("/login", data={"email": email, "contrasena": "contrasena-de-test"})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/verificar"
    client.post("/verificar", data={"codigo": codigo_de_verificacion(enviados[0])})
    return email


def _datos(patologia_id, **cambios):
    datos = {
        "dni": "12345678",
        "nombre": "Ana",
        "apellido": "Prueba",
        "fecha_nacimiento": "2000-01-01",
        "telefono": "+54 9 221 555-1234",
        "email": "ana.paciente@exoma.test",
        "tipo_sospecha": "clinica",
        "resumen_historia_clinica": "Debilidad muscular progresiva.",
        "patologia": [str(patologia_id)],
        "sintoma": ["S-CARDINAL|Síntoma cardinal de prueba"],
    }
    datos.update(cambios)
    return datos


def _patologia(app, crear_patologia):
    with app.app_context():
        patologia = crear_patologia(
            nombre="Pompe de prueba",
            cardinal=("S-CARDINAL", "Síntoma cardinal de prueba"),
            secundarios=(
                ("S-SEC-1", "Síntoma secundario uno"),
                ("S-SEC-2", "Síntoma secundario dos"),
            ),
        )
        return patologia.id


def test_alta_completa_envia_credenciales_y_registra_auditoria(
    app, client, crear_medico, crear_patologia, tmp_path, monkeypatch
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)
    from src.integraciones import familiograma

    generar = familiograma.generar
    payloads = []

    def capturar_payload(familiares, **opciones):
        payloads.extend(familiares)
        return generar(familiares, **opciones)

    monkeypatch.setattr(familiograma, "generar", capturar_payload)

    with mail.record_messages() as mensajes:
        respuesta = client.post(
            "/pacientes/nuevo",
            data=_datos(
                patologia,
                familiares_parentesco=["madre"],
                familiares_nombre=["Eva Prueba"],
                familiares_dni=[""],
                familiares_sintomas_0=["S-SEC-1|Síntoma secundario uno"],
                familiares_patologias_0=[str(patologia)],
            ),
        )

    assert respuesta.status_code == 302
    assert respuesta.location.startswith("/pacientes/")
    paciente_id = int(respuesta.location.rsplit("/", 1)[1])
    with app.app_context():
        paciente = db.session.get(Paciente, paciente_id)
        assert paciente.usuario.debe_cambiar_contrasena is True
        assert paciente.usuario.rol_codigo == roles.PACIENTE
        assert len(paciente.sintomas) == 1
        assert len(paciente.diagnosticos_presuntivos) == 1
        assert len(paciente.familiares) == 1
        assert paciente.familiares[0].paciente_vinculado_id is None
        assert paciente.familiograma_path == f"pacientes/{paciente_id}/familiograma.pdf"
        assert (tmp_path / paciente.familiograma_path).is_file()
        assert (
            db.session.scalar(
                sa.select(sa.func.count())
                .select_from(RegistroDeCambio)
                .where(
                    RegistroDeCambio.entidad == Entidad.PACIENTE,
                    RegistroDeCambio.entidad_id == paciente_id,
                )
            )
            >= 2
        )
        assert (
            paciente.usuario.hash_contrasena
            != mensajes[0].body.split("Contraseña: ")[1].splitlines()[0]
        )
    assert len(mensajes) == 1
    assert "Contraseña:" in mensajes[0].body
    assert "ana.paciente@exoma.test" in mensajes[0].recipients
    assert payloads == [
        {
            "parentesco": "madre",
            "nombre": "Eva Prueba",
            "sintomas": [{"codigo": "S-SEC-1", "termino": "Síntoma secundario uno"}],
            "patologias": ["Pompe de prueba"],
        }
    ]


def test_rechazo_de_e08_no_guarda_y_preserva_el_formulario(
    app, client, crear_medico, crear_patologia
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)

    respuesta = client.post(
        "/pacientes/nuevo",
        data=_datos(patologia, sintoma=["S-SEC-1|Síntoma secundario uno"]),
    )

    assert respuesta.status_code == 400
    assert "Pompe de prueba" in respuesta.text
    assert "Ana" in respuesta.text
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Paciente)) == 0
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Usuario)) == 2


def test_sospecha_familiar_acepta_sin_sintomas_si_hay_diagnostico_familiar(
    app, client, crear_medico, crear_patologia, tmp_path
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)

    respuesta = client.post(
        "/pacientes/nuevo",
        data=_datos(
            patologia,
            tipo_sospecha="familiar",
            sintoma=[],
            familiares_parentesco=["madre"],
            familiares_nombre=["Eva"],
            familiares_dni=[""],
            familiares_sintomas_0=[],
            familiares_patologias_0=[str(patologia)],
        ),
    )

    assert respuesta.status_code == 302
    with app.app_context():
        paciente = db.session.scalar(sa.select(Paciente).where(Paciente.dni == "12345678"))
        assert paciente.tipo_sospecha.value == "familiar"
        assert paciente.familiares[0].patologias[0].patologia_id == patologia


def test_rechaza_dni_mail_repetido_y_resumen_vacio(app, client, crear_medico, crear_patologia):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    creada = client.post("/pacientes/nuevo", data=_datos(patologia))
    assert creada.status_code == 302

    respuesta_dni = client.post(
        "/pacientes/nuevo",
        data=_datos(patologia, email="otro.dni@exoma.test"),
    )
    respuesta_mail = client.post(
        "/pacientes/nuevo",
        data=_datos(patologia, dni="22345678"),
    )
    respuesta_resumen = client.post(
        "/pacientes/nuevo",
        data=_datos(
            patologia,
            dni="32345678",
            email="otra@exoma.test",
            resumen_historia_clinica=" ",
        ),
    )

    assert respuesta_dni.status_code == 400
    assert "Ya hay un paciente con ese DNI" in respuesta_dni.text
    assert respuesta_mail.status_code == 400
    assert "Ya hay un usuario con ese mail" in respuesta_mail.text
    assert respuesta_resumen.status_code == 400
    assert "Completá el resumen" in respuesta_resumen.text


def test_transcripcion_con_mock(client, crear_medico):
    _login_medico(client, crear_medico)

    respuesta = client.post(
        "/pacientes/transcribir",
        data={"audio": (io.BytesIO(b"audio de prueba"), "resumen.webm")},
        content_type="multipart/form-data",
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["texto"].startswith("Paciente con debilidad")


def test_familiograma_caido_se_reintenta_sin_perder_el_alta(
    app, client, crear_medico, crear_patologia, tmp_path, monkeypatch
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)

    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("Familiograma", "API de familiograma no disponible.")

    monkeypatch.setattr("src.core.pacientes.servicios.familiograma.generar", caido)
    respuesta = client.post(
        "/pacientes/nuevo",
        data=_datos(
            patologia,
            familiares_parentesco=["madre"],
            familiares_nombre=["Eva"],
            familiares_dni=[""],
            familiares_sintomas_0=[],
            familiares_patologias_0=[],
        ),
    )

    assert respuesta.status_code == 302
    paciente_id = int(respuesta.location.rsplit("/", 1)[1])
    with app.app_context():
        paciente = db.session.get(Paciente, paciente_id)
        assert paciente is not None
        assert paciente.familiograma_path is None

    monkeypatch.undo()
    retry = client.post(f"/pacientes/{paciente_id}/familiograma")
    assert retry.status_code == 302
    with app.app_context():
        paciente = db.session.get(Paciente, paciente_id)
        assert paciente.familiograma_path == f"pacientes/{paciente_id}/familiograma.pdf"
        assert (tmp_path / paciente.familiograma_path).is_file()


def test_vincula_familiar_existente_y_paciente_nuevo_en_ambos_sentidos(
    app, client, crear_medico, crear_patologia, crear_paciente, crear_familiar
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    with app.app_context():
        paciente_existente = crear_paciente()
        familiar_esperando = crear_familiar(paciente_existente, dni="12345678")
        db.session.commit()
        familiar_id = familiar_esperando.id
        paciente_existente_id = paciente_existente.id
        paciente_existente_dni = paciente_existente.dni

    respuesta = client.post(
        "/pacientes/nuevo",
        data=_datos(
            patologia,
            familiares_parentesco=["madre"],
            familiares_nombre=["Paciente existente"],
            familiares_dni=[paciente_existente_dni],
            familiares_sintomas_0=[],
            familiares_patologias_0=[],
        ),
    )
    assert respuesta.status_code == 302
    nuevo_id = int(respuesta.location.rsplit("/", 1)[1])
    with app.app_context():
        nuevo = db.session.get(Paciente, nuevo_id)
        familiar_nuevo = nuevo.familiares[0]
        assert familiar_nuevo.paciente_vinculado_id == paciente_existente_id
        familiar_de_otro = db.session.get(Familiar, familiar_id)
        assert familiar_de_otro.paciente_vinculado_id == nuevo_id
        assert familiar_de_otro.vinculado_en is not None


def test_detalle_muestra_solo_codigo_y_estado_del_estudio_vinculado(
    app, client, crear_medico, crear_patologia, crear_estudio
):
    _login_medico(client, crear_medico)
    patologia = _patologia(app, crear_patologia)
    with app.app_context():
        estudio = crear_estudio()
        codigo_estudio = estudio.codigo
        dni_vinculado = estudio.paciente.dni
        nombre_vinculado = estudio.paciente.usuario.nombre_completo

    respuesta = client.post(
        "/pacientes/nuevo",
        data=_datos(
            patologia,
            familiares_parentesco=["hermano"],
            familiares_nombre=["Hermano informado"],
            familiares_dni=[dni_vinculado],
            familiares_sintomas_0=[],
            familiares_patologias_0=[],
        ),
    )
    paciente_id = int(respuesta.location.rsplit("/", 1)[1])

    lista = client.get("/pacientes?q=12345678")
    assert lista.status_code == 200
    assert "Ana Prueba" in lista.text

    detalle = client.get(f"/pacientes/{paciente_id}")
    assert detalle.status_code == 200
    assert codigo_estudio in detalle.text
    assert "Creado" in detalle.text
    assert nombre_vinculado not in detalle.text


def test_medico_solo_ve_sus_pacientes_y_administrativo_recibe_403(
    app, client, crear_medico, crear_paciente, crear_usuario, autenticar_como
):
    with app.app_context():
        paciente = crear_paciente()
        paciente_id = paciente.id
        db.session.commit()
    _login_medico(client, crear_medico)
    assert client.get(f"/pacientes/{paciente_id}").status_code == 404

    client.post("/logout")
    email = crear_usuario(roles.ADMINISTRATIVO)
    autenticar_como(email)
    assert client.get("/pacientes").status_code == 403
