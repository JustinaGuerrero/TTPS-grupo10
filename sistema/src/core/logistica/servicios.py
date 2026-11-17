"""Reglas de la orden del día (E23 Generar orden del día) y del retiro de muestras (E24).

Cada mañana hábil el sistema reúne, por provincia, los centros de extracción con muestras listas
para retirar (centros_con_muestras_listas de core/muestras), le pide el orden del recorrido al
módulo de optimización y le asigna la orden al transportista de la provincia. El transportista
registra el retiro centro por centro, en el orden que dio el módulo: no se puede saltear una
parada (G10: cada retiro se lleva todas las muestras listas del centro).

Ninguna función hace commit: lo decide el controlador o la tarea programada. `ahora` y `cliente`
son para los tests.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

import sqlalchemy as sa

from src.core.calendario import ahora as ahora_en_argentina
from src.core.calendario import es_dia_habil, hoy
from src.core.centros.modelos import CentroExtraccion
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, cambiar_estado
from src.core.logistica.modelos import OrdenDelDia, ParadaOrdenDelDia
from src.core.muestras.modelos import Muestra
from src.core.muestras.servicios import centros_con_muestras_listas
from src.core.notificaciones import notificar
from src.core.provincias import Provincia, listar_provincias
from src.core.turnos.modelos import TurnoExtraccion
from src.core.usuarios import listar_activos_por_rol, roles
from src.core.usuarios.modelos import Transportista, Usuario
from src.integraciones import optimizacion
from src.integraciones.base import ClienteApi, ErrorDeIntegracion

LINK_DE_LA_ORDEN = "/orden-del-dia"
LINK_DE_LAS_ORDENES = "/ordenes-del-dia"


class ErrorDeRetiro(ValueError):
    """No se puede registrar el retiro; el mensaje se muestra al transportista."""


@dataclass
class Generacion:
    """Lo que dejó una corrida de generar_ordenes()."""

    fecha: date
    es_habil: bool = True
    nuevas: list[OrdenDelDia] = field(default_factory=list)
    ya_generadas: list[OrdenDelDia] = field(default_factory=list)
    sin_transportista: list[Provincia] = field(default_factory=list)
    # Provincias en las que el módulo de recorridos falló, con el mensaje del error.
    con_error: list[tuple[Provincia, str]] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.es_habil:
            return f"El {self.fecha:%d/%m/%Y} no es día hábil: no se generan órdenes."
        partes = []
        if self.nuevas:
            partes.append(_cantidad(len(self.nuevas), "orden nueva", "órdenes nuevas"))
        if self.ya_generadas:
            partes.append(
                _cantidad(len(self.ya_generadas), "ya estaba generada", "ya estaban generadas")
            )
        if self.sin_transportista:
            nombres = ", ".join(provincia.nombre for provincia in self.sin_transportista)
            partes.append(f"sin transportista: {nombres}")
        if self.con_error:
            nombres = ", ".join(provincia.nombre for provincia, _ in self.con_error)
            partes.append(f"falló el módulo de recorridos en: {nombres}")
        if not partes:
            return "No hay muestras listas para retirar."
        return "; ".join(partes) + "."


# --- E23 Generar orden del día ----------------------------------------------------------------


def generar_ordenes(fecha: date | None = None, *, cliente: ClienteApi | None = None) -> Generacion:
    """E23.1 a E23.5: una orden del día por provincia con muestras listas para retirar.

    No hace nada en sábados, domingos ni feriados. Un transportista que ya tiene la orden de la
    fecha no recibe otra (se puede correr dos veces sin duplicar). Si la provincia no tiene
    transportista activo o el módulo de recorridos falla, esa provincia queda sin orden y se
    avisa a los administrativos, que la regeneran a mano (G5). Corre los días hábiles a las 7
    (tarea programada de src/web/tareas.py).
    """
    fecha = fecha or hoy()
    generacion = Generacion(fecha)
    if not es_dia_habil(fecha):
        generacion.es_habil = False
        return generacion

    for provincia in listar_provincias():
        centros = centros_con_muestras_listas(provincia)
        if not centros:
            continue
        transportista = transportista_de(provincia)
        if transportista is None:
            generacion.sin_transportista.append(provincia)
            _avisar_a_los_administrativos(
                "Provincia sin transportista",
                f"{provincia.nombre} tiene muestras listas para retirar y no tiene un "
                "transportista activo. Asigná uno y regenerá las órdenes del día.",
            )
            continue
        existente = orden_de(transportista.usuario, fecha)
        if existente is not None:
            generacion.ya_generadas.append(existente)
            continue
        try:
            orden = _crear_orden(transportista, fecha, centros, cliente)
        except ErrorDeIntegracion as error:
            generacion.con_error.append((provincia, error.mensaje))
            _avisar_a_los_administrativos(
                "No se generó la orden del día",
                f"No se pudo generar la orden del día de {provincia.nombre}: {error.mensaje} "
                "Regenerala desde Órdenes del día.",
            )
            continue
        generacion.nuevas.append(orden)
    return generacion


def _crear_orden(
    transportista: Transportista,
    fecha: date,
    centros: list[CentroExtraccion],
    cliente: ClienteApi | None,
) -> OrdenDelDia:
    """E23.2 a E23.5: pide el recorrido al módulo, guarda la orden con sus paradas y avisa."""
    por_id = {centro.id: centro for centro in centros}
    puntos = [
        optimizacion.Punto(centro.id, centro.direccion_completa, centro.latitud, centro.longitud)
        for centro in centros
    ]
    recorrido = [por_id[centro_id] for centro_id in optimizacion.ordenar(puntos, cliente=cliente)]

    orden = OrdenDelDia(transportista_id=transportista.usuario_id, fecha=fecha)
    db.session.add(orden)
    db.session.flush()
    for posicion, centro in enumerate(recorrido, start=1):
        db.session.add(
            ParadaOrdenDelDia(orden_del_dia_id=orden.id, posicion=posicion, centro_id=centro.id)
        )
    db.session.flush()
    db.session.refresh(orden)

    primero = recorrido[0]
    cantidad = f"{len(recorrido)} centro{'s' if len(recorrido) != 1 else ''}"
    notificar(
        transportista.usuario,
        "Tu orden del día",
        f"Hoy retirás muestras en {cantidad} de {transportista.provincia.nombre}. Empezá por "
        f"{primero.nombre} ({primero.direccion_completa}) y seguí el orden de la lista.",
        LINK_DE_LA_ORDEN,
    )
    return orden


def _cantidad(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def transportista_de(provincia: Provincia) -> Transportista | None:
    """El transportista activo de la provincia (hay uno como mucho), o None."""
    consulta = (
        sa.select(Transportista)
        .join(Usuario, Usuario.id == Transportista.usuario_id)
        .where(Transportista.provincia_id == provincia.id, Usuario.activo)
    )
    return db.session.scalar(consulta)


def _avisar_a_los_administrativos(asunto: str, mensaje: str) -> None:
    for administrativo in listar_activos_por_rol(roles.ADMINISTRATIVO):
        notificar(administrativo, asunto, mensaje, LINK_DE_LAS_ORDENES)


# --- consultas --------------------------------------------------------------------------------


def orden_de(transportista: Usuario, fecha: date) -> OrdenDelDia | None:
    consulta = sa.select(OrdenDelDia).where(
        OrdenDelDia.transportista_id == transportista.id, OrdenDelDia.fecha == fecha
    )
    return db.session.scalar(consulta)


def orden_de_hoy(transportista: Usuario) -> OrdenDelDia | None:
    """E24: la orden del día del transportista para hoy, o None."""
    return orden_de(transportista, hoy())


def ordenes_de(fecha: date) -> list[OrdenDelDia]:
    """Las órdenes de la fecha, por provincia: para la pantalla del administrativo."""
    consulta = (
        sa.select(OrdenDelDia)
        .join(Transportista, Transportista.usuario_id == OrdenDelDia.transportista_id)
        .join(Provincia, Provincia.id == Transportista.provincia_id)
        .where(OrdenDelDia.fecha == fecha)
        .order_by(Provincia.nombre)
    )
    return list(db.session.scalars(consulta))


def buscar_parada(orden: OrdenDelDia, posicion: int) -> ParadaOrdenDelDia | None:
    return db.session.get(ParadaOrdenDelDia, (orden.id, posicion))


def siguiente_parada(orden: OrdenDelDia) -> ParadaOrdenDelDia | None:
    """La primera parada sin retiro, o None si el recorrido está completo."""
    return next((parada for parada in orden.paradas if parada.retirado_en is None), None)


def muestras_por_retirar(centro: CentroExtraccion) -> int:
    """Cuántas muestras listas para retirar hay en el centro (las que se lleva el retiro)."""
    return len(_muestras_listas(centro))


def muestras_retiradas(parada: ParadaOrdenDelDia) -> int:
    """Cuántas muestras se llevó el transportista de esa parada."""
    consulta = (
        sa.select(sa.func.count())
        .select_from(Muestra)
        .join(TurnoExtraccion, TurnoExtraccion.id == Muestra.turno_id)
        .where(
            Muestra.orden_del_dia_id == parada.orden_del_dia_id,
            TurnoExtraccion.centro_id == parada.centro_id,
        )
    )
    return db.session.scalar(consulta) or 0


# --- E24 Retirar muestras ---------------------------------------------------------------------


def registrar_retiro(
    parada: ParadaOrdenDelDia, transportista: Usuario, ahora: datetime | None = None
) -> list[Estudio]:
    """E24.3 y E24.4: el transportista retira las muestras del centro; pasan a En camino.

    Se lleva todas las muestras listas del centro, también las que llegaron después de generar
    la orden (G10), y les carga la orden del día. Solo se puede registrar la siguiente parada
    pendiente de la orden propia. Lanza ErrorDeRetiro si no. Devuelve los estudios que retiró.
    """
    ahora = ahora or ahora_en_argentina()
    orden = parada.orden_del_dia
    if orden.transportista_id != transportista.id:
        raise ErrorDeRetiro("Solo el transportista de la orden registra sus retiros.")
    if parada.retirado_en is not None:
        raise ErrorDeRetiro(f"Ya registraste el retiro en {parada.centro.nombre}.")
    siguiente = siguiente_parada(orden)
    if siguiente is not None and siguiente.posicion != parada.posicion:
        raise ErrorDeRetiro(
            f"El orden del recorrido es fijo: primero retirá en {siguiente.centro.nombre}."
        )

    estudios = []
    for muestra in _muestras_listas(parada.centro):
        muestra.orden_del_dia_id = orden.id
        cambiar_estado(
            muestra.estudio,
            EstadoEstudio.EN_CAMINO_LABORATORIO,
            transportista,
            motivo=f"Retiro en {parada.centro.nombre}",
        )
        estudios.append(muestra.estudio)
    parada.retirado_en = ahora
    db.session.flush()
    return estudios


def _muestras_listas(centro: CentroExtraccion) -> list[Muestra]:
    """Las muestras del centro listas para retirar, con el mismo criterio que
    centros_con_muestras_listas: estudio Listo para retirar, sin orden y no insuficientes."""
    consulta = (
        sa.select(Muestra)
        .join(TurnoExtraccion, TurnoExtraccion.id == Muestra.turno_id)
        .join(Estudio, Estudio.id == Muestra.estudio_id)
        .where(
            TurnoExtraccion.centro_id == centro.id,
            Estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR,
            Muestra.orden_del_dia_id.is_(None),
            Muestra.insuficiente_en.is_(None),
        )
        .order_by(Muestra.id)
    )
    return list(db.session.scalars(consulta))
