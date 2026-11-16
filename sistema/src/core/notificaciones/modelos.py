"""Modelo del aviso: una fila de la lista de pendientes del usuario (docs/modelo-datos.md, 8).

La tabla se llama notificaciones, como el símbolo Notificación del LEL; la guía de agentes llama
Aviso al modelo. Lo crea notificar() de src/core/notificaciones.
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.usuarios.modelos import Usuario


class Aviso(Base):
    """Notificación para un usuario: asunto, mensaje y link a la tarea pendiente."""

    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(sa.ForeignKey("usuarios.id"))
    usuario: Mapped[Usuario] = relationship()
    asunto: Mapped[str]
    mensaje: Mapped[str]
    # Ruta dentro del sistema, por ejemplo /estudios/42.
    link: Mapped[str]
    estudio_id: Mapped[int | None] = mapped_column(sa.ForeignKey("estudios.id"))
    creada_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    # Nulo si el mail no salió.
    mail_enviado_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    leida_en: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    @property
    def leido(self) -> bool:
        return self.leida_en is not None

    def __repr__(self) -> str:
        return f"<Aviso {self.id} para {self.usuario_id}: {self.asunto}>"
