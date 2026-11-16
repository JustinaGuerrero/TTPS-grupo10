"""Modelo de la provincia. Mapea la tabla provincias de la migración de E03."""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Provincia(Base):
    """Una de las 24 jurisdicciones del país. Son datos fijos que carga la migración."""

    __tablename__ = "provincias"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)

    def __repr__(self) -> str:
        return f"<Provincia {self.id} {self.nombre}>"
