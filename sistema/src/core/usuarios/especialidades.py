"""Modelo de las especialidades SNOMED de cada médico (E01)."""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class MedicoEspecialidad(Base):
    """Relación entre un médico y una especialidad del catálogo SNOMED."""

    __tablename__ = "medico_especialidades"

    medico_id: Mapped[int] = mapped_column(
        sa.ForeignKey("medicos.usuario_id", ondelete="RESTRICT"), primary_key=True
    )
    termino_codigo: Mapped[str] = mapped_column(
        sa.ForeignKey("terminos_snomed.codigo", ondelete="RESTRICT"), primary_key=True
    )

    def __repr__(self) -> str:
        return f"<MedicoEspecialidad {self.medico_id} {self.termino_codigo}>"
