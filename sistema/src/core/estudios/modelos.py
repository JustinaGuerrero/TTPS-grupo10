"""Modelos del estudio: el estudio, su historial de estados y sus análisis con los genes pedidos.

Mapean las tablas de la migración estudios (docs/modelo-datos.md, sección 4). El estado no se
asigna a mano: lo cambia cambiar_estado() de src/core/estudios.
"""

from datetime import date, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, enum_de_texto
from src.core.estudios.estados import EstadoEstudio
from src.core.pacientes.modelos import Paciente
from src.core.usuarios.modelos import Medico, Usuario


class TipoAnalisis(StrEnum):
    INICIAL = "inicial"
    REANALISIS = "reanalisis"


class Estudio(Base):
    """Exoma clínico de un paciente. Siempre está en uno de los 16 estados de EstadoEstudio."""

    __tablename__ = "estudios"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    # Lo calcula la base con el año del alta y el id: EX-2026-00042.
    codigo: Mapped[str] = mapped_column(server_default=sa.FetchedValue())
    paciente_id: Mapped[int] = mapped_column(sa.ForeignKey("pacientes.id"), unique=True)
    paciente: Mapped[Paciente] = relationship()
    medico_tratante_id: Mapped[int] = mapped_column(sa.ForeignKey("medicos.usuario_id"))
    medico_tratante: Mapped[Medico] = relationship()
    estado: Mapped[EstadoEstudio] = mapped_column(enum_de_texto(EstadoEstudio))
    pompe_urgente: Mapped[bool] = mapped_column(server_default=sa.false())
    datos_crudos_path: Mapped[str | None]
    datos_crudos_cargados_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    datos_crudos_cargados_por: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    # now() da la misma hora a todo lo que pasa en una transacción: el id desempata.
    historial: Mapped[list["HistorialEstado"]] = relationship(
        back_populates="estudio",
        order_by=lambda: (HistorialEstado.creado_en, HistorialEstado.id),
    )
    analisis: Mapped[list["Analisis"]] = relationship(
        back_populates="estudio", order_by=lambda: Analisis.numero
    )

    @property
    def analisis_actual(self) -> "Analisis":
        """El último análisis: el inicial o el reanálisis más reciente."""
        return self.analisis[-1]

    def __repr__(self) -> str:
        return f"<Estudio {self.id} {self.estado}>"


class HistorialEstado(Base):
    """Un cambio de estado del estudio, con fecha y usuario (decisión S9)."""

    __tablename__ = "historial_estados"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    estudio: Mapped[Estudio] = relationship(back_populates="historial")
    # Nulo solo en la primera fila, la del alta en Creado.
    estado_anterior: Mapped[EstadoEstudio | None] = mapped_column(enum_de_texto(EstadoEstudio))
    estado_nuevo: Mapped[EstadoEstudio] = mapped_column(enum_de_texto(EstadoEstudio))
    # Nulo cuando el cambio lo dispara el sistema (bot de mensajería, FedEx, tareas programadas).
    usuario_id: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    usuario: Mapped[Usuario | None] = relationship()
    motivo: Mapped[str | None]
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"<HistorialEstado {self.estudio_id} {self.estado_anterior} → {self.estado_nuevo}>"


class Analisis(Base):
    """Una vuelta de análisis del exoma: la inicial (numero 1) o un reanálisis (E12)."""

    __tablename__ = "analisis"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    estudio_id: Mapped[int] = mapped_column(sa.ForeignKey("estudios.id"))
    estudio: Mapped[Estudio] = relationship(back_populates="analisis")
    numero: Mapped[int] = mapped_column(sa.SmallInteger)
    tipo: Mapped[TipoAnalisis] = mapped_column(enum_de_texto(TipoAnalisis))
    evalua_hallazgos_secundarios: Mapped[bool]
    solicitado_por: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"))
    solicitado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    disponible_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    bioinformatico_id: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    tomado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    finalizado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    resultado: Mapped[str | None]
    resultado_path: Mapped[str | None]
    fecha_reevaluacion: Mapped[date | None]

    genes: Mapped[list["AnalisisGen"]] = relationship(
        back_populates="analisis", order_by=lambda: AnalisisGen.gen_simbolo
    )

    def __repr__(self) -> str:
        return f"<Analisis {self.estudio_id} n.° {self.numero}>"


class AnalisisGen(Base):
    """Gen que se evalúa en un análisis. Los de hallazgos secundarios no se guardan (Apigen)."""

    __tablename__ = "analisis_genes"

    analisis_id: Mapped[int] = mapped_column(sa.ForeignKey("analisis.id"), primary_key=True)
    analisis: Mapped[Analisis] = relationship(back_populates="genes")
    gen_simbolo: Mapped[str] = mapped_column(primary_key=True)
    # True si lo agregó el médico tratante y Apigen no lo devolvió para ninguna patología.
    agregado_a_mano: Mapped[bool]

    def __repr__(self) -> str:
        return f"<AnalisisGen {self.analisis_id} {self.gen_simbolo}>"
