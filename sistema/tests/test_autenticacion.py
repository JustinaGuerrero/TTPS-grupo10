"""E04 Iniciar sesión (sin el código por dispositivo nuevo), cerrar sesión y control de acceso por rol."""

from urllib.parse import parse_qs, urlsplit

import pytest
import sqlalchemy as sa
from conftest import CONTRASENA_DE_TEST

from src.core.database import db
from src.core.usuarios import Usuario, roles
from src.web.helpers import menu
from src.web.helpers.auth import destino_seguro, login_required, rol_requerido

MENSAJE_DE_RECHAZO = "El mail o la contraseña no son correctos."


def _login(client, email, contrasena=CONTRASENA_DE_TEST, **extra):
    return client.post("/login", data={"email": email, "contrasena": contrasena, **extra})


def _redireccion(respuesta) -> tuple[str, dict[str, list[str]]]:
    partes = urlsplit(respuesta.headers["Location"])
    return partes.path, parse_qs(partes.query)


@pytest.fixture
def ruta_solo_administrativos(app):
    """Ruta de prueba restringida a un rol. Se registra antes del primer request del test."""

    @app.get("/solo-administrativos")
    @login_required
    @rol_requerido(roles.ADMINISTRATIVO)
    def solo_administrativos():
        return "Contenido para administrativos"


# --- Login correcto (E04, episodios 1, 2 y 6) ---


def test_login_correcto_entra_a_la_vista_de_su_rol(client, crear_usuario):
    email = crear_usuario(roles.BIOINFORMATICO)

    respuesta = _login(client, email)

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    inicio = client.get("/")
    assert inicio.status_code == 200
    assert "Hola, Nombre." in inicio.text
    assert "Bioinformático" in inicio.text
    assert "Cerrar sesión" in inicio.text


def test_login_no_distingue_mayusculas_ni_espacios_en_el_mail(client, crear_usuario):
    crear_usuario(roles.PACIENTE, email="ana.paciente@exoma.test")

    respuesta = _login(client, "  Ana.Paciente@EXOMA.test ")

    assert respuesta.status_code == 302


def test_la_contrasena_se_guarda_con_hash_scrypt(app, crear_usuario):
    email = crear_usuario(roles.PACIENTE)

    with app.app_context():
        usuario = db.session.scalars(sa.select(Usuario).where(Usuario.email == email)).one()

    assert usuario.hash_contrasena.startswith("scrypt:")
    assert CONTRASENA_DE_TEST not in usuario.hash_contrasena


def test_login_regenera_el_id_de_sesion(client, crear_usuario):
    email = crear_usuario(roles.ADMINISTRATIVO)
    client.get("/")  # Sin sesión: el aviso de "Iniciá sesión" crea una sesión anónima.
    id_anonimo = client.get_cookie("session").value

    _login(client, email)

    assert client.get_cookie("session").value != id_anonimo


def test_login_con_sesion_iniciada_va_al_inicio(login_como):
    client = login_como(roles.PACIENTE)

    respuesta = client.get("/login")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"


# --- Credenciales no válidas (E04, episodio 3) ---


def test_contrasena_incorrecta_rechaza_el_ingreso(client, crear_usuario):
    email = crear_usuario(roles.ADMINISTRATIVO)

    respuesta = _login(client, email, "otra-contrasena")

    assert respuesta.status_code == 401
    assert MENSAJE_DE_RECHAZO in respuesta.text
    assert f'value="{email}"' in respuesta.text  # Conserva el mail para reintentar.
    assert client.get("/").status_code == 302  # Sigue sin sesión.


def test_mail_inexistente_da_el_mismo_mensaje(client):
    respuesta = _login(client, "nadie@exoma.test")

    assert respuesta.status_code == 401
    assert MENSAJE_DE_RECHAZO in respuesta.text


def test_usuario_inactivo_no_puede_entrar(client, crear_usuario):
    email = crear_usuario(roles.ADMINISTRATIVO, activo=False)

    respuesta = _login(client, email)

    assert respuesta.status_code == 401
    assert MENSAJE_DE_RECHAZO in respuesta.text


def test_login_con_campos_vacios_pide_completarlos(client):
    respuesta = _login(client, "", "")

    assert respuesta.status_code == 400
    assert "Completá el mail y la contraseña." in respuesta.text


# --- Acceso sin sesión ---


