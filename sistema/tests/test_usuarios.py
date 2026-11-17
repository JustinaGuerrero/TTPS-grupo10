"""E03 Dar de alta usuario: grilla de usuarios y alta con credenciales por mail.

Los tests siguen los episodios del escenario (docs/escenarios.md) y después la grilla y el
acceso. El administrador general es el único que entra.
"""

import re
import smtplib

import pytest
import sqlalchemy as sa
from conftest import codigo_de_verificacion

from src.core.database import db
from src.core.paginacion import Pagina
from src.core.provincias import Provincia
from src.core.usuarios import (
    BusquedaDeUsuarios,
    DatosDeAlta,
    ErrorDeValidacion,
    Medico,
    MedicoEspecialidad,
    Transportista,
    Usuario,
    alta,
    buscar_por_email,
    buscar_usuarios,
    dar_de_alta_usuario,
    generar_contrasena_provisoria,
    roles,
)
from src.integraciones.mail import mail

DATOS_VALIDOS = {
    "rol_codigo": roles.ADMINISTRATIVO,
    "nombre": "Ana",
    "apellido": "Gómez",
    "email": "ana.gomez@exoma.test",
    "telefono": "+54 9 221 555-1234",
}


@pytest.fixture
def admin(login_como):
    """Cliente con sesión de administrador general."""
    return login_como(roles.ADMINISTRADOR_GENERAL)


def _alta(client, **cambios):
    datos = {**DATOS_VALIDOS, **cambios}
    return client.post("/usuarios/nuevo", data=datos)


def _usuario(app, email: str) -> Usuario | None:
    with app.app_context():
        usuario = buscar_por_email(email)
        if usuario is not None:
            db.session.expunge(usuario)
        return usuario


def _provincia(app, nombre: str) -> int:
    with app.app_context():
        return db.session.scalars(sa.select(Provincia.id).where(Provincia.nombre == nombre)).one()


def _contrasena_del_mail(mensaje) -> str:
    coincidencia = re.search(r"Contraseña: (\S+)", mensaje.body)
    assert coincidencia, mensaje.body
    return coincidencia.group(1)


# --- Episodio 1: el administrador general elige el rol del nuevo usuario ---


def test_el_formulario_ofrece_solo_los_cinco_roles_del_escenario(admin):
    respuesta = admin.get("/usuarios/nuevo")

    assert respuesta.status_code == 200
    opciones = re.findall(
        r'<option value="([a-z_]+)"', respuesta.text.split('id="provincia_id"')[0]
    )
    assert opciones == [
        roles.MEDICO_TRATANTE,
        roles.GERENTE_MEDICO,
        roles.ADMINISTRATIVO,
        roles.BIOINFORMATICO,
        roles.TRANSPORTISTA,
    ]


@pytest.mark.parametrize("rol", ["", roles.PACIENTE, roles.ADMINISTRADOR_GENERAL, "superusuario"])
def test_no_se_da_de_alta_con_un_rol_fuera_del_escenario(app, admin, rol):
    respuesta = _alta(admin, rol_codigo=rol)

    assert respuesta.status_code == 400
    assert "Elegí el rol del nuevo usuario." in respuesta.text
    assert _usuario(app, DATOS_VALIDOS["email"]) is None


# --- Episodio 2: completa los datos que corresponden al rol ---


@pytest.mark.parametrize("rol", [roles.ADMINISTRATIVO, roles.BIOINFORMATICO])
def test_administrativo_y_bioinformatico_se_dan_de_alta_con_sus_datos(app, admin, rol):
    # La matrícula no corresponde a estos roles: se ignora.
    respuesta = _alta(admin, rol_codigo=rol, matricula="MP-1")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/usuarios"
    usuario = _usuario(app, DATOS_VALIDOS["email"])
    assert (usuario.nombre, usuario.apellido, usuario.telefono, usuario.rol_codigo) == (
        "Ana",
        "Gómez",
        "+54 9 221 555-1234",
        rol,
    )
    with app.app_context():
        assert db.session.get(Medico, usuario.id) is None
        assert db.session.get(Transportista, usuario.id) is None


