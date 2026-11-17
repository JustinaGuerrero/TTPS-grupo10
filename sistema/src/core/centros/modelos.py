"""Modelo del centro de extracción. Mapea la tabla centros_extraccion de la migración de E19."""

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.provincias.modelos import Provincia


class CentroExtraccion(Base):
    """Lugar donde se toma la muestra de sangre (LEL). No opera el sistema: avisa por el bot.

    El horario (lunes a viernes de 9 a 18) es el mismo para todos y no se guarda.
    """

    __tablename__ = "centros_extraccion"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    nombre: Mapped[str]
    direccion: Mapped[str]
    localidad: Mapped[str]
    provincia_id: Mapped[int] = mapped_column(sa.ForeignKey("provincias.id"))
    provincia: Mapped[Provincia] = relationship()
    latitud: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6))
    longitud: Mapped[Decimal] = mapped_column(sa.Numeric(9, 6))
    telefono: Mapped[str]
    # Chat desde el que el centro escribe al bot de mensajería (E22).
    telegram_chat_id: Mapped[str] = mapped_column(unique=True)
    activo: Mapped[bool] = mapped_column(server_default=sa.true())

    @property
    def direccion_completa(self) -> str:
        return f"{self.direccion}, {self.localidad}, {self.provincia.nombre}"

    def __repr__(self) -> str:
        return f"<CentroExtraccion {self.id} {self.nombre}>"
