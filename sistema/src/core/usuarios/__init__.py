"""Usuarios y roles. Es el módulo de referencia (E03): un módulo nuevo copia esta estructura."""

from src.core.usuarios import roles
from src.core.usuarios.modelos import Medico, Rol, Usuario
from src.core.usuarios.servicios import (
    buscar_por_email,
    buscar_por_id,
    crear_perfil_medico,
    crear_usuario,
    hashear_contrasena,
    validar_credenciales,
)

__all__ = [
    "Medico",
    "Rol",
    "Usuario",
    "buscar_por_email",
    "buscar_por_id",
    "crear_perfil_medico",
    "crear_usuario",
    "hashear_contrasena",
    "roles",
    "validar_credenciales",
]
