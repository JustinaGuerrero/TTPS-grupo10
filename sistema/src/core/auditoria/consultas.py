"""Consultar el registro de cambios (E43): el historial de una entidad y la lista completa.

historial_de() es la línea de tiempo de un paciente, un estudio o un sample set. Para un estudio
mezcla los cambios de datos (auditoria) con los de estado (historial_estados, acción `estado`),
porque cambiar_estado() ya deja cada cambio de estado ahí y no se duplica (G16).

Este módulo no importa core/estudios: lee historial_estados con una definición mínima de la tabla,
para que core/estudios pueda llamar a registrar() sin dependencias circulares.

    filtros = FiltrosDeAuditoria.desde(request.args)
    pagina = listar(filtros)
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from src.core.auditoria.modelos import Accion, Entidad, RegistroDeCambio
from src.core.database import db
from src.core.paginacion import Pagina, paginar
from src.core.usuarios.modelos import Usuario

REGISTROS_POR_PAGINA = 25
# Los filtros de fecha son días de Argentina, que es como se muestran.
ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")
# Valor del filtro de usuario para los cambios que hizo el sistema.
USUARIO_SISTEMA = "sistema"

_HISTORIAL_ESTADOS = sa.table(
    "historial_estados",
    sa.column("id", sa.BigInteger),
    sa.column("estudio_id", sa.BigInteger),
    sa.column("estado_anterior", sa.Text),
    sa.column("estado_nuevo", sa.Text),
    sa.column("usuario_id", sa.BigInteger),
    sa.column("motivo", sa.Text),
    sa.column("creado_en", sa.DateTime(timezone=True)),
)


@dataclass(frozen=True)
class Cambio:
    """Una línea del historial: un campo que cambió, o un cambio de estado."""

    creado_en: datetime
    accion: Accion
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None
    # Nulo si lo hizo el sistema.
    usuario: Usuario | None
    detalle: str | None = None

    @property
    def quien(self) -> str:
        return self.usuario.nombre_completo if self.usuario is not None else "Sistema"


def historial_de(entidad: Entidad | str, entidad_id: int) -> list[Cambio]:
    """Todos los cambios de una entidad, del más nuevo al más viejo."""
    entidad = Entidad(entidad)
    registros = db.session.scalars(
        sa.select(RegistroDeCambio)
        .where(RegistroDeCambio.entidad == entidad, RegistroDeCambio.entidad_id == entidad_id)
        .options(selectinload(RegistroDeCambio.usuario))
    ).all()
    # El segundo valor desempata: now() da la misma hora a todo lo de una transacción.
    cambios = [((c.creado_en, 1, c.id), _cambio_de(c)) for c in registros]
    if entidad is Entidad.ESTUDIO:
        cambios += _cambios_de_estado(entidad_id)
    cambios.sort(key=lambda par: par[0], reverse=True)
    return [cambio for _, cambio in cambios]


def _cambio_de(registro: RegistroDeCambio) -> Cambio:
    return Cambio(
        creado_en=registro.creado_en,
        accion=registro.accion,
        campo=registro.campo,
        valor_anterior=registro.valor_anterior,
        valor_nuevo=registro.valor_nuevo,
        usuario=registro.usuario,
        detalle=registro.detalle,
    )


def _cambios_de_estado(estudio_id: int) -> list[tuple[tuple, Cambio]]:
    filas = db.session.execute(
        sa.select(_HISTORIAL_ESTADOS)
        .where(_HISTORIAL_ESTADOS.c.estudio_id == estudio_id)
        .order_by(_HISTORIAL_ESTADOS.c.creado_en, _HISTORIAL_ESTADOS.c.id)
    ).all()
    ids = {fila.usuario_id for fila in filas if fila.usuario_id is not None}
    usuarios = (
        {u.id: u for u in db.session.scalars(sa.select(Usuario).where(Usuario.id.in_(ids)))}
        if ids
        else {}
    )
    return [
        (
            (fila.creado_en, 0, fila.id),
            Cambio(
                creado_en=fila.creado_en,
                accion=Accion.ESTADO,
                campo="estado",
                valor_anterior=fila.estado_anterior,
                valor_nuevo=fila.estado_nuevo,
                usuario=usuarios.get(fila.usuario_id),
                detalle=fila.motivo,
            ),
        )
        for fila in filas
    ]


@dataclass(frozen=True)
class FiltrosDeAuditoria:
    """Lo que pidió el administrador general en la lista. Sin filtros, todo, lo último primero."""

    # Código de la entidad, o vacío para todas.
    entidad: str = ""
    # Id del usuario, USUARIO_SISTEMA o vacío para todos.
    usuario: str = ""
    # Días de Argentina, ambos incluidos.
    desde: date | None = None
    hasta: date | None = None
    pagina: int = 1

    @classmethod
    def desde_parametros(cls, parametros: Mapping[str, str]) -> "FiltrosDeAuditoria":
        """Toma los parámetros de la URL (request.args) y descarta los que no son válidos."""
        entidad = parametros.get("entidad") or ""
        usuario = parametros.get("usuario") or ""
        pagina = parametros.get("pagina") or ""
        return cls(
            entidad=entidad if entidad in list(Entidad) else "",
            usuario=usuario
            if usuario == USUARIO_SISTEMA
            or (usuario.isascii() and usuario.isdigit())
            and len(usuario) < 12
            else "",
            desde=_fecha(parametros.get("desde")),
            hasta=_fecha(parametros.get("hasta")),
            pagina=int(pagina) if pagina.isascii() and pagina.isdigit() and len(pagina) < 7 else 1,
        )

    @property
    def filtrada(self) -> bool:
        return bool(self.entidad or self.usuario or self.desde or self.hasta)

    def parametros(self, **cambios) -> dict[str, str | int]:
        """Parámetros de URL con `cambios`, sin los vacíos. Vuelve a la página 1 salvo que se pida."""
        filtros = replace(self, **{"pagina": 1, **cambios})
        resultado: dict[str, str | int] = {}
        for clave, valor in asdict(filtros).items():
            if clave == "pagina":
                if valor != 1:
                    resultado[clave] = valor
            elif valor:
                resultado[clave] = valor.isoformat() if isinstance(valor, date) else valor
        return resultado


def _fecha(texto: str | None) -> date | None:
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def listar(
    filtros: FiltrosDeAuditoria, por_pagina: int = REGISTROS_POR_PAGINA
) -> Pagina[RegistroDeCambio]:
    """Cambios que cumplen los filtros, del más nuevo al más viejo y de a `por_pagina`.

    Es solo el registro de datos (auditoria): los cambios de estado se ven en el historial del
    estudio. Con las dos fechas invertidas no hay resultados.
    """
    consulta = sa.select(RegistroDeCambio).options(selectinload(RegistroDeCambio.usuario))
    if filtros.entidad:
        consulta = consulta.where(RegistroDeCambio.entidad == Entidad(filtros.entidad))
    if filtros.usuario == USUARIO_SISTEMA:
        consulta = consulta.where(RegistroDeCambio.usuario_id.is_(None))
    elif filtros.usuario:
        consulta = consulta.where(RegistroDeCambio.usuario_id == int(filtros.usuario))
    if filtros.desde:
        consulta = consulta.where(RegistroDeCambio.creado_en >= _inicio_del_dia(filtros.desde))
    if filtros.hasta:
        consulta = consulta.where(
            RegistroDeCambio.creado_en < _inicio_del_dia(filtros.hasta + timedelta(days=1))
        )
    consulta = consulta.order_by(RegistroDeCambio.creado_en.desc(), RegistroDeCambio.id.desc())
    return paginar(consulta, filtros.pagina, por_pagina)


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=ZONA_HORARIA)


def usuarios_con_registros() -> list[Usuario]:
    """Usuarios que hicieron algún cambio, para el filtro de la lista."""
    return list(
        db.session.scalars(
            sa.select(Usuario)
            .where(
                Usuario.id.in_(
                    sa.select(RegistroDeCambio.usuario_id).where(
                        RegistroDeCambio.usuario_id.is_not(None)
                    )
                )
            )
            .order_by(sa.func.lower(Usuario.apellido), sa.func.lower(Usuario.nombre), Usuario.id)
        )
    )


def hay_registros_de(entidad: Entidad | str, entidad_id: int) -> bool:
    """Si la entidad tiene algún cambio registrado."""
    return db.session.scalar(
        sa.select(
            sa.exists().where(
                RegistroDeCambio.entidad == Entidad(entidad),
                RegistroDeCambio.entidad_id == entidad_id,
            )
        )
    )
