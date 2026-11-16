"""Modelo del cupón de descuento. Lo comparten pagos y finanzas, que no se importan entre sí.

Las reglas y pantallas del cupón las agrega el issue de cupones.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, enum_de_texto
from src.core.pacientes.modelos import Paciente
from src.core.usuarios.modelos import Medico


class EstadoCupon(StrEnum):
    VIGENTE = "vigente"
    UTILIZADO = "utilizado"


class Cupon(Base):
    """Cupón de descuento (porcentaje, supuesto O15). Lo gestiona el issue de cupones."""

    __tablename__ = "cupones"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(unique=True)
    descuento_porcentaje: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    pdf_path: Mapped[str]
    estado: Mapped[EstadoCupon] = mapped_column(enum_de_texto(EstadoCupon))
    generado_por: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"))
    generado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    medico_tratante_id: Mapped[int | None] = mapped_column(sa.ForeignKey("medicos.usuario_id"))
    asignado_a_medico_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    medico_tratante: Mapped[Medico | None] = relationship()
    paciente_id: Mapped[int | None] = mapped_column(sa.ForeignKey("pacientes.id"))
    paciente: Mapped[Paciente | None] = relationship()
    asignado_a_paciente_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    utilizado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
