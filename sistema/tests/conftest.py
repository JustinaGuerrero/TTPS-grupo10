"""Fixtures compartidos: la base de test, la app, el cliente y el login por rol.

Los tests corren contra DATABASE_URL_TEST, nunca contra la base compartida de Supabase.
Al empezar la corrida, `base_de_test` borra el esquema public de esa base y aplica en
orden todas las migraciones de supabase/migrations (src/core/migraciones.py). En cada test,
lo que se escribe con db.session, aunque haga commit, se revierte al terminar (ver `app`).

Las fábricas de datos (crear_usuario, usuario_rapido, crear_paciente, crear_estudio…) están en
fabricas.py, que se carga con pytest_plugins.
"""

import os
import re

import pytest
import sqlalchemy as sa
from dotenv import load_dotenv

from src.core import migraciones
from src.core.database import db
from src.core.usuarios import buscar_por_email
from src.web import create_app
from src.web.helpers.auth import CLAVE_DE_SESION

pytest_plugins = ["fabricas"]

# Contraseña de los usuarios que crea la fábrica crear_usuario (no es la de `flask seeds`).
# Los tests la importan de acá: `from conftest import CONTRASENA_DE_TEST`.
CONTRASENA_DE_TEST = "contrasena-de-test"


def codigo_de_verificacion(mensaje) -> str:
    coincidencia = re.search(r"(?m)^\s+([0-9]{6})$", mensaje.body)
    assert coincidencia is not None, "El mail no contiene un código de seis dígitos"
    return coincidencia.group(1)


def _url_de_test() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL_TEST")
    if not url:
        pytest.exit("Falta DATABASE_URL_TEST en sistema/.env (ver .env.example).", returncode=1)
    motivo = migraciones.motivo_para_no_borrar(url, os.getenv("DATABASE_URL"))
    if motivo:
        pytest.exit(
            f"DATABASE_URL_TEST no sirve para los tests ({motivo}): los tests borran su esquema "
            "public. Usá una base local.",
            returncode=1,
        )
    return url


@pytest.fixture(scope="session")
def base_de_test():
    url = _url_de_test()
    try:
        # Así nadie tiene que correr createdb para la base de test (por ejemplo exoma_test).
        migraciones.crear_base_si_falta(url)
    except sa.exc.OperationalError as error:
        sin_clave = sa.make_url(url).render_as_string(hide_password=True)
        pytest.exit(f"No se pudo conectar a la base de test ({sin_clave}): {error.orig}", 1)
    try:
        migraciones.aplicar_migraciones(url)
    except migraciones.MigracionFallida as error:
        pytest.exit(str(error), returncode=1)


@pytest.fixture
def app(base_de_test):
    """App de test cuyas sesiones escriben dentro de una transacción que se revierte al final.

    Es la receta de SQLAlchemy "Joining a Session into an External Transaction". No usamos
    db.test_isolation() de Flask-SQLAlchemy-Lite 0.2.1 porque con SQLAlchemy 2.1 el commit
    de la sesión confirma la transacción externa: los datos quedan guardados y el test
    siguiente falla con RecursionError.
    """
    app = create_app("testing")
    with app.app_context():
        motor = db.engine
        sesiones = db.sessionmaker

    conexion = motor.connect()
    transaccion = conexion.begin()
    # Ligada a la conexión, cada sesión abre un savepoint y su commit() solo lo libera.
    sesiones.configure(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield app
    finally:
        transaccion.rollback()
        conexion.close()
        motor.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def autenticar_como(app, client):
    """Instala una sesión autenticada por email para tests que no prueban el login."""

    def _autenticar(email: str, otro_cliente=None):
        with app.app_context():
            usuario = buscar_por_email(email)
            assert usuario is not None
            usuario_id = usuario.id
        cliente = otro_cliente or client
        with cliente.session_transaction() as sesion:
            sesion[CLAVE_DE_SESION] = usuario_id
            sesion.permanent = True
        return cliente

    return _autenticar


@pytest.fixture
def login_como(crear_usuario, autenticar_como):
    """Crea un usuario e instala una sesión autenticada para los tests que no prueban el login."""

    def _login(rol: str):
        return autenticar_como(crear_usuario(rol))

    return _login
