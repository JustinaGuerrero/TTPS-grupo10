"""Modelos de roles y usuarios. Mapean las tablas de la migración inicial."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class Rol(Base):
    """Uno de los 7 roles del LEL. Son datos fijos que carga la migración."""

    __tablename__ = "roles"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)

    def __repr__(self) -> str:
        return f"<Rol {self.codigo}>"


class Usuario(Base):
    """Persona registrada en el sistema con un rol. El email es único sin distinguir mayúsculas."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    email: Mapped[str]
    hash_contrasena: Mapped[str]
    nombre: Mapped[str]
    apellido: Mapped[str]
    rol_codigo: Mapped[str] = mapped_column(sa.ForeignKey("roles.codigo"))
    rol: Mapped[Rol] = relationship()
    activo: Mapped[bool] = mapped_column(server_default=sa.true())
    creado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"

    def tiene_rol(self, *codigos: str) -> bool:
        return self.rol_codigo in codigos

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.email}>"
