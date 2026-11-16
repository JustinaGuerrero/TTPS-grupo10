"""Aplicar supabase/migrations a una base local: la de los tests y la de `flask migrar-local`.

Borra el esquema public y aplica las migraciones en el orden de `npx supabase db push`. Como
borra todo, nunca se usa con la base de Supabase: motivo_para_no_borrar() dice por qué no.
En Supabase las migraciones las aplica una persona con `npx supabase db push`.
"""

from pathlib import Path

import sqlalchemy as sa

from src.core.database import url_de_conexion

CARPETA_DE_MIGRACIONES = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


class MigracionFallida(Exception):
    def __init__(self, archivo: Path, error: Exception) -> None:
        super().__init__(f"Falla la migración {archivo.name}: {error}")
        self.archivo = archivo


def motivo_para_no_borrar(url: str, url_compartida: str | None) -> str | None:
    """Por qué no se puede borrar el esquema de `url`, o None si es una base local distinta.

    Se niega si el host es de Supabase o si es la misma base que `url_compartida` (DATABASE_URL).
    """
    destino = sa.make_url(url_de_conexion(url))
    if "supabase" in (destino.host or "").lower():
        return "la URL es de Supabase"
    if url_compartida and _misma_base(sa.make_url(url_de_conexion(url_compartida)), destino):
        return "es la misma base que DATABASE_URL, la compartida"
    return None


def _misma_base(una: sa.URL, otra: sa.URL) -> bool:
    """Mismo servidor, puerto y base, aunque cambien el driver, la clave o un :5432 explícito."""

    def clave(url: sa.URL) -> tuple:
        return ((url.host or "localhost").lower(), url.port or 5432, url.database)

    return clave(una) == clave(otra)


def crear_base_si_falta(url: str) -> bool:
    """Crea la base de `url` (por ejemplo exoma_local) si no existe. Devuelve True si la creó.

    Lanza sqlalchemy.exc.OperationalError si no se puede conectar al servidor.
    """
    destino = sa.make_url(url_de_conexion(url))
    motor = sa.create_engine(destino.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with motor.connect() as conexion:
            existe = conexion.scalar(
                sa.text("select 1 from pg_database where datname = :nombre"),
                {"nombre": destino.database},
            )
            if existe:
                return False
            nombre = conexion.dialect.identifier_preparer.quote(destino.database)
            conexion.exec_driver_sql(f"create database {nombre}")
            return True
    finally:
        motor.dispose()


def aplicar_migraciones(url: str, carpeta: Path = CARPETA_DE_MIGRACIONES) -> list[str]:
    """Deja el esquema public vacío y aplica las migraciones en orden, en una sola transacción.

    Devuelve los nombres de los archivos aplicados. Lanza MigracionFallida si una falla; en ese
    caso no queda nada a medias.
    """
    motor = sa.create_engine(url_de_conexion(url))
    aplicadas = []
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql("drop schema if exists public cascade")
            conexion.exec_driver_sql("create schema public")
            for archivo in sorted(carpeta.glob("*.sql")):
                try:
                    # Sin parámetros, psycopg acepta varios statements y no interpreta los %.
                    conexion.exec_driver_sql(
                        archivo.read_text(encoding="utf-8"),
                        execution_options={"no_parameters": True},
                    )
                except sa.exc.DBAPIError as error:
                    raise MigracionFallida(archivo, error.orig) from error
                aplicadas.append(archivo.name)
    finally:
        motor.dispose()
    return aplicadas
