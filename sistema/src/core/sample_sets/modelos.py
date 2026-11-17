"""Modelo del sample set. Mapea la tabla sample_sets de la migración de E22.

La lógica (armar, cerrar, autorizar, programar el retiro y despachar: E28 a E31) es del issue #14.
"""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, enum_de_texto


class EstadoSampleSet(StrEnum):
    """Estados del sample set del LEL. Siempre en este orden; cada uno tiene su fecha de inicio."""

    EN_ARMADO = "en_armado"
    CERRADO = "cerrado"
    PENDIENTE_RETIRO = "pendiente_retiro"
    RETIRO_PROGRAMADO = "retiro_programado"
    DESPACHADO = "despachado"


class SampleSet(Base):
    """Lote de hasta 10 muestras que viaja a Corea. Hay un solo sample set en armado a la vez.

    En armado empieza en creado_en, Cerrado en cerrado_en, Pendiente de retiro en autorizado_en,
    Retiro programado en retiro_programado_en y Despachado en despachado_en.
    """

    __tablename__ = "sample_sets"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estado: Mapped[EstadoSampleSet] = mapped_column(
        enum_de_texto(EstadoSampleSet), default=EstadoSampleSet.EN_ARMADO
    )
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    cerrado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Excel con los pacientes del sample set (E29).
    ccb_path: Mapped[str | None]
    # PDF de autorización del Ministerio de Salud.
    autorizacion_path: Mapped[str | None]
    autorizado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    # Día y hora hábiles del retiro de FedEx (E30).
    retiro_programado_para: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retiro_programado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retiro_programado_por: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    # Parte secreta de la URL que invoca FedEx (E31).
    token_retiro: Mapped[str | None] = mapped_column(unique=True)
    despachado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<SampleSet {self.id} {self.estado}>"
