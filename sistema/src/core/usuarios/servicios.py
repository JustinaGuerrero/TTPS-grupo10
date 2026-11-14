"""Reglas de negocio de usuarios: crear usuarios y validar credenciales de acceso (E04).

Las contraseñas se guardan con hash scrypt de Werkzeug; nunca en texto plano.
"""

from functools import cache

import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from src.core.database import db
from src.core.usuarios import roles
from src.core.usuarios.modelos import Medico, Usuario


def hashear_contrasena(contrasena: str) -> str:
    return generate_password_hash(contrasena, method="scrypt")


@cache
def _hash_ficticio() -> str:
    # Se compara contra este hash cuando el mail no existe, para que la respuesta tarde lo
    # mismo y no revele qué mails están registrados.
    return hashear_contrasena("contrasena-ficticia")


def buscar_por_id(usuario_id: int) -> Usuario | None:
    # Trae el rol en la misma consulta: el layout lo muestra en cada página.
    return db.session.get(Usuario, usuario_id, options=[joinedload(Usuario.rol)])


def buscar_por_email(email: str) -> Usuario | None:
    """Busca sin distinguir mayúsculas, igual que el índice usuarios_email_unico."""
    consulta = sa.select(Usuario).where(sa.func.lower(Usuario.email) == email.strip().lower())
    return db.session.scalars(consulta).one_or_none()


def crear_usuario(
    email: str, contrasena: str, nombre: str, apellido: str, rol_codigo: str
) -> Usuario:
    """Crea el usuario con la contraseña hasheada. No hace commit: lo decide quien llama."""
    usuario = Usuario(
        email=email.strip(),
        hash_contrasena=hashear_contrasena(contrasena),
        nombre=nombre,
        apellido=apellido,
        rol_codigo=rol_codigo,
    )
    db.session.add(usuario)
    return usuario


def crear_perfil_medico(usuario: Usuario, matricula: str) -> Medico:
    """Crea el perfil con la matrícula de un médico tratante o gerente médico. No hace commit.

    Lanza ValueError si el usuario tiene otro rol: la base no controla el rol del usuario.
    """
    if not usuario.tiene_rol(roles.MEDICO_TRATANTE, roles.GERENTE_MEDICO):
        raise ValueError("Solo un médico tratante o un gerente médico tiene matrícula.")
    medico = Medico(usuario=usuario, matricula=matricula.strip())
    db.session.add(medico)
    return medico


def validar_credenciales(email: str, contrasena: str) -> Usuario | None:
    """Devuelve el usuario si el mail y la contraseña son correctos y está activo; si no, None.

    No distingue entre mail inexistente, contraseña incorrecta o usuario inactivo: quien
    intenta entrar no tiene que poder averiguar qué mails existen.
    """
    usuario = buscar_por_email(email)
    if usuario is None:
        check_password_hash(_hash_ficticio(), contrasena)
        return None
    if not check_password_hash(usuario.hash_contrasena, contrasena):
        return None
    if not usuario.activo:
        return None
    return usuario
