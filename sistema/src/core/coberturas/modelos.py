"""Modelos de la cobertura de obra social y de la demanda de reautorización (E16 a E18).

Mapean las tablas coberturas y demandas_reautorizacion de la migración de obra social.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, enum_de_texto
from src.core.estudios.modelos import Estudio
from src.core.obras_sociales import ObraSocial


class EstadoCobertura(StrEnum):
    PENDIENTE = "pendiente"
    AUTORIZADA = "autorizada"
    RECHAZADA = "rechazada"


class Cobertura(Base):
    """Pedido de cobertura de un estudio a la obra social del paciente. Uno por estudio."""

    __tablename__ = "coberturas"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"), unique=True)
    estudio: Mapped[Estudio] = relationship()
    obra_social_codigo: Mapped[str] = mapped_column(sa.ForeignKey("obras_sociales.codigo"))
    obra_social: Mapped[ObraSocial] = relationship()
    # Porcentaje que informó la API al elegirla.
    porcentaje: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    estado: Mapped[EstadoCobertura] = mapped_column(
        enum_de_texto(EstadoCobertura), default=EstadoCobertura.PENDIENTE
    )
    importe_cubierto_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2))
    solicitada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    respondida_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Nulo si respondió el módulo de obras sociales (G22) en lugar de un administrativo.
    respondida_por: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    # Id del estudio en el módulo de obras sociales; nulo mientras el alta no salió.
    id_estudio_modulo: Mapped[str | None]

    demandas: Mapped[list["DemandaReautorizacion"]] = relationship(
        back_populates="cobertura", order_by=lambda: DemandaReautorizacion.cargada_en
    )

    @property
    def es_parcial(self) -> bool:
        return self.porcentaje < 100

    def __repr__(self) -> str:
        return f"<Cobertura {self.id} estudio {self.estudio_id} {self.estado}>"


class DemandaReautorizacion(Base):
    """PDF de la resolución judicial favorable que carga el paciente tras un rechazo (E18)."""

    __tablename__ = "demandas_reautorizacion"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    cobertura_id: Mapped[int] = mapped_column(sa.ForeignKey("coberturas.id"))
    cobertura: Mapped[Cobertura] = relationship(back_populates="demandas")
    resolucion_path: Mapped[str]
    cargada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    # Cuándo se subió al módulo de obras sociales; nulo mientras no salió (G22).
    presentada_en_modulo_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<DemandaReautorizacion {self.id} cobertura {self.cobertura_id}>"