@pytest.mark.parametrize("rol", [roles.MEDICO_TRATANTE, roles.GERENTE_MEDICO])
def test_medico_tratante_y_gerente_medico_se_dan_de_alta_con_matricula(app, admin, rol):
    respuesta = _alta(
        admin,
        rol_codigo=rol,
        matricula="  MP-12345  ",
        especialidad=["394580004|Genética clínica"],
    )

    assert respuesta.status_code == 302
    usuario = _usuario(app, DATOS_VALIDOS["email"])
    with app.app_context():
        assert db.session.get(Medico, usuario.id).matricula == "MP-12345"
        assert db.session.get(MedicoEspecialidad, (usuario.id, "394580004")) is not None


@pytest.mark.parametrize("rol", [roles.MEDICO_TRATANTE, roles.GERENTE_MEDICO])
def test_medico_sin_matricula_no_se_da_de_alta(app, admin, rol):
    respuesta = _alta(admin, rol_codigo=rol, matricula="")

    assert respuesta.status_code == 400
    assert "Completá la matrícula." in respuesta.text
    assert _usuario(app, DATOS_VALIDOS["email"]) is None


def test_medico_sin_especialidades_no_se_da_de_alta(app, admin):
    respuesta = _alta(admin, rol_codigo=roles.MEDICO_TRATANTE, matricula="MP-1")

    assert respuesta.status_code == 400
    assert "Elegí al menos una especialidad." in respuesta.text
    assert _usuario(app, DATOS_VALIDOS["email"]) is None


def test_la_matricula_no_se_repite(app, admin):
    _alta(
        admin,
        rol_codigo=roles.MEDICO_TRATANTE,
        matricula="MP-1",
        especialidad=["394580004|Genética clínica"],
    )

    respuesta = _alta(
        admin, rol_codigo=roles.GERENTE_MEDICO, matricula="MP-1", email="otro@exoma.test"
    )

    assert respuesta.status_code == 400
    assert "Ya hay un médico con esa matrícula." in respuesta.text
    assert _usuario(app, "otro@exoma.test") is None


def test_transportista_se_da_de_alta_con_su_provincia(app, admin):
    salta = _provincia(app, "Salta")

    respuesta = _alta(admin, rol_codigo=roles.TRANSPORTISTA, provincia_id=str(salta))

    assert respuesta.status_code == 302
    usuario = _usuario(app, DATOS_VALIDOS["email"])
    with app.app_context():
        assert db.session.get(Transportista, usuario.id).provincia.nombre == "Salta"


@pytest.mark.parametrize("provincia_id", ["", "abc", "999999", "1" * 40])
def test_transportista_sin_provincia_valida_no_se_da_de_alta(app, admin, provincia_id):
    respuesta = _alta(admin, rol_codigo=roles.TRANSPORTISTA, provincia_id=provincia_id)

    assert respuesta.status_code == 400
    assert "Elegí la provincia del transportista." in respuesta.text
    assert _usuario(app, DATOS_VALIDOS["email"]) is None


def test_hay_un_transportista_por_provincia(app, admin):
    salta = str(_provincia(app, "Salta"))
    _alta(admin, rol_codigo=roles.TRANSPORTISTA, provincia_id=salta)

    formulario = admin.get("/usuarios/nuevo").text
    respuesta = _alta(
        admin, rol_codigo=roles.TRANSPORTISTA, provincia_id=salta, email="otro@exoma.test"
    )

    assert re.search(
        r'value="' + salta + r'"\s+disabled>\s+Salta \(ya tiene transportista\)', formulario
    )
    assert respuesta.status_code == 400
    assert "Salta ya tiene transportista: hay uno por provincia." in respuesta.text
    assert _usuario(app, "otro@exoma.test") is None


def test_campos_vacios_muestran_un_error_en_cada_uno(app, admin):
    respuesta = _alta(admin, nombre=" ", apellido="", email="", telefono="")

    assert respuesta.status_code == 400
    for mensaje in (
        "Completá el nombre.",
        "Completá el apellido.",
        "Completá el mail.",
        "Completá el teléfono.",
    ):
        assert mensaje in respuesta.text
    assert respuesta.text.count('aria-invalid="true"') == 4


@pytest.mark.parametrize("email", ["ana", "ana@exoma", "ana @exoma.test", "@exoma.test"])
def test_el_mail_tiene_que_ser_valido(app, admin, email):
    respuesta = _alta(admin, email=email)

    assert respuesta.status_code == 400
    assert "Ingresá un mail válido" in respuesta.text


