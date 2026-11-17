"""Modelo del turno de extracción. Mapea la tabla turnos_extraccion de la migración de E19."""

from datetime import datetime, timedelta
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.centros.modelos import CentroExtraccion
from src.core.database import Base, enum_de_texto
from src.core.estudios.modelos import Estudio

DURACION_DEL_TURNO = timedelta(minutes=15)


class EstadoTurno(StrEnum):
    """Estado del turno. ausente: el paciente no fue (supuesto O7, lo marca E22)."""

    RESERVADO = "reservado"
    CANCELADO = "cancelado"
    ASISTIDO = "asistido"
    AUSENTE = "ausente"


class TurnoExtraccion(Base):
    """Franja de 15 minutos que reservó el paciente en un centro de extracción (E19).

    Un paciente por franja y un turno vigente por estudio: los controlan dos índices únicos
    de la migración, así que dos reservas simultáneas no pueden quedar las dos guardadas.
    """

    __tablename__ = "turnos_extraccion"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    estudio: Mapped[Estudio] = relationship()
    centro_id: Mapped[int] = mapped_column(sa.ForeignKey("centros_extraccion.id"))
    centro: Mapped[CentroExtraccion] = relationship()
    inicio: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    estado: Mapped[EstadoTurno] = mapped_column(
        enum_de_texto(EstadoTurno), default=EstadoTurno.RESERVADO
    )
    reservado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    cancelado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    recordatorio_enviado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    @property
    def fin(self) -> datetime:
        return self.inicio + DURACION_DEL_TURNO

    def __repr__(self) -> str:
        return f"<TurnoExtraccion {self.id} {self.inicio} {self.estado}>"
