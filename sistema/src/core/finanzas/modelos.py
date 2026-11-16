"""Modelos del pago y del asiento financiero (docs/modelo-datos.md, sección 5).

El pago está acá y no en core/pagos para que el asiento, que lo referencia, no dependa de
core/pagos. Los asientos solo se insertan.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.core.cupones import Cupon  # noqa: F401  (tabla cupones, referenciada por pagos)
from src.core.database import Base, enum_de_texto
from src.core.estudios.modelos import Estudio  # noqa: F401  (tabla estudios, referenciada)
from src.core.obras_sociales import ObraSocial  # noqa: F401  (tabla referenciada)


class TipoPago(StrEnum):
    PARTICULAR = "particular"
    OBRA_SOCIAL = "obra_social"


class Pago(Base):
    """Pago de un estudio: uno de cada tipo, sin cuotas."""

    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    tipo: Mapped[TipoPago] = mapped_column(enum_de_texto(TipoPago))
    importe_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2))
    cupon_id: Mapped[int | None] = mapped_column(sa.ForeignKey("cupones.id"), unique=True)
    descuento_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), server_default="0")
    pagado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<Pago {self.tipo} {self.importe_usd} USD estudio {self.estudio_id}>"


class TipoAsiento(StrEnum):
    PRESUPUESTO_EMITIDO = "presupuesto_emitido"
    PAGO_PARTICULAR = "pago_particular"
    COBERTURA_OBRA_SOCIAL = "cobertura_obra_social"
    DESCUENTO_CUPON = "descuento_cupon"
    COBRO_OBRA_SOCIAL = "cobro_obra_social"


class AsientoFinanciero(Base):
    """Una operación económica. El importe es siempre positivo; el tipo indica el sentido."""

    __tablename__ = "asientos_financieros"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    tipo: Mapped[TipoAsiento] = mapped_column(enum_de_texto(TipoAsiento))
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    pago_id: Mapped[int | None] = mapped_column(sa.ForeignKey("pagos.id"))
    obra_social_codigo: Mapped[str | None] = mapped_column(sa.ForeignKey("obras_sociales.codigo"))
    importe_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2))
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<AsientoFinanciero {self.tipo} {self.importe_usd} estudio {self.estudio_id}>"
