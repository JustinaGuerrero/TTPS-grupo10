"""Modelos de la muestra y del mensaje del bot. Mapean las tablas de la migración de E22."""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.centros.modelos import CentroExtraccion
from src.core.database import Base, enum_de_texto
from src.core.estudios.modelos import Estudio
from src.core.logistica.modelos import OrdenDelDia
from src.core.sample_sets.modelos import SampleSet
from src.core.turnos.modelos import TurnoExtraccion


class MotivoInsuficiente(StrEnum):
    """Por qué la muestra no sirve y hay que volver a extraer (E27)."""

    VOLUMEN = "volumen"
    ADN = "adn"


class Muestra(Base):
    """Tubo con la sangre del paciente, tomado en un turno de extracción (E22).

    Un estudio tiene una muestra por extracción; la vigente es la última. El volumen no se
    registra en el sistema (G15).
    """

    __tablename__ = "muestras"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    estudio: Mapped[Estudio] = relationship()
    turno_id: Mapped[int] = mapped_column(sa.ForeignKey("turnos_extraccion.id"), unique=True)
    turno: Mapped[TurnoExtraccion] = relationship()
    # Llegada del mensaje de muestra tomada al bot (E22).
    tomada_en: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    # Orden con la que la retiró el transportista (E24).
    orden_del_dia_id: Mapped[int | None] = mapped_column(sa.ForeignKey("ordenes_del_dia.id"))
    orden_del_dia: Mapped[OrdenDelDia | None] = relationship()
    sample_set_id: Mapped[int | None] = mapped_column(sa.ForeignKey("sample_sets.id"))
    sample_set: Mapped[SampleSet | None] = relationship()
    insuficiente_motivo: Mapped[MotivoInsuficiente | None] = mapped_column(
        enum_de_texto(MotivoInsuficiente)
    )
    insuficiente_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Muestra {self.id} estudio {self.estudio_id} turno {self.turno_id}>"


class MensajeBot(Base):
    """Un update que recibió el bot de mensajería (E22), se haya podido procesar o no.

    `error` nulo con `procesado_en` cargado: el mensaje cambió el estudio a Listo para retirar.
    """

    __tablename__ = "mensajes_bot"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    telegram_update_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True)
    chat_id: Mapped[str | None]
    texto: Mapped[str | None]
    centro_id: Mapped[int | None] = mapped_column(sa.ForeignKey("centros_extraccion.id"))
    centro: Mapped[CentroExtraccion | None] = relationship()
    estudio_id: Mapped[int | None] = mapped_column(sa.ForeignKey("estudios.id"))
    estudio: Mapped[Estudio | None] = relationship()
    recibido_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    procesado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error: Mapped[str | None]

    def __repr__(self) -> str:
        return f"<MensajeBot {self.id} update {self.telegram_update_id} error={self.error!r}>"
