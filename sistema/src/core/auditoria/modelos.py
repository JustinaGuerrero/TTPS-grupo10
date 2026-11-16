"""Modelo del registro de cambios (docs/modelo-datos.md, tabla auditoria).

Una fila por campo que cambió. La tabla no tiene claves foráneas a las entidades: `entidad`
dice a cuál apunta `entidad_id`. Solo se insertan filas, desde registrar() de servicios.py.
"""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, enum_de_texto
from src.core.usuarios.modelos import Usuario


class Entidad(StrEnum):
    """Lo que se audita (G16). No se registran usuarios, pagos ni cupones."""

    PACIENTE = "paciente"
    ESTUDIO = "estudio"
    SAMPLE_SET = "sample_set"

    @property
    def nombre(self) -> str:
        return {"paciente": "Paciente", "estudio": "Estudio", "sample_set": "Sample set"}[
            self.value
        ]


class Accion(StrEnum):
    ALTA = "alta"
    MODIFICACION = "modificacion"
    BAJA = "baja"
    # Solo aparece en el historial de un estudio y viene de historial_estados: registrar() no
    # la acepta, para que un cambio de estado no quede dos veces.
    ESTADO = "estado"

    @property
    def nombre(self) -> str:
        return {
            "alta": "Alta",
            "modificacion": "Modificación",
            "baja": "Baja",
            "estado": "Cambio de estado",
        }[self.value]


class RegistroDeCambio(Base):
    """Un campo que cambió en un paciente, un estudio o un sample set."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    entidad: Mapped[Entidad] = mapped_column(enum_de_texto(Entidad))
    entidad_id: Mapped[int] = mapped_column(sa.BigInteger)
    accion: Mapped[Accion] = mapped_column(enum_de_texto(Accion))
    campo: Mapped[str]
    valor_anterior: Mapped[str | None]
    valor_nuevo: Mapped[str | None]
    # Nulo cuando el cambio lo hizo el sistema.
    usuario_id: Mapped[int | None] = mapped_column(sa.ForeignKey("usuarios.id"))
    usuario: Mapped[Usuario | None] = relationship()
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    detalle: Mapped[str | None]

    def __repr__(self) -> str:
        return f"<RegistroDeCambio {self.entidad} {self.entidad_id} {self.campo}>"
