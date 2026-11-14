"""Modelo mínimo del paciente con los datos de E06. Mapea la tabla pacientes.

Nombre, apellido, mail y teléfono están en el usuario del paciente. Diagnóstico presuntivo,
síntomas y familiares se agregan con sus escenarios (E06, E08, E09), cuando existan las
patologías (E36) y los términos SNOMED.
"""

from datetime import date, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, enum_de_texto
from src.core.usuarios.modelos import Medico, Usuario


class TipoSospecha(StrEnum):
    """Origen de la sospecha (LEL): clínica, por síntomas, o familiar, por un pariente enfermo."""

    CLINICA = "clinica"
    FAMILIAR = "familiar"


class Paciente(Base):
    """Persona a la que se le hace el estudio. Tiene un solo estudio (observación O20)."""

    __tablename__ = "pacientes"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"), unique=True)
    usuario: Mapped[Usuario] = relationship()
    dni: Mapped[str] = mapped_column(unique=True)
    fecha_nacimiento: Mapped[date]
    tipo_sospecha: Mapped[TipoSospecha] = mapped_column(enum_de_texto(TipoSospecha))
    resumen_historia_clinica: Mapped[str]
    resumen_audio_path: Mapped[str | None]
    familiograma_path: Mapped[str | None]
    medico_tratante_id: Mapped[int] = mapped_column(sa.ForeignKey("medicos.usuario_id"))
    medico_tratante: Mapped[Medico] = relationship()
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<Paciente {self.id} DNI {self.dni}>"