def test_el_mail_no_se_repite_aunque_cambien_las_mayusculas(app, admin, crear_usuario):
    crear_usuario(roles.PACIENTE, email="ana.gomez@exoma.test")

    respuesta = _alta(admin, email="Ana.Gomez@EXOMA.test")

    assert respuesta.status_code == 400
    assert "Ya hay un usuario con ese mail." in respuesta.text


@pytest.mark.parametrize("telefono", ["telefono", "12345", "221-555-12a4", "1" * 31])
def test_el_telefono_tiene_que_ser_valido(app, admin, telefono):
    respuesta = _alta(admin, telefono=telefono)

    assert respuesta.status_code == 400
    assert "Ingresá un teléfono válido" in respuesta.text


def test_el_nombre_tiene_un_largo_maximo(app, admin):
    respuesta = _alta(admin, nombre="A" * 101)

    assert respuesta.status_code == 400
    assert "Usá como máximo 100 caracteres." in respuesta.text


def test_con_errores_el_formulario_conserva_lo_escrito(admin):
    respuesta = _alta(admin, rol_codigo=roles.MEDICO_TRATANTE, telefono="x", matricula="MP-9")

    assert 'value="Ana"' in respuesta.text
    assert 'value="ana.gomez@exoma.test"' in respuesta.text
    assert 'value="MP-9"' in respuesta.text
    assert '<option value="medico_tratante" selected>' in respuesta.text


def test_el_formulario_valida_tambien_en_el_cliente(admin):
    html = admin.get("/usuarios/nuevo").text

    assert "data-validar" in html
    assert "js/formularios.js" in html
    assert re.search(r'id="email"[^>]*\brequired\b', html, re.DOTALL)
    assert re.search(r'type="email"[^>]*id="email"', html, re.DOTALL)
    assert 'maxlength="100"' in html
    assert 'pattern="\\+?[0-9 \\(\\)\\-]{6,}"' in html
    # Matrícula y provincia: obligatorias solo cuando el rol las muestra.
    assert re.search(r'id="matricula"(?:(?!>).)*data-requerido', html, re.DOTALL)
    assert re.search(r'data-segun="rol_codigo"\s+data-valores="transportista"', html)


def test_otra_alta_simultanea_con_el_mismo_mail_da_error_de_validacion(app, monkeypatch):
    """Si otra alta guarda el mismo mail entre la validación y el guardado, choca el índice."""
    with app.app_context():
        db.session.add(
            Usuario(
                email="ana.gomez@exoma.test",
                hash_contrasena="hash",
                nombre="Otra",
                apellido="Ana",
                rol_codigo=roles.PACIENTE,
            )
        )
        db.session.flush()
        # La validación no la ve, como si la otra alta todavía no hubiera hecho commit.
        monkeypatch.setattr(alta, "buscar_por_email", lambda email: None)

        with pytest.raises(ErrorDeValidacion) as error:
            dar_de_alta_usuario(DatosDeAlta(**DATOS_VALIDOS))

        assert error.value.errores == {"email": "Ese dato ya está registrado."}
        # El savepoint deshizo solo el alta: la sesión sigue usable.
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Usuario)) == 1


@pytest.mark.parametrize(
    ("rol", "campo", "validacion_ciega"),
    [
        (roles.MEDICO_TRATANTE, "matricula", "_matricula_usada"),
        (roles.TRANSPORTISTA, "provincia_id", "provincias_con_transportista"),
    ],
)
def test_otra_alta_simultanea_con_la_misma_matricula_o_provincia(
    app, monkeypatch, usuario_rapido, rol, campo, validacion_ciega
):
    """Los nombres de los índices únicos de la migración coinciden con CAMPO_DE_CADA_RESTRICCION."""
    with app.app_context():
        provincia = db.session.scalars(
            sa.select(Provincia).where(Provincia.nombre == "Salta")
        ).one()
        otro = usuario_rapido(rol)
        if rol == roles.MEDICO_TRATANTE:
            db.session.add(Medico(usuario=otro, matricula="MP-1"))
        else:
            db.session.add(Transportista(usuario=otro, provincia=provincia))
        db.session.flush()
        ciega = (lambda matricula: False) if campo == "matricula" else (lambda: set())
        monkeypatch.setattr(alta, validacion_ciega, ciega)
        datos = DatosDeAlta(
            **{**DATOS_VALIDOS, "rol_codigo": rol},
            matricula="MP-1",
            provincia_id=str(provincia.id),
        )

        with pytest.raises(ErrorDeValidacion) as error:
            dar_de_alta_usuario(datos)

        assert error.value.errores == {campo: "Ese dato ya está registrado."}


