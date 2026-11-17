"""Modelos de la orden del día y sus paradas. Mapean las tablas de la migración de E22.

La lógica (generar la orden del día, E23, y registrar los retiros, E24) es del issue #13.
"""

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.centros.modelos import CentroExtraccion
from src.core.database import Base
from src.core.usuarios.modelos import Transportista


class OrdenDelDia(Base):
    """Lista de centros de extracción de una provincia que el transportista recorre un día hábil.

    Hay una por transportista y día (único de la migración). El orden de las paradas es fijo.
    """

    __tablename__ = "ordenes_del_dia"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    transportista_id: Mapped[int] = mapped_column(sa.ForeignKey("transportistas.usuario_id"))
    transportista: Mapped[Transportista] = relationship()
    fecha: Mapped[date]
    generada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    # Llegada al laboratorio central con todas las muestras (E26).
    llegada_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    paradas: Mapped[list["ParadaOrdenDelDia"]] = relationship(
        back_populates="orden_del_dia", order_by=lambda: ParadaOrdenDelDia.posicion
    )

    def __repr__(self) -> str:
        return f"<OrdenDelDia {self.id} transportista {self.transportista_id} {self.fecha}>"


class ParadaOrdenDelDia(Base):
    """Un centro de la orden del día, en la posición que fijó el módulo de recorridos (E23)."""

    __tablename__ = "paradas_orden_del_dia"

    orden_del_dia_id: Mapped[int] = mapped_column(
        sa.ForeignKey("ordenes_del_dia.id"), primary_key=True
    )
    orden_del_dia: Mapped[OrdenDelDia] = relationship(back_populates="paradas")
    posicion: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    centro_id: Mapped[int] = mapped_column(sa.ForeignKey("centros_extraccion.id"))
    centro: Mapped[CentroExtraccion] = relationship()
    # Cuándo el transportista registró el retiro en ese centro (E24).
    retirado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<ParadaOrdenDelDia {self.orden_del_dia_id}/{self.posicion} centro {self.centro_id}>"
        )
