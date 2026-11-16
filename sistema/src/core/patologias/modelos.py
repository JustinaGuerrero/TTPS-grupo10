"""Modelos de patologías y sus síntomas. Mapean las tablas de la migración patologias_snomed."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.patologias.validacion import PatologiaSospechada
from src.core.snomed.modelos import TerminoSnomed
from src.core.usuarios.modelos import Usuario


class Patologia(Base):
    """Patología lisosomal con la que trabaja el laboratorio (E36).

    Los genes no se guardan: los devuelve Apigen a partir de `codigo_apigen`. No hay bajas:
    una patología que deja de usarse se desactiva.
    """

    __tablename__ = "patologias"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    codigo_apigen: Mapped[str] = mapped_column(unique=True)
    nombre: Mapped[str] = mapped_column(unique=True)
    activa: Mapped[bool] = mapped_column(server_default=sa.true())
    creado_por: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"))
    creador: Mapped[Usuario] = relationship(foreign_keys=[creado_por])
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )
    sintomas: Mapped[list["PatologiaSintoma"]] = relationship(
        back_populates="patologia", cascade="all, delete-orphan"
    )

    @property
    def cardinal(self) -> str | None:
        """Código SNOMED del síntoma cardinal."""
        return next((s.termino_codigo for s in self.sintomas if s.es_cardinal), None)

    @property
    def secundarios(self) -> frozenset[str]:
        """Códigos SNOMED de los síntomas secundarios."""
        return frozenset(s.termino_codigo for s in self.sintomas if not s.es_cardinal)

    def como_sospechada(self) -> PatologiaSospechada:
        """La patología como la espera la regla de E08 (validar_diagnostico_presuntivo)."""
        if self.cardinal is None:
            raise ValueError(f"La patología {self.nombre} no tiene síntoma cardinal.")
        return PatologiaSospechada(self.codigo_apigen, self.nombre, self.cardinal, self.secundarios)

    def __repr__(self) -> str:
        return f"<Patologia {self.id} {self.codigo_apigen}>"


class PatologiaSintoma(Base):
    """Síntoma de una patología: un solo cardinal (índice único) y los demás secundarios."""

    __tablename__ = "patologia_sintomas"

    patologia_id: Mapped[int] = mapped_column(sa.ForeignKey("patologias.id"), primary_key=True)
    patologia: Mapped[Patologia] = relationship(back_populates="sintomas")
    termino_codigo: Mapped[str] = mapped_column(
        sa.ForeignKey("terminos_snomed.codigo"), primary_key=True
    )
    termino: Mapped[TerminoSnomed] = relationship()
    es_cardinal: Mapped[bool] = mapped_column(server_default=sa.false())

    def __repr__(self) -> str:
        return f"<PatologiaSintoma {self.patologia_id} {self.termino_codigo}>"
