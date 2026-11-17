"""Consultas de los centros de extracción (E19: el mapa; E22 y E23: el bot y la orden del día)."""

import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from src.core.centros.modelos import CentroExtraccion
from src.core.database import db


def listar_centros_activos() -> list[CentroExtraccion]:
    """Los centros activos con su provincia, ordenados por provincia, localidad y nombre."""
    consulta = (
        sa.select(CentroExtraccion)
        .options(joinedload(CentroExtraccion.provincia))
        .where(CentroExtraccion.activo)
        .order_by(
            CentroExtraccion.provincia_id, CentroExtraccion.localidad, CentroExtraccion.nombre
        )
    )
    return list(db.session.scalars(consulta))


def buscar_centro(centro_id: int) -> CentroExtraccion | None:
    return db.session.get(CentroExtraccion, centro_id)


def buscar_por_chat(telegram_chat_id: str) -> CentroExtraccion | None:
    """El centro que escribe desde ese chat de Telegram, o None (E22)."""
    consulta = sa.select(CentroExtraccion).where(
        CentroExtraccion.telegram_chat_id == str(telegram_chat_id)
    )
    return db.session.scalar(consulta)
