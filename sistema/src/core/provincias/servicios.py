"""Consultas de provincias."""

import sqlalchemy as sa

from src.core.database import db
from src.core.provincias.modelos import Provincia


def listar_provincias() -> list[Provincia]:
    """Todas las provincias, por nombre."""
    return list(db.session.scalars(sa.select(Provincia).order_by(Provincia.nombre)))


def buscar_provincia(provincia_id: int) -> Provincia | None:
    return db.session.get(Provincia, provincia_id)
