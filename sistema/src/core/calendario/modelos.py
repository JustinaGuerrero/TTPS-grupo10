"""Modelo del feriado. Mapea la tabla feriados de la migración de E19."""

from datetime import date

from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Feriado(Base):
    """Día sin turnos, sin orden del día y sin retiros de FedEx. Son datos fijos de la migración."""

    __tablename__ = "feriados"

    fecha: Mapped[date] = mapped_column(primary_key=True)
    descripcion: Mapped[str]

    def __repr__(self) -> str:
        return f"<Feriado {self.fecha} {self.descripcion}>"
