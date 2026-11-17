"""E11 Consultar historial de estudios: consultas de solo lectura sobre los estudios.

Ninguna función cambia datos ni hace commit. El estado y el historial los escribe solo
src/core/estudios; acá solo se leen.

Quién ve qué:
- El paciente ve solo su estudio (hay uno por paciente, observación O20).
- El médico tratante ve solo los estudios que tiene a cargo.
- Los demás roles no ven ninguno.

Un estudio o un análisis que el usuario no puede ver se trata igual que uno inexistente (None),
para que el controlador responda 404 y no revele que existe.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace

import sqlalchemy as sa
from sqlalchemy.orm import aliased, selectinload

from src.core.database import db
from src.core.estudios import Analisis, Estudio
from src.core.pacientes import Paciente
from src.core.paginacion import Pagina, paginar
from src.core.usuarios import Usuario, roles

ESTUDIOS_POR_PAGINA = 20
LARGO_MAXIMO_DEL_TEXTO = 100


@dataclass(frozen=True)
class BusquedaDeEstudios:
    """Lo que busca el médico tratante en su listado: DNI o nombre del paciente, y la página."""

    texto: str = ""
    pagina: int = 1

    @classmethod
    def desde(cls, parametros: Mapping[str, str]) -> "BusquedaDeEstudios":
        """Toma los parámetros de la URL (request.args); una página inválida es la primera."""
        texto = " ".join((parametros.get("texto") or "").split())[:LARGO_MAXIMO_DEL_TEXTO]
        pagina = parametros.get("pagina") or ""
        return cls(
            texto=texto,
            pagina=int(pagina) if pagina.isascii() and pagina.isdigit() and len(pagina) < 7 else 1,
        )

    @property
    def filtrada(self) -> bool:
        return bool(self.texto)

    def parametros(self, **cambios) -> dict[str, str | int]:
        """Parámetros de URL de esta búsqueda con `cambios`, sin los que valen lo de por defecto."""
        busqueda = replace(self, **{"pagina": 1, **cambios})
        por_defecto = asdict(BusquedaDeEstudios())
        return {
            clave: valor for clave, valor in asdict(busqueda).items() if valor != por_defecto[clave]
        }


def estudio_del_paciente(usuario: Usuario) -> Estudio | None:
    """El estudio del paciente logueado, o None si todavía no tiene (O20: uno por paciente)."""
    consulta = (
        sa.select(Estudio)
        .join(Estudio.paciente)
        .where(Paciente.usuario_id == usuario.id)
        .options(selectinload(Estudio.paciente).selectinload(Paciente.usuario))
    )
    return db.session.scalar(consulta)


def estudios_del_medico(
    usuario: Usuario, busqueda: BusquedaDeEstudios, por_pagina: int = ESTUDIOS_POR_PAGINA
) -> Pagina[Estudio]:
    """Estudios a cargo del médico tratante, ordenados por apellido y nombre del paciente.

    Cada palabra del texto tiene que aparecer en el DNI, el nombre o el apellido del paciente,
    sin distinguir mayúsculas: "gom 3012" encuentra a Gómez, DNI 30123456.
    """
    usuario_del_paciente = aliased(Usuario)
    consulta = (
        sa.select(Estudio)
        .join(Estudio.paciente)
        .join(usuario_del_paciente, Paciente.usuario_id == usuario_del_paciente.id)
        .where(Estudio.medico_tratante_id == usuario.id)
        .options(selectinload(Estudio.paciente).selectinload(Paciente.usuario))
    )
    for palabra in busqueda.texto.split():
        consulta = consulta.where(
            sa.or_(
                Paciente.dni.contains(palabra, autoescape=True),
                usuario_del_paciente.nombre.icontains(palabra, autoescape=True),
                usuario_del_paciente.apellido.icontains(palabra, autoescape=True),
            )
        )
    consulta = consulta.order_by(
        sa.func.lower(usuario_del_paciente.apellido),
        sa.func.lower(usuario_del_paciente.nombre),
        Estudio.id,
    )
    return paginar(consulta, busqueda.pagina, por_pagina)


def puede_ver(usuario: Usuario, estudio: Estudio) -> bool:
    """True si el usuario puede ver el estudio: es su paciente o su médico tratante."""
    if usuario.tiene_rol(roles.PACIENTE):
        return estudio.paciente.usuario_id == usuario.id
    if usuario.tiene_rol(roles.MEDICO_TRATANTE):
        return estudio.medico_tratante_id == usuario.id
    return False


def estudio_visible(usuario: Usuario, estudio_id: int) -> Estudio | None:
    """El estudio con ese id si el usuario lo puede ver; None si no existe o es ajeno."""
    estudio = db.session.get(Estudio, estudio_id)
    if estudio is None or not puede_ver(usuario, estudio):
        return None
    return estudio


def analisis_visible(usuario: Usuario, analisis_id: int) -> Analisis | None:
    """El análisis con ese id si el usuario puede ver su estudio; None si no existe o es ajeno."""
    analisis = db.session.get(Analisis, analisis_id)
    if analisis is None or not puede_ver(usuario, analisis.estudio):
        return None
    return analisis
