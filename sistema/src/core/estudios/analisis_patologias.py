"""Patologías que evalúa un análisis (tabla analisis_patologias, E10 y E12).

Vive aparte de modelos.py para no tocar los modelos del estudio, y no importa a core/pacientes.
"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.patologias.modelos import Patologia


class AnalisisPatologia(Base):
    """Una patología que evalúa un análisis. `resultado` queda nulo hasta finalizar (E35)."""

    __tablename__ = "analisis_patologias"

    analisis_id: Mapped[int] = mapped_column(
        sa.ForeignKey("analisis.id", ondelete="RESTRICT"), primary_key=True
    )
    patologia_id: Mapped[int] = mapped_column(
        sa.ForeignKey("patologias.id", ondelete="RESTRICT"), primary_key=True
    )
    patologia: Mapped[Patologia] = relationship()
    resultado: Mapped[str | None]

    def __repr__(self) -> str:
        return f"<AnalisisPatologia {self.analisis_id} {self.patologia_id}>"