# --- Episodio 3: el sistema crea las credenciales de acceso ---


def test_la_contrasena_provisoria_es_aleatoria_y_facil_de_copiar():
    contrasenas = {generar_contrasena_provisoria() for _ in range(50)}

    assert len(contrasenas) == 50
    for contrasena in contrasenas:
        assert len(contrasena) == 12
        assert any(c.isdigit() for c in contrasena)
        assert any(c.isalpha() for c in contrasena)
        assert not set(contrasena) & set("0O1lI")


def test_el_nuevo_usuario_inicia_sesion_con_la_contrasena_del_mail(app, admin):
    with mail.record_messages() as enviados:
        _alta(admin)
    contrasena = _contrasena_del_mail(enviados[0])

    usuario = _usuario(app, DATOS_VALIDOS["email"])
    assert contrasena not in usuario.hash_contrasena
    assert usuario.hash_contrasena.startswith("scrypt:")
    assert usuario.activo

    nuevo = app.test_client()
    with mail.record_messages() as verificacion:
        respuesta = nuevo.post(
            "/login", data={"email": DATOS_VALIDOS["email"], "contrasena": contrasena}
        )
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/verificar"
    nuevo.post("/verificar", data={"codigo": codigo_de_verificacion(verificacion[0])})
    assert "Ana Gómez" in nuevo.get("/").text


# --- Episodio 4: el sistema le manda por mail sus credenciales de acceso ---


def test_el_mail_lleva_las_credenciales_y_el_link_de_ingreso(app, admin):
    with mail.record_messages() as enviados:
        respuesta = _alta(admin, rol_codigo=roles.BIOINFORMATICO)

    assert len(enviados) == 1
    mensaje = enviados[0]
    assert mensaje.recipients == ["ana.gomez@exoma.test"]
    assert mensaje.subject == "Tus credenciales de acceso al sistema de exoma"
    assert "Hola, Ana:" in mensaje.body
    assert "con el rol Bioinformático" in mensaje.body
    assert "Usuario: ana.gomez@exoma.test" in mensaje.body
    assert "Ingresá en: http://exoma.test/login" in mensaje.body
    pagina = admin.get(respuesta.headers["Location"]).text
    assert "Le enviamos sus credenciales de acceso a ana.gomez@exoma.test." in pagina


def test_la_contrasena_no_queda_en_los_avisos(app, admin):
    with mail.record_messages() as enviados:
        _alta(admin)
    contrasena = _contrasena_del_mail(enviados[0])

    with app.app_context():
        mensajes = db.session.scalars(sa.text("select mensaje from notificaciones")).all()
    assert not any(contrasena in mensaje for mensaje in mensajes)


def test_si_el_mail_no_sale_no_se_crea_el_usuario(app, admin, monkeypatch):
    def servidor_caido(mensaje):
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    monkeypatch.setattr(mail, "send", servidor_caido)

    respuesta = _alta(
        admin, rol_codigo=roles.TRANSPORTISTA, provincia_id=str(_provincia(app, "Jujuy"))
    )

    assert respuesta.status_code == 503
    assert "No se pudo enviar el mail con las credenciales" in respuesta.text
    assert 'value="ana.gomez@exoma.test"' in respuesta.text
    assert _usuario(app, DATOS_VALIDOS["email"]) is None
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Transportista)) == 0


# --- Grilla: búsqueda, filtro por rol, orden y paginación ---


@pytest.fixture
def usuarios_de_la_grilla(app):
    """Cuatro usuarios con nombres y mails conocidos, además del administrador del test."""
    datos = [
        ("Ana", "Gómez", "ana@lab.test", roles.ADMINISTRATIVO),
        ("Bruno", "Álvarez", "bruno@lab.test", roles.BIOINFORMATICO),
        ("carla", "zapata", "Carla.Z@lab.test", roles.MEDICO_TRATANTE),
        ("Diego", "Pérez", "diego_100%@lab.test", roles.TRANSPORTISTA),
    ]
    with app.app_context():
        for nombre, apellido, email, rol in datos:
            db.session.add(
                Usuario(
                    email=email,
                    hash_contrasena="hash",
                    nombre=nombre,
                    apellido=apellido,
                    rol_codigo=rol,
                )
            )
        db.session.commit()


