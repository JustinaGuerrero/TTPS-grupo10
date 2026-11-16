"""Modelo de la obra social. Lo usan core/pagos y core/finanzas, que no se importan entre sí."""

from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ObraSocial(Base):
    """Copia local de una obra social elegida por un paciente. El listado vive en la API."""

    __tablename__ = "obras_sociales"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str]
