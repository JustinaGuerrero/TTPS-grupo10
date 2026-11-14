"""Menú del layout según el rol del usuario logueado.

"Inicio" lo muestra el layout a todos. Cada módulo nuevo agrega acá la entrada de su pantalla
principal en los roles que la usan, con el endpoint de su blueprint. Por ejemplo, E03:

    roles.ADMINISTRADOR_GENERAL: [ItemDeMenu("Usuarios", "usuarios.listar")],
"""

from typing import NamedTuple

from flask import Flask, g

from src.core.usuarios import Usuario, roles


class ItemDeMenu(NamedTuple):
    texto: str
    endpoint: str


MENU_POR_ROL: dict[str, list[ItemDeMenu]] = {
    roles.PACIENTE: [],
    roles.MEDICO_TRATANTE: [],
    roles.ADMINISTRATIVO: [],
    roles.BIOINFORMATICO: [],
    roles.TRANSPORTISTA: [],
    roles.GERENTE_MEDICO: [],
    roles.ADMINISTRADOR_GENERAL: [],
}


def items_del_menu(usuario: Usuario | None) -> list[ItemDeMenu]:
    if usuario is None:
        return []
    return MENU_POR_ROL.get(usuario.rol_codigo, [])


def init_app(app: Flask) -> None:
    @app.context_processor
    def inyectar_menu():
        return {"menu": items_del_menu(g.get("usuario"))}
