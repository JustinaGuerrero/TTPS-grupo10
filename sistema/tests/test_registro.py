"""Auto registro de médicos y personal del laboratorio (E01 y E02)."""

import pytest
import sqlalchemy as sa
from conftest import codigo_de_verificacion

from src.core.database import db
from src.core.snomed import TerminoSnomed
from src.core.usuarios import (
    Medico,
    MedicoEspecialidad,
    Usuario,
    buscar_por_email,
    listar_activos_por_rol,
    roles,
)
from src.integraciones.mail import mail

DATOS_VALIDOS = {
    "rol_codigo": roles.MEDICO_TRATANTE,
    "nombre": "Ana",
    "apellido": "Gómez",
    "email": "ana.registro@exoma.test",
    "telefono": "+54 9 221 555-1234",
    "matricula": "MP-REG-1",
    "contrasena": "contrasena-segura",
    "confirmar_contrasena": "contrasena-segura",
}
ESPECIALIDADES = [
    "394580004|Genética clínica",
    "394537008|Pediatría",
]


def _registrar(client, **cambios):
    return client.post(
        "/registro",
        data={**DATOS_VALIDOS, "especialidad": ESPECIALIDADES, **cambios},
    )


@pytest.mark.parametrize(
    ("rol", "email", "matricula"),
    [
        (roles.MEDICO_TRATANTE, "medico@exoma.test", "MP-MED-1"),
        (roles.GERENTE_MEDICO, "gerente@exoma.test", "MP-GER-1"),
    ],
)
def test_registra_medico_con_dos_especialidades_y_puede_iniciar_sesion(
    app, client, rol, email, matricula
):
    respuesta = _registrar(client, rol_codigo=rol, email=email, matricula=matricula)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/login"
    with app.app_context():
        usuario = buscar_por_email(email)
        medico = db.session.get(Medico, usuario.id)
        asociaciones = db.session.scalars(
            sa.select(MedicoEspecialidad).where(MedicoEspecialidad.medico_id == usuario.id)
        ).all()
        assert {fila.termino_codigo for fila in asociaciones} == {"394580004", "394537008"}
        assert db.session.get(TerminoSnomed, "394580004").tipo == "especialidad"
        assert medico.matricula == matricula

    with mail.record_messages() as enviados:
        ingreso = client.post(
            "/login", data={"email": email, "contrasena": DATOS_VALIDOS["contrasena"]}
        )
    assert ingreso.status_code == 302
    assert ingreso.headers["Location"] == "/verificar"
    client.post("/verificar", data={"codigo": codigo_de_verificacion(enviados[0])})
    assert "Ana Gómez" in client.get("/").text


@pytest.mark.parametrize("rol", [roles.ADMINISTRATIVO, roles.BIOINFORMATICO])
def test_registra_personal_del_laboratorio_con_su_rol(app, client, rol):
    email = f"{rol}@exoma.test"
    respuesta = _registrar(
        client,
        rol_codigo=rol,
        email=email,
        especialidad=[],
        matricula="",
    )

    assert respuesta.status_code == 302
    with app.app_context():
        usuario = buscar_por_email(email)
        assert usuario.rol_codigo == rol
        assert db.session.get(Medico, usuario.id) is None
        if rol == roles.BIOINFORMATICO:
            assert usuario in listar_activos_por_rol(roles.BIOINFORMATICO)


def test_no_se_puede_autoregistrar_un_rol_no_habilitado(app, client):
    respuesta = _registrar(client, rol_codigo=roles.ADMINISTRADOR_GENERAL)

    assert respuesta.status_code == 400
    assert "Elegí un rol habilitado" in respuesta.text
    with app.app_context():
        assert buscar_por_email(DATOS_VALIDOS["email"]) is None


def test_mail_repetido_sin_distinguir_mayusculas_no_crea_usuario(app, client):
    _registrar(client, rol_codigo=roles.ADMINISTRATIVO, email="ana.registro@exoma.test")

    respuesta = _registrar(
        client,
        rol_codigo=roles.ADMINISTRATIVO,
        email="Ana.Registro@EXOMA.test",
        especialidad=[],
    )

    assert respuesta.status_code == 400
    assert "Ya hay un usuario con ese mail." in respuesta.text
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Usuario)) == 1


def test_matricula_repetida_no_crea_usuario(app, client):
    _registrar(client)

    respuesta = _registrar(
        client,
        email="otra.medica@exoma.test",
        matricula=DATOS_VALIDOS["matricula"],
    )

    assert respuesta.status_code == 400
    assert "Ya hay un médico con esa matrícula." in respuesta.text
    with app.app_context():
        assert buscar_por_email("otra.medica@exoma.test") is None


def test_medico_sin_especialidades_no_se_crea(app, client):
    respuesta = _registrar(client, especialidad=[])

    assert respuesta.status_code == 400
    assert "Elegí al menos una especialidad." in respuesta.text
    with app.app_context():
        assert buscar_por_email(DATOS_VALIDOS["email"]) is None


def test_contrasena_debe_tener_ocho_caracteres_y_confirmarse(app, client):
    respuesta = _registrar(
        client,
        contrasena="corta",
        confirmar_contrasena="otra",
    )

    assert respuesta.status_code == 400
    assert "al menos 8 caracteres" in respuesta.text
    assert "Las contraseñas no coinciden." in respuesta.text
    with app.app_context():
        assert buscar_por_email(DATOS_VALIDOS["email"]) is None


def test_busqueda_publica_consulta_especialidades_snomed(client, monkeypatch):
    def buscar(texto, tipo):
        assert texto == "gene"
        assert tipo == "especialidad"
        from src.integraciones.snomed import TerminoSnomed

        return [TerminoSnomed("394580004", "Genética clínica")]

    monkeypatch.setattr("src.web.controllers.registro.integracion_snomed.buscar_terminos", buscar)
    respuesta = client.get("/registro/especialidades?q=gene")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == [{"codigo": "394580004", "termino": "Genética clínica"}]


def test_busqueda_publica_muestra_error_legible_si_snomed_no_responde(client, monkeypatch):
    from src.integraciones.base import ErrorDeIntegracion

    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("SNOMED", "SNOMED no respondió a tiempo.")

    monkeypatch.setattr("src.web.controllers.registro.integracion_snomed.buscar_terminos", caido)
    respuesta = client.get("/registro/especialidades?q=gene")

    assert respuesta.status_code == 503
    assert "SNOMED no respondió a tiempo." in respuesta.get_json()["error"]
