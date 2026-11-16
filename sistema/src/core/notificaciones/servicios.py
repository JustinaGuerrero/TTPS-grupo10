"""Reglas de las notificaciones (decisión S11, E39).

notificar() guarda el aviso en la lista de pendientes del usuario y le manda el mail. Ninguna
función hace commit: lo decide quien llama, como en src/core/usuarios.
"""

from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from src.core.database import db
from src.core.estudios.modelos import Estudio
from src.core.notificaciones.modelos import Aviso
from src.core.usuarios.modelos import Usuario
from src.integraciones import mail

AVISOS_POR_PAGINA = 20


class PaginaDeAvisos(NamedTuple):
    avisos: list[Aviso]
    pagina: int
    por_pagina: int
    total: int

    @property
    def hay_anterior(self) -> bool:
        return self.pagina > 1

    @property
    def hay_siguiente(self) -> bool:
        return self.pagina * self.por_pagina < self.total


def notificar(
    usuario: Usuario,
    asunto: str,
    mensaje: str,
    link: str,
    estudio: Estudio | None = None,
) -> Aviso:
    """Publica un aviso en la lista de pendientes de `usuario` y le manda el mismo aviso por mail.

    `link` es la ruta de la tarea pendiente dentro del sistema (por ejemplo, la de url_for()); el
    mail lleva el link absoluto. Si el mail no sale, el aviso se guarda igual con
    mail_enviado_en nulo: una falla del correo no rompe el escenario que notifica.

    El mail sale en el momento, antes del commit de quien llama: si después se hace rollback,
    el mail ya salió aunque el aviso no quede guardado.

    Lanza ValueError si falta el asunto o el mensaje, o si `link` no es una ruta del sistema.
    """
    asunto = (asunto or "").strip()
    mensaje = (mensaje or "").strip()
    link = (link or "").strip()
    if not asunto or not mensaje:
        raise ValueError("La notificación necesita asunto y mensaje.")
    if not link.startswith("/") or link.startswith("//"):
        raise ValueError(f"El link de la notificación tiene que ser una ruta del sistema: {link!r}")

    aviso = Aviso(
        usuario=usuario,
        asunto=asunto,
        mensaje=mensaje,
        link=link,
        estudio_id=estudio.id if estudio is not None else None,
    )
    db.session.add(aviso)
    db.session.flush()

    if mail.enviar(usuario.email, asunto, _cuerpo_del_mail(usuario, mensaje, link)):
        aviso.mail_enviado_en = datetime.now(UTC)
    return aviso


def avisos_de(usuario: Usuario, pagina: int = 1) -> PaginaDeAvisos:
    """Avisos del usuario, los más nuevos primero, de a AVISOS_POR_PAGINA."""
    pagina = max(pagina, 1)
    filtro = Aviso.usuario_id == usuario.id
    total = db.session.scalar(sa.select(sa.func.count()).select_from(Aviso).where(filtro))
    consulta = (
        sa.select(Aviso)
        .where(filtro)
        .order_by(Aviso.creada_en.desc(), Aviso.id.desc())
        .limit(AVISOS_POR_PAGINA)
        .offset((pagina - 1) * AVISOS_POR_PAGINA)
    )
    avisos = list(db.session.scalars(consulta))
    return PaginaDeAvisos(avisos, pagina, AVISOS_POR_PAGINA, total or 0)


def contar_sin_leer(usuario: Usuario) -> int:
    consulta = (
        sa.select(sa.func.count())
        .select_from(Aviso)
        .where(Aviso.usuario_id == usuario.id, Aviso.leida_en.is_(None))
    )
    return db.session.scalar(consulta) or 0


def marcar_leido(aviso_id: int, usuario: Usuario) -> Aviso | None:
    """Marca leído el aviso y lo devuelve. Devuelve None si no existe o es de otro usuario."""
    aviso = db.session.get(Aviso, aviso_id)
    if aviso is None or aviso.usuario_id != usuario.id:
        return None
    if aviso.leida_en is None:
        aviso.leida_en = datetime.now(UTC)
    return aviso


def _cuerpo_del_mail(usuario: Usuario, mensaje: str, link: str) -> str:
    return (
        f"Hola, {usuario.nombre}:\n\n"
        f"{mensaje}\n\n"
        f"Ver en el sistema: {mail.url_absoluta(link)}\n\n"
        "--\n"
        "Laboratorio central · Sistema de exoma clínico\n"
        "Este mail se envió automáticamente: no lo respondas.\n"
    )
