"""Modelos de presupuesto, pago, cupón y obra social (docs/modelo-datos.md, sección 5).

Cupón y obra social están acá porque las referencian pagos y asientos; sus reglas y pantallas
las agregan los issues de cupones y de obra social.
"""

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.estudios.modelos import Estudio


class Presupuesto(Base):
    """Costo fijo del estudio: un presupuesto por estudio."""

    __tablename__ = "presupuestos"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"), unique=True)
    estudio: Mapped[Estudio] = relationship()
    cantidad_genes: Mapped[int] = mapped_column(sa.SmallInteger)
    total_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2))
    emitido_por: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"))
    emitido_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<Presupuesto estudio {self.estudio_id} {self.total_usd} USD>"