def _mails(app, **parametros) -> list[str]:
    with app.app_context():
        pagina = buscar_usuarios(BusquedaDeUsuarios.desde(parametros))
        return [usuario.email for usuario in pagina.items]


def test_la_grilla_lista_los_usuarios_con_su_rol(admin, usuarios_de_la_grilla):
    respuesta = admin.get("/usuarios")

    assert respuesta.status_code == 200
    assert "Gómez, Ana" in respuesta.text
    assert "Bioinformático" in respuesta.text
    assert "1–5 de 5 usuarios" in respuesta.text
    assert 'href="/usuarios/nuevo"' in respuesta.text


def test_por_defecto_muestra_primero_los_ultimos_dados_de_alta(app, usuarios_de_la_grilla):
    assert _mails(app)[:2] == ["diego_100%@lab.test", "Carla.Z@lab.test"]


@pytest.mark.parametrize(
    ("texto", "esperados"),
    [
        ("ana", ["ana@lab.test"]),
        ("GÓMEZ", ["ana@lab.test"]),
        ("lab.test", ["ana@lab.test", "bruno@lab.test", "Carla.Z@lab.test", "diego_100%@lab.test"]),
        ("carla zap", ["Carla.Z@lab.test"]),
        ("carla gómez", []),
        ("100%", ["diego_100%@lab.test"]),
        ("%", ["diego_100%@lab.test"]),
        ("_", ["diego_100%@lab.test"]),
    ],
)
def test_busca_por_nombre_o_mail(app, usuarios_de_la_grilla, texto, esperados):
    assert sorted(_mails(app, texto=texto, orden="email", direccion="asc")) == sorted(esperados)


def test_filtra_por_rol(app, usuarios_de_la_grilla):
    assert _mails(app, rol=roles.BIOINFORMATICO) == ["bruno@lab.test"]


def test_busqueda_y_filtro_juntos(app, usuarios_de_la_grilla):
    assert _mails(app, texto="lab", rol=roles.ADMINISTRATIVO) == ["ana@lab.test"]
    assert _mails(app, texto="ana", rol=roles.BIOINFORMATICO) == []


def test_sin_resultados_lo_dice_y_ofrece_ver_todos(admin, usuarios_de_la_grilla):
    respuesta = admin.get("/usuarios?texto=nadie")

    assert "Ningún usuario coincide con la búsqueda." in respuesta.text
    assert '<a href="/usuarios">Ver todos</a>' in respuesta.text


def test_ordena_por_nombre_sin_distinguir_mayusculas(app, usuarios_de_la_grilla):
    ascendente = _mails(app, texto="lab", orden="nombre", direccion="asc")
    descendente = _mails(app, texto="lab", orden="nombre", direccion="desc")

    # Por apellido: Álvarez, Gómez, Pérez, zapata (la minúscula no va al final).
    assert ascendente == [
        "bruno@lab.test",
        "ana@lab.test",
        "diego_100%@lab.test",
        "Carla.Z@lab.test",
    ]
    assert descendente == ascendente[::-1]


def test_ordena_por_mail_y_por_rol(app, usuarios_de_la_grilla):
    assert _mails(app, texto="lab", orden="email", direccion="asc") == [
        "ana@lab.test",
        "bruno@lab.test",
        "Carla.Z@lab.test",
        "diego_100%@lab.test",
    ]
    # Administrativo, Bioinformático, Médico tratante, Transportista.
    assert _mails(app, texto="lab", orden="rol", direccion="desc") == [
        "diego_100%@lab.test",
        "Carla.Z@lab.test",
        "bruno@lab.test",
        "ana@lab.test",
    ]


def test_la_cabecera_activa_invierte_el_orden_y_conserva_los_filtros(admin, usuarios_de_la_grilla):
    html = admin.get("/usuarios?texto=lab&rol=administrativo&orden=nombre&direccion=asc").text

    assert 'aria-sort="ascending"' in html
    # Descendente es la dirección por defecto: no va en la URL.
    assert 'href="/usuarios?texto=lab&amp;rol=administrativo&amp;orden=nombre"' in html
    # Otra columna empieza de la A a la Z.
    assert (
        'href="/usuarios?texto=lab&amp;rol=administrativo&amp;orden=email&amp;direccion=asc"'
        in html
    )


