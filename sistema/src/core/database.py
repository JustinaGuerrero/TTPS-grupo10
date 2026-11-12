"""Conexión a la base con Flask-SQLAlchemy-Lite.

Lite (no es Flask-SQLAlchemy) solo maneja engines y sesiones: no trae db.Model ni
create_all. Los modelos heredan de Base, que es SQLAlchemy puro, y el esquema sale
de las migraciones de supabase/migrations.

Uso en core: `db.session` es la sesión del contexto de app actual y se cierra sola
al terminar el request.
"""

from flask import Flask
from flask_sqlalchemy_lite import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""


# pool_pre_ping descarta las conexiones que el pooler de Supabase cerró por inactividad.
db = SQLAlchemy(engine_options={"pool_pre_ping": True})


def url_de_conexion(url: str) -> str:
    """Fuerza el driver psycopg 3 aunque la URL venga como la copia Supabase (postgresql://)."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url.removeprefix(prefijo)
    return url


def init_app(app: Flask) -> None:
    url = app.config.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta la URL de la base: DATABASE_URL (o DATABASE_URL_TEST en los tests). "
            "Copiá sistema/.env.example a sistema/.env y completala."
        )
    app.config["SQLALCHEMY_ENGINES"] = {"default": url_de_conexion(url)}
    db.init_app(app)
