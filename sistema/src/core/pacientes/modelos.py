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
from src.core.patologias.modelos import Patologia
from src.core.snomed.modelos import TerminoSnomed
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
    sintomas: Mapped[list["PacienteSintoma"]] = relationship(
        back_populates="paciente", cascade="all, delete-orphan"
    )
    diagnosticos_presuntivos: Mapped[list["DiagnosticoPresuntivo"]] = relationship(
        back_populates="paciente", cascade="all, delete-orphan"
    )
    familiares: Mapped[list["Familiar"]] = relationship(
        back_populates="paciente",
        foreign_keys="Familiar.paciente_id",
        cascade="all, delete-orphan",
    )
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<Paciente {self.id} DNI {self.dni}>"


class PacienteSintoma(Base):
    __tablename__ = "paciente_sintomas"

    paciente_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pacientes.id", ondelete="RESTRICT"), primary_key=True
    )
    paciente: Mapped[Paciente] = relationship(back_populates="sintomas")
    termino_codigo: Mapped[str] = mapped_column(
        sa.ForeignKey("terminos_snomed.codigo", ondelete="RESTRICT"), primary_key=True
    )
    termino: Mapped[TerminoSnomed] = relationship()


class DiagnosticoPresuntivo(Base):
    __tablename__ = "diagnosticos_presuntivos"

    paciente_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pacientes.id", ondelete="RESTRICT"), primary_key=True
    )
    paciente: Mapped[Paciente] = relationship(back_populates="diagnosticos_presuntivos")
    patologia_id: Mapped[int] = mapped_column(
        sa.ForeignKey("patologias.id", ondelete="RESTRICT"), primary_key=True
    )
    patologia: Mapped[Patologia] = relationship()


class Familiar(Base):
    __tablename__ = "familiares"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(sa.ForeignKey("pacientes.id", ondelete="RESTRICT"))
    paciente: Mapped[Paciente] = relationship(
        back_populates="familiares", foreign_keys=[paciente_id]
    )
    parentesco: Mapped[str]
    nombre: Mapped[str]
    dni: Mapped[str | None]
    paciente_vinculado_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("pacientes.id", ondelete="RESTRICT")
    )
    paciente_vinculado: Mapped[Paciente | None] = relationship(foreign_keys=[paciente_vinculado_id])
    vinculado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sintomas: Mapped[list["FamiliarSintoma"]] = relationship(
        back_populates="familiar", cascade="all, delete-orphan"
    )
    patologias: Mapped[list["FamiliarPatologia"]] = relationship(
        back_populates="familiar", cascade="all, delete-orphan"
    )
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class FamiliarSintoma(Base):
    __tablename__ = "familiar_sintomas"

    familiar_id: Mapped[int] = mapped_column(
        sa.ForeignKey("familiares.id", ondelete="RESTRICT"), primary_key=True
    )
    familiar: Mapped[Familiar] = relationship(back_populates="sintomas")
    termino_codigo: Mapped[str] = mapped_column(
        sa.ForeignKey("terminos_snomed.codigo", ondelete="RESTRICT"), primary_key=True
    )
    termino: Mapped[TerminoSnomed] = relationship()


class FamiliarPatologia(Base):
    __tablename__ = "familiar_patologias"

    familiar_id: Mapped[int] = mapped_column(
        sa.ForeignKey("familiares.id", ondelete="RESTRICT"), primary_key=True
    )
    familiar: Mapped[Familiar] = relationship(back_populates="patologias")
    patologia_id: Mapped[int] = mapped_column(
        sa.ForeignKey("patologias.id", ondelete="RESTRICT"), primary_key=True
    )
    patologia: Mapped[Patologia] = relationship()
