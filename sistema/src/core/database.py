"""Conexión a la base con Flask-SQLAlchemy-Lite.

Lite (no es Flask-SQLAlchemy) solo maneja engines y sesiones: no trae db.Model ni
create_all. Los modelos heredan de Base, que es SQLAlchemy puro, y el esquema sale
de las migraciones de supabase/migrations.

Uso en core: `db.session` es la sesión del contexto de app actual y se cierra sola
al terminar el request.
"""

from enum import StrEnum

import sqlalchemy as sa
from flask import Flask
from flask_sqlalchemy_lite import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""


def enum_de_texto(enum: type[StrEnum]) -> sa.Enum:
    """Tipo de columna para un estado o valor cerrado guardado como text (ver modelo-datos.md).

    Guarda el valor del miembro ('creado'), no su nombre ('CREADO'), y devuelve el miembro del
    enum. No crea un check propio: los valores válidos los controla el check de la migración.
    """
    return sa.Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda miembros: [miembro.value for miembro in miembros],
    )


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