def test_acceso_sin_sesion_redirige_al_login(client):
    respuesta = client.get("/")

    assert respuesta.status_code == 302
    ruta, parametros = _redireccion(respuesta)
    assert ruta == "/login"
    assert parametros["next"] == ["/"]
    login = client.get(respuesta.headers["Location"])
    assert "Iniciá sesión para continuar." in login.text
    assert "Cerrar sesión" not in login.text


def test_despues_del_login_vuelve_a_la_pagina_pedida(
    client, crear_usuario, ruta_solo_administrativos
):
    email = crear_usuario(roles.ADMINISTRATIVO)
    _, parametros = _redireccion(client.get("/solo-administrativos?pagina=2"))

    respuesta = _login(client, email, next=parametros["next"][0])

    assert respuesta.headers["Location"] == "/solo-administrativos?pagina=2"


def test_login_ignora_un_destino_de_otro_sitio(client, crear_usuario):
    email = crear_usuario(roles.ADMINISTRATIVO)

    respuesta = _login(client, email, next="https://otro-sitio.example/")

    assert respuesta.headers["Location"] == "/"


@pytest.mark.parametrize(
    "destino",
    ["https://otro-sitio.example/", "//otro-sitio.example/", "/\\otro-sitio.example", "inicio", ""],
)
def test_destino_seguro_descarta_lo_que_no_es_una_ruta_local(destino):
    assert destino_seguro(destino) is None


def test_destino_seguro_acepta_rutas_locales():
    assert destino_seguro("/estudios?pagina=2") == "/estudios?pagina=2"


def test_usuario_desactivado_pierde_la_sesion(app, client, crear_usuario):
    email = crear_usuario(roles.GERENTE_MEDICO)
    _login(client, email)

    with app.app_context():
        db.session.execute(sa.update(Usuario).where(Usuario.email == email).values(activo=False))
        db.session.commit()

    assert client.get("/").status_code == 302


# --- Rol equivocado ---


@pytest.mark.parametrize("rol", [r for r in roles.TODOS if r != roles.ADMINISTRATIVO])
def test_acceso_con_el_rol_equivocado_devuelve_403(login_como, ruta_solo_administrativos, rol):
    client = login_como(rol)

    respuesta = client.get("/solo-administrativos")

    assert respuesta.status_code == 403
    assert "Acceso denegado" in respuesta.text


def test_acceso_con_el_rol_correcto(login_como, ruta_solo_administrativos):
    client = login_como(roles.ADMINISTRATIVO)

    respuesta = client.get("/solo-administrativos")

    assert respuesta.status_code == 200
    assert respuesta.text == "Contenido para administrativos"


def test_rol_requerido_sin_sesion_redirige_al_login(client, ruta_solo_administrativos):
    respuesta = client.get("/solo-administrativos")

    assert respuesta.status_code == 302
    assert _redireccion(respuesta)[0] == "/login"


def test_rol_requerido_rechaza_roles_que_no_estan_en_el_lel():
    with pytest.raises(ValueError, match="medico"):
        rol_requerido("medico")
    with pytest.raises(ValueError):
        rol_requerido()


# --- Cerrar sesión ---


def test_logout_cierra_la_sesion(login_como):
    client = login_como(roles.TRANSPORTISTA)

    respuesta = client.post("/logout")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/login"
    assert "Cerraste la sesión." in client.get("/login").text
    assert client.get("/").status_code == 302


def test_logout_solo_acepta_post(login_como):
    client = login_como(roles.TRANSPORTISTA)

    assert client.get("/logout").status_code == 405


# --- Menú según el rol ---


def test_el_menu_tiene_una_entrada_por_rol_del_lel():
    assert set(menu.MENU_POR_ROL) == set(roles.TODOS)


def test_el_menu_cambia_segun_el_rol(app, client, crear_usuario, monkeypatch):
    item = menu.ItemDeMenu("Patologías de prueba", "inicio.index")
    monkeypatch.setitem(menu.MENU_POR_ROL, roles.GERENTE_MEDICO, [item])
    gerente, paciente = app.test_client(), app.test_client()
    _login(gerente, crear_usuario(roles.GERENTE_MEDICO))
    _login(paciente, crear_usuario(roles.PACIENTE))

    assert "Patologías de prueba" in gerente.get("/").text
    assert "Patologías de prueba" not in paciente.get("/").text
