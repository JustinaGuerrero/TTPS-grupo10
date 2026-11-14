"""Protección CSRF: todo POST necesita el token de la sesión (CSRFProtect de Flask-WTF).

En el resto de los tests está desactivada (TestingConfig); acá se activa con `csrf_activo`.
"""

import re
from pathlib import Path

import pytest
from conftest import CONTRASENA_DE_TEST

from src.core.usuarios import roles

PLANTILLAS = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
APERTURA_DE_FORM_POST = re.compile(r"<form\b[^>]*\bmethod\s*=\s*[\"']?post\b", re.IGNORECASE)
MENSAJE_DE_RECHAZO = "No se pudo enviar el formulario"


@pytest.fixture
def csrf_activo(app):
    app.config["WTF_CSRF_ENABLED"] = True


def _token(html: str) -> str:
    coincidencia = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert coincidencia, "La página no tiene el campo csrf_token"
    return coincidencia.group(1)


def _login(client, email, **extra):
    return client.post("/login", data={"email": email, "contrasena": CONTRASENA_DE_TEST, **extra})


def _login_con_token(client, email):
    return _login(client, email, csrf_token=_token(client.get("/login").text))


def test_login_sin_token_se_rechaza(client, crear_usuario, csrf_activo):
    email = crear_usuario(roles.ADMINISTRATIVO)

    respuesta = _login(client, email)

    assert respuesta.status_code == 400
    assert MENSAJE_DE_RECHAZO in respuesta.text
    assert client.get("/").status_code == 302  # No inició sesión.


def test_login_y_logout_con_token_funcionan(client, crear_usuario, csrf_activo):
    email = crear_usuario(roles.ADMINISTRATIVO)

    assert _login_con_token(client, email).status_code == 302
    inicio = client.get("/")
    assert inicio.status_code == 200

    respuesta = client.post("/logout", data={"csrf_token": _token(inicio.text)})

    assert respuesta.status_code == 302
    assert client.get("/").status_code == 302


def test_otro_sitio_no_puede_cerrar_la_sesion(client, crear_usuario, csrf_activo):
    _login_con_token(client, crear_usuario(roles.PACIENTE))

    # Un formulario de otro sitio puede mandar la cookie, pero no conoce el token.
    respuesta = client.post("/logout")

    assert respuesta.status_code == 400
    assert client.get("/").status_code == 200  # La sesión sigue abierta.


def test_el_token_de_otra_sesion_se_rechaza(app, client, crear_usuario, csrf_activo):
    email = crear_usuario(roles.ADMINISTRATIVO)
    token_ajeno = _token(app.test_client().get("/login").text)
    client.get("/login")

    respuesta = _login(client, email, csrf_token=token_ajeno)

    assert respuesta.status_code == 400


def test_el_token_tambien_se_acepta_en_el_header(client, crear_usuario, csrf_activo):
    email = crear_usuario(roles.ADMINISTRATIVO)
    token = _token(client.get("/login").text)

    respuesta = client.post(
        "/login",
        data={"email": email, "contrasena": CONTRASENA_DE_TEST},
        headers={"X-CSRFToken": token},
    )

    assert respuesta.status_code == 302


def test_todos_los_formularios_post_llevan_el_token():
    formularios, sin_token = 0, []
    for plantilla in sorted(PLANTILLAS.rglob("*.html")):
        texto = plantilla.read_text(encoding="utf-8")
        for apertura in APERTURA_DE_FORM_POST.finditer(texto):
            formularios += 1
            cierre = texto.find("</form>", apertura.end())
            if "csrf_token()" not in texto[apertura.start() : cierre]:
                linea = texto.count("\n", 0, apertura.start()) + 1
                sin_token.append(f"{plantilla.relative_to(PLANTILLAS).as_posix()}:{linea}")

    assert formularios >= 2, "No encontró los formularios de login y logout: revisar la búsqueda"
    assert not sin_token, f"Formularios POST sin csrf_token(): {sin_token}"
