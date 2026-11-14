"""Fixtures compartidos.

Los tests corren contra DATABASE_URL_TEST, nunca contra la base compartida de Supabase.
Al empezar la corrida, `base_de_test` borra el esquema public de esa base y aplica en
orden todas las migraciones de supabase/migrations. En cada test, lo que se escribe
con db.session, aunque haga commit, se revierte al terminar (ver el fixture `app`).
"""

import itertools
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from dotenv import load_dotenv

from src.core.database import db, url_de_conexion
from src.core.usuarios import crear_usuario as crear_usuario_en_core
from src.web import create_app

MIGRACIONES = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


def _url_de_test() -> sa.URL:
    load_dotenv()
    valor = os.getenv("DATABASE_URL_TEST")
    if not valor:
        pytest.exit("Falta DATABASE_URL_TEST en sistema/.env (ver .env.example).", returncode=1)

    url = sa.make_url(url_de_conexion(valor))
    compartida = os.getenv("DATABASE_URL")
    es_la_compartida = bool(compartida) and sa.make_url(url_de_conexion(compartida)) == url
    if "supabase" in (url.host or "") or es_la_compartida:
        pytest.exit(
            "DATABASE_URL_TEST apunta a la base compartida y los tests borran su esquema public. "
            "Usá una base local.",
            returncode=1,
        )
    return url


def _crear_base_si_falta(url: sa.URL) -> None:
    """Crea la base de test (por ejemplo exoma_test) para que nadie tenga que correr createdb."""
    motor = sa.create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as conexion:
            existe = conexion.scalar(
                sa.text("select 1 from pg_database where datname = :nombre"),
                {"nombre": url.database},
            )
            if not existe:
                nombre = conexion.dialect.identifier_preparer.quote(url.database)
                conexion.exec_driver_sql(f"create database {nombre}")
    except sa.exc.OperationalError as error:
        pytest.exit(
            f"No se pudo conectar a la base de test "
            f"({url.render_as_string(hide_password=True)}): {error.orig}",
            returncode=1,
        )
    finally:
        motor.dispose()


def _aplicar_migraciones(url: sa.URL) -> None:
    """Deja el esquema public vacío y aplica las migraciones en el orden de `db push`."""
    motor = sa.create_engine(url)
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql("drop schema if exists public cascade")
            conexion.exec_driver_sql("create schema public")
            for archivo in sorted(MIGRACIONES.glob("*.sql")):
                try:
                    # Sin parámetros, psycopg acepta varios statements y no interpreta los %.
                    conexion.exec_driver_sql(
                        archivo.read_text(encoding="utf-8"),
                        execution_options={"no_parameters": True},
                    )
                except sa.exc.DBAPIError as error:
                    pytest.exit(f"Falla la migración {archivo.name}: {error.orig}", returncode=1)
    finally:
        motor.dispose()


@pytest.fixture(scope="session")
def base_de_test():
    url = _url_de_test()
    _crear_base_si_falta(url)
    _aplicar_migraciones(url)


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


# Contraseña de los usuarios que crean los fixtures (no es la de `flask seeds`).
CONTRASENA_DE_TEST = "contrasena-de-test"


@pytest.fixture
def crear_usuario(app):
    """Fábrica: `crear_usuario(roles.PACIENTE)` guarda un usuario con ese rol y devuelve su mail.

    La contraseña es CONTRASENA_DE_TEST. Con `activo=False` queda desactivado.
    """
    numeros = itertools.count(1)

    def _crear(rol: str, email: str | None = None, activo: bool = True) -> str:
        email = email or f"{rol}.{next(numeros)}@exoma.test"
        with app.app_context():
            usuario = crear_usuario_en_core(email, CONTRASENA_DE_TEST, "Nombre", "De Test", rol)
            usuario.activo = activo
            db.session.commit()
        return email

    return _crear


@pytest.fixture
def login_como(client, crear_usuario):
    """Fábrica: `login_como(roles.ADMINISTRATIVO)` crea un usuario de ese rol y loguea `client`."""

    def _login(rol: str):
        email = crear_usuario(rol)
        respuesta = client.post("/login", data={"email": email, "contrasena": CONTRASENA_DE_TEST})
        assert respuesta.status_code == 302, f"No se pudo iniciar sesión como {rol}"
        return client

    return _login
