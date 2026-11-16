"""Grilla de usuarios del administrador general (E03): búsqueda, filtro por rol, orden y páginas.

Todo se resuelve en la base. Los parámetros llegan de la URL y BusquedaDeUsuarios los normaliza:
un valor desconocido (un rol que no existe, una columna que no se puede ordenar) se reemplaza
por el valor por defecto en vez de dar error, porque la URL la puede escribir cualquiera.

    busqueda = BusquedaDeUsuarios.desde(request.args)
    pagina = buscar_usuarios(busqueda)
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace

import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from src.core.paginacion import Pagina, paginar
from src.core.usuarios import roles
from src.core.usuarios.modelos import Rol, Usuario

USUARIOS_POR_PAGINA = 20
LARGO_MAXIMO_DEL_TEXTO = 100

# Columnas por las que se puede ordenar la grilla: el nombre del parámetro `orden` y las
# expresiones de la base. Los textos se ordenan sin distinguir mayúsculas.
COLUMNAS_DE_ORDEN = {
    "nombre": (sa.func.lower(Usuario.apellido), sa.func.lower(Usuario.nombre)),
    "email": (sa.func.lower(Usuario.email),),
    "rol": (Rol.nombre,),
    "alta": (Usuario.creado_en,),
}
ASCENDENTE = "asc"
DESCENDENTE = "desc"


@dataclass(frozen=True)
class BusquedaDeUsuarios:
    """Lo que pidió el administrador en la grilla. Por defecto, los últimos dados de alta primero."""

    # Palabras a buscar en el nombre, el apellido o el mail.
    texto: str = ""
    # Código del rol, o vacío para todos.
    rol: str = ""
    orden: str = "alta"
    direccion: str = DESCENDENTE
    pagina: int = 1

    @classmethod
    def desde(cls, parametros: Mapping[str, str]) -> "BusquedaDeUsuarios":
        """Toma los parámetros de la URL (request.args) y descarta los que no son válidos."""
        texto = " ".join((parametros.get("texto") or "").split())[:LARGO_MAXIMO_DEL_TEXTO]
        rol = parametros.get("rol") or ""
        orden = parametros.get("orden") or ""
        direccion = parametros.get("direccion") or ""
        pagina = parametros.get("pagina") or ""
        por_defecto = cls()
        return cls(
            texto=texto,
            rol=rol if rol in roles.TODOS else por_defecto.rol,
            orden=orden if orden in COLUMNAS_DE_ORDEN else por_defecto.orden,
            direccion=direccion
            if direccion in (ASCENDENTE, DESCENDENTE)
            else por_defecto.direccion,
            pagina=int(pagina) if pagina.isascii() and pagina.isdigit() and len(pagina) < 7 else 1,
        )

    @property
    def descendente(self) -> bool:
        return self.direccion == DESCENDENTE

    @property
    def filtrada(self) -> bool:
        return bool(self.texto or self.rol)

    def parametros(self, **cambios) -> dict[str, str | int]:
        """Parámetros de URL para esta búsqueda con `cambios`, sin los que valen lo de por defecto.

        Vuelve a la página 1 salvo que `cambios` diga otra: cambiar el orden o un filtro
        cambia qué hay en cada página.
        """
        busqueda = replace(self, **{"pagina": 1, **cambios})
        por_defecto = asdict(BusquedaDeUsuarios())
        return {
            clave: valor for clave, valor in asdict(busqueda).items() if valor != por_defecto[clave]
        }

    def al_ordenar_por(self, columna: str) -> dict[str, str | int]:
        """Parámetros del link de una cabecera: invierte la dirección si ya se ordena por ella."""
        if columna == self.orden:
            direccion = ASCENDENTE if self.descendente else DESCENDENTE
        else:
            # La fecha de alta empieza por los más nuevos; el resto, de la A a la Z.
            direccion = DESCENDENTE if columna == "alta" else ASCENDENTE
        return self.parametros(orden=columna, direccion=direccion)


def buscar_usuarios(
    busqueda: BusquedaDeUsuarios, por_pagina: int = USUARIOS_POR_PAGINA
) -> Pagina[Usuario]:
    """Usuarios que cumplen la búsqueda, ordenados y de a `por_pagina`.

    Cada palabra del texto tiene que aparecer en el nombre, el apellido o el mail, sin
    distinguir mayúsculas: "ana gom" encuentra a Ana Gómez. %, _ y \\ se buscan tal cual.
    """
    consulta = sa.select(Usuario).join(Usuario.rol).options(selectinload(Usuario.rol))
    for palabra in busqueda.texto.split():
        consulta = consulta.where(
            sa.or_(
                Usuario.nombre.icontains(palabra, autoescape=True),
                Usuario.apellido.icontains(palabra, autoescape=True),
                Usuario.email.icontains(palabra, autoescape=True),
            )
        )
    if busqueda.rol:
        consulta = consulta.where(Usuario.rol_codigo == busqueda.rol)

    # El id al final desempata: sin él, dos usuarios iguales en la columna podrían aparecer
    # en dos páginas o en ninguna.
    columnas = (*COLUMNAS_DE_ORDEN[busqueda.orden], Usuario.id)
    consulta = consulta.order_by(
        *(columna.desc() if busqueda.descendente else columna.asc() for columna in columnas)
    )
    return paginar(consulta, busqueda.pagina, por_pagina)
