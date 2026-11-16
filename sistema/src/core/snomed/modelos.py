"""Copia local de los términos SNOMED que alguien eligió (E07). Mapea terminos_snomed."""

from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class TerminoSnomed(Base):
    """El catálogo completo vive en el módulo SNOMED: acá solo están los términos elegidos."""

    __tablename__ = "terminos_snomed"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    termino: Mapped[str]
    # sintoma o especialidad
    tipo: Mapped[str]

    def __repr__(self) -> str:
        return f"<TerminoSnomed {self.codigo} {self.termino}>"