def test_parametros_invalidos_usan_los_valores_por_defecto(admin, usuarios_de_la_grilla):
    respuesta = admin.get("/usuarios?orden=hash_contrasena&direccion=;drop&rol=jefe&pagina=-3")

    assert respuesta.status_code == 200
    assert "1–5 de 5 usuarios" in respuesta.text
    assert (
        BusquedaDeUsuarios.desde(
            {"orden": "hash_contrasena", "direccion": "x", "rol": "jefe", "pagina": "9" * 50}
        )
        == BusquedaDeUsuarios()
    )


def test_pagina_del_lado_del_servidor_y_los_links_conservan_la_busqueda(app, admin, usuario_rapido):
    with app.app_context():
        for _ in range(23):
            usuario_rapido(roles.BIOINFORMATICO)
        db.session.commit()

    primera = admin.get("/usuarios?rol=bioinformatico")
    segunda = admin.get("/usuarios?rol=bioinformatico&pagina=2")
    despues_de_la_ultima = admin.get("/usuarios?rol=bioinformatico&pagina=99")

    assert primera.text.count("<tr>") == 1 + 20
    assert "1–20 de 23 usuarios" in primera.text
    assert 'href="/usuarios?rol=bioinformatico&amp;pagina=2"' in primera.text
    assert segunda.text.count("<tr>") == 1 + 3
    assert "21–23 de 23 usuarios" in segunda.text
    assert 'aria-current="page"><span class="page-link">2</span>' in segunda.text
    assert "21–23 de 23 usuarios" in despues_de_la_ultima.text


def test_busqueda_arma_los_parametros_sin_los_valores_por_defecto():
    busqueda = BusquedaDeUsuarios(texto="ana", orden="email", direccion="asc", pagina=3)

    assert BusquedaDeUsuarios().parametros() == {}
    assert busqueda.parametros() == {"texto": "ana", "orden": "email", "direccion": "asc"}
    assert busqueda.parametros(pagina=4)["pagina"] == 4
    assert busqueda.al_ordenar_por("email") == {"texto": "ana", "orden": "email"}
    assert busqueda.al_ordenar_por("alta") == {"texto": "ana"}


@pytest.mark.parametrize(
    ("numero", "total", "esperados"),
    [
        (1, 0, [1]),
        (1, 60, [1, 2, 3]),
        (1, 200, [1, 2, 3, None, 10]),
        (6, 200, [1, None, 4, 5, 6, 7, 8, None, 10]),
        (10, 200, [1, None, 8, 9, 10]),
        (4, 200, [1, 2, 3, 4, 5, 6, None, 10]),
    ],
)
def test_pagina_muestra_los_numeros_cercanos_a_la_actual(numero, total, esperados):
    pagina = Pagina(items=[], numero=numero, por_pagina=20, total=total)

    assert pagina.numeros_visibles == esperados


# --- Acceso: solo el administrador general ---


def test_el_menu_del_administrador_lleva_a_usuarios(admin):
    html = admin.get("/usuarios/nuevo").text

    assert re.search(
        r'class="nav-link active" aria-current="page"\s+href="/usuarios">Usuarios', html
    )


@pytest.mark.parametrize("ruta", ["/usuarios", "/usuarios/nuevo"])
def test_sin_sesion_lleva_al_login(client, ruta):
    respuesta = client.get(ruta)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].startswith("/login")


def test_sin_sesion_no_se_puede_dar_de_alta(app, client):
    respuesta = _alta(client)

    assert respuesta.status_code == 302
    assert _usuario(app, DATOS_VALIDOS["email"]) is None


@pytest.mark.parametrize("rol", [rol for rol in roles.TODOS if rol != roles.ADMINISTRADOR_GENERAL])
def test_los_demas_roles_no_entran(app, login_como, rol):
    client = login_como(rol)

    assert client.get("/usuarios").status_code == 403
    assert client.get("/usuarios/nuevo").status_code == 403
    assert _alta(client).status_code == 403
    assert _usuario(app, DATOS_VALIDOS["email"]) is None
    assert 'href="/usuarios"' not in client.get("/").text
