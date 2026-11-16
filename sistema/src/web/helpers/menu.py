"""Menú del layout según el rol del usuario logueado.

"Inicio" y "Mis avisos" los muestra el layout a todos. Cada módulo nuevo agrega acá la entrada de su pantalla
principal en los roles que la usan, con el endpoint de su blueprint, como "Usuarios" (E03). La entrada
queda marcada en todas las pantallas de ese blueprint.
"""

from typing import NamedTuple

from flask import Flask, current_app, g
from sqlalchemy.exc import SQLAlchemyError

from src.core.notificaciones import contar_sin_leer
from src.core.usuarios import Usuario, roles


class ItemDeMenu(NamedTuple):
    texto: str
    endpoint: str


MENU_POR_ROL: dict[str, list[ItemDeMenu]] = {
    roles.PACIENTE: [ItemDeMenu("Mi presupuesto", "pagos.mi_presupuesto")],
    roles.MEDICO_TRATANTE: [],
    roles.ADMINISTRATIVO: [ItemDeMenu("Presupuestos", "pagos.pendientes")],
    roles.BIOINFORMATICO: [],
    roles.TRANSPORTISTA: [],
    roles.GERENTE_MEDICO: [ItemDeMenu("Patologías", "patologias.listar")],
    roles.ADMINISTRADOR_GENERAL: [ItemDeMenu("Usuarios", "usuarios.listar")],
}


def items_del_menu(usuario: Usuario | None) -> list[ItemDeMenu]:
    if usuario is None:
        return []
    return MENU_POR_ROL.get(usuario.rol_codigo, [])


def init_app(app: Flask) -> None:
    @app.context_processor
    def inyectar_menu():
        usuario = g.get("usuario")
        return {"menu": items_del_menu(usuario), "avisos_sin_leer": _avisos_sin_leer(usuario)}


def _avisos_sin_leer(usuario: Usuario | None) -> int:
    """Cantidad para el badge de "Mis avisos", que el layout muestra a todos (E39).

    Si la base falla (por ejemplo, al mostrar la página de error 500 de una consulta que falló),
    no muestra el número en vez de romper la página de error.
    """
    if usuario is None:
        return 0
    try:
        return contar_sin_leer(usuario)
    except SQLAlchemyError:
        current_app.logger.exception("No se pudo contar los avisos sin leer")
        return 0
