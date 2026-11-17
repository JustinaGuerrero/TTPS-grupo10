"""Reglas de la cobertura de obra social: solicitar (E16), autorizar o rechazar (E17) y la demanda
de reautorización (E18).

Ninguna función hace commit: el controlador confirma o hace rollback, así que la cobertura, el
pago, el asiento, el cambio de estado y los avisos van en una sola transacción. Todas las
validaciones van antes de escribir.

Cobertura parcial (supuestos O3 y O18): si la obra social cubre menos del 100 %, la cobertura
queda autorizada pero el estudio sigue en Pendiente de autorización hasta que el paciente paga la
diferencia con el pago particular (core/pagos); recién ahí pasa a Habilitado para turno.

Módulo de obras sociales (G22): al elegir la obra social, el controlador da de alta el estudio en
el módulo después del commit (dar_de_alta_en_modulo). La obra social responde en la web del
módulo y la tarea programada consultar_respuestas aplica autorizar o rechazar sin usuario. Si el
módulo no responde, el administrativo registra la respuesta a mano, como antes.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa

from src.core.calendario import ZONA_HORARIA, ahora
from src.core.coberturas.modelos import Cobertura, DemandaReautorizacion, EstadoCobertura
from src.core.database import db
from src.core.estudios import EstadoEstudio, TransicionInvalida, cambiar_estado
from src.core.estudios.modelos import Estudio
from src.core.finanzas.modelos import Pago, TipoAsiento, TipoPago
from src.core.finanzas.servicios import registrar_asiento
from src.core.notificaciones import notificar
from src.core.obras_sociales import ObraSocial
from src.core.pagos.modelos import Presupuesto
from src.core.usuarios import listar_activos_por_rol, roles
from src.core.usuarios.modelos import Usuario
from src.integraciones import obras_sociales as api_de_obras_sociales
from src.integraciones import storage
from src.integraciones.base import ClienteApi, ErrorDeIntegracion
from src.integraciones.obras_sociales import EstadoEnModulo, ObraSocialEnApi

# E18: la resolución judicial se sube en PDF, de hasta 5 MB.
TAMANO_MAXIMO_DE_LA_RESOLUCION = 5 * 1024 * 1024
CENTAVOS = Decimal("0.01")

log = logging.getLogger(__name__)


class ErrorDeCobertura(ValueError):
    """No se puede registrar el pedido o la respuesta; el mensaje se muestra al usuario."""


# --- consultas -------------------------------------------------------------------------------


def cobertura_de(estudio: Estudio) -> Cobertura | None:
    return db.session.scalar(sa.select(Cobertura).where(Cobertura.estudio_id == estudio.id))


def buscar_cobertura(cobertura_id: int) -> Cobertura | None:
    return db.session.get(Cobertura, cobertura_id)


def pendientes() -> list[Cobertura]:
    """Pedidos que esperan la respuesta de la obra social, los más viejos primero."""
    consulta = (
        sa.select(Cobertura)
        .where(Cobertura.estado == EstadoCobertura.PENDIENTE)
        .order_by(Cobertura.solicitada_en, Cobertura.id)
    )
    return list(db.session.scalars(consulta))


def opciones(*, cliente: ClienteApi | None = None) -> list[ObraSocialEnApi]:
    """E16.2: las obras sociales de la API que cubren algo del estudio.

    Lanza ErrorDeIntegracion si la API no responde.
    """
    return [obra for obra in api_de_obras_sociales.listar(cliente=cliente) if obra.porcentaje > 0]


def diferencia_a_pagar(estudio: Estudio) -> Decimal | None:
    """Lo que le falta pagar al paciente con una cobertura parcial autorizada, o None."""
    cobertura = cobertura_de(estudio)
    if (
        cobertura is None
        or cobertura.estado != EstadoCobertura.AUTORIZADA
        or estudio.estado != EstadoEstudio.PENDIENTE_AUTORIZACION
    ):
        return None
    return _total(estudio) - cobertura.importe_cubierto_usd


# --- E16 Solicitar cobertura ------------------------------------------------------------------


def solicitar(
    estudio: Estudio, paciente: Usuario, codigo: str, *, cliente: ClienteApi | None = None
) -> Cobertura:
    """E16.3 a E16.5: guarda la obra social elegida, pasa a Pendiente de autorización y avisa.

    El porcentaje se copia de la API en este momento. Lanza ErrorDeCobertura si quien pide no es
    el paciente del estudio, si el estudio no está Presupuestado o si la obra social no está en
    la API; ErrorDeIntegracion si la API no responde.
    """
    if not paciente.tiene_rol(roles.PACIENTE) or estudio.paciente.usuario_id != paciente.id:
        raise ErrorDeCobertura("Solo el paciente del estudio puede pedir la cobertura.")
    if estudio.estado != EstadoEstudio.PRESUPUESTADO:
        raise ErrorDeCobertura(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: la cobertura se pide "
            "con el estudio Presupuestado."
        )
    if cobertura_de(estudio) is not None:
        raise ErrorDeCobertura("Ya pediste la cobertura de tu obra social para este estudio.")
    elegida = next((obra for obra in opciones(cliente=cliente) if obra.codigo == codigo), None)
    if elegida is None:
        raise ErrorDeCobertura("Elegí una obra social de la lista.")

    obra_social = _guardar_obra_social(elegida)
    cobertura = Cobertura(
        estudio_id=estudio.id,
        obra_social_codigo=obra_social.codigo,
        porcentaje=elegida.porcentaje,
    )
    db.session.add(cobertura)
    db.session.flush()
    cambiar_estado(estudio, EstadoEstudio.PENDIENTE_AUTORIZACION, paciente)
    for administrativo in listar_activos_por_rol(roles.ADMINISTRATIVO):
        notificar(
            administrativo,
            "Cobertura para autorizar",
            f"El paciente del estudio {estudio.codigo} eligió {obra_social.nombre} "
            f"({_porcentaje(cobertura)} de cobertura). El pedido va al módulo de obras sociales "
            "y la respuesta se toma de ahí; si el módulo no responde, registrala a mano.",
            "/coberturas",
            estudio=estudio,
        )
    return cobertura


def _guardar_obra_social(elegida: ObraSocialEnApi) -> ObraSocial:
    """Copia local de la obra social (upsert): el listado vigente sigue en la API."""
    obra_social = db.session.get(ObraSocial, elegida.codigo)
    if obra_social is None:
        obra_social = ObraSocial(codigo=elegida.codigo, nombre=elegida.nombre)
        db.session.add(obra_social)
    else:
        obra_social.nombre = elegida.nombre
    db.session.flush()
    return obra_social


# --- E17 Autorizar cobertura ------------------------------------------------------------------


def autorizar(cobertura: Cobertura, administrativo: Usuario | None) -> Pago:
    """E17.1 a E17.3 y E17.6: una autorización equivale a un pago de la obra social.

    Registra el pago de tipo obra_social y el asiento cobertura_obra_social por el total del
    presupuesto por el porcentaje. Al 100 % el estudio pasa a Habilitado para turno; con menos,
    sigue en Pendiente de autorización hasta que el paciente paga la diferencia. Avisa al paciente.
    `administrativo` es None cuando la respuesta llegó del módulo de obras sociales (G22).
    """
    estudio = _pendiente_de_respuesta(cobertura, administrativo)
    importe = (_total(estudio) * cobertura.porcentaje / 100).quantize(CENTAVOS, ROUND_HALF_UP)

    pago = Pago(estudio_id=estudio.id, tipo=TipoPago.OBRA_SOCIAL, importe_usd=importe)
    db.session.add(pago)
    db.session.flush()
    registrar_asiento(
        TipoAsiento.COBERTURA_OBRA_SOCIAL,
        estudio,
        importe,
        pago=pago,
        obra_social=cobertura.obra_social,
    )
    cobertura.estado = EstadoCobertura.AUTORIZADA
    cobertura.importe_cubierto_usd = importe
    _registrar_respuesta(cobertura, administrativo)

    nombre = cobertura.obra_social.nombre
    if importe >= _total(estudio):
        cambiar_estado(estudio, EstadoEstudio.HABILITADO_TURNO, administrativo)
        notificar(
            estudio.paciente.usuario,
            "Tu obra social autorizó el estudio",
            f"{nombre} autorizó la cobertura total de tu estudio {estudio.codigo}. Ya podés "
            "sacar tu turno de extracción.",
            "/turnos/mio",
            estudio=estudio,
        )
    else:
        diferencia = _total(estudio) - importe
        notificar(
            estudio.paciente.usuario,
            "Tu obra social autorizó el estudio",
            f"{nombre} autorizó el {_porcentaje(cobertura)} de tu estudio {estudio.codigo} "
            f"({importe} USD). Falta que pagues la diferencia, {diferencia} USD, para sacar tu "
            "turno de extracción.",
            f"/estudios/{estudio.id}/presupuesto",
            estudio=estudio,
        )
    return pago


def rechazar(
    cobertura: Cobertura, administrativo: Usuario | None, motivo: str | None = None
) -> Cobertura:
    """E17.4 a E17.6: pasa el estudio a Rechazado por obra social y avisa al paciente.

    `administrativo` es None cuando la respuesta llegó del módulo de obras sociales (G22).
    """
    estudio = _pendiente_de_respuesta(cobertura, administrativo)
    motivo = (motivo or "").strip() or None
    cobertura.estado = EstadoCobertura.RECHAZADA
    _registrar_respuesta(cobertura, administrativo)
    cambiar_estado(estudio, EstadoEstudio.RECHAZADO_OBRA_SOCIAL, administrativo, motivo=motivo)
    notificar(
        estudio.paciente.usuario,
        "Tu obra social rechazó el estudio",
        f"{cobertura.obra_social.nombre} rechazó la cobertura de tu estudio {estudio.codigo}"
        + (f": {motivo}." if motivo else ".")
        + " Si tenés una resolución judicial favorable, podés pedir la reautorización.",
        f"/estudios/{estudio.id}/reautorizacion",
        estudio=estudio,
    )
    return cobertura


def _pendiente_de_respuesta(cobertura: Cobertura, administrativo: Usuario | None) -> Estudio:
    if administrativo is not None and not administrativo.tiene_rol(roles.ADMINISTRATIVO):
        raise ErrorDeCobertura("Solo un administrativo registra la respuesta de la obra social.")
    estudio = cobertura.estudio
    if (
        cobertura.estado != EstadoCobertura.PENDIENTE
        or estudio.estado != EstadoEstudio.PENDIENTE_AUTORIZACION
    ):
        raise ErrorDeCobertura(
            f"La cobertura del estudio {estudio.codigo} no está esperando la respuesta de la "
            "obra social."
        )
    return estudio


def _registrar_respuesta(cobertura: Cobertura, administrativo: Usuario | None) -> None:
    cobertura.respondida_en = ahora()
    cobertura.respondida_por = administrativo.id if administrativo is not None else None
    db.session.flush()


# --- E18 Solicitar reautorización -------------------------------------------------------------


def cargar_demanda(estudio: Estudio, paciente: Usuario, resolucion: bytes) -> DemandaReautorizacion:
    """E18.1 a E18.4: guarda la resolución judicial, vuelve a Pendiente de autorización y avisa.

    La cobertura vuelve a pendiente y pierde el id del módulo: el controlador vuelve a dar de
    alta el estudio en el módulo después del commit (G22), y la respuesta llega de ahí o la carga
    el administrativo (E18.5). Lanza ErrorDeCobertura si quien la carga no es el paciente, si el estudio no está
    Rechazado por obra social o si el archivo no es un PDF de hasta 5 MB.
    """
    if estudio.paciente.usuario_id != paciente.id:
        raise ErrorDeCobertura("Solo el paciente del estudio puede cargar la demanda.")
    cobertura = cobertura_de(estudio)
    if (
        cobertura is None
        or cobertura.estado != EstadoCobertura.RECHAZADA
        or estudio.estado != EstadoEstudio.RECHAZADO_OBRA_SOCIAL
    ):
        raise ErrorDeCobertura(
            "La reautorización se pide cuando la obra social rechazó la cobertura del estudio."
        )
    if not resolucion or not resolucion.startswith(b"%PDF"):
        raise ErrorDeCobertura("Subí la resolución judicial en PDF.")
    if len(resolucion) > TAMANO_MAXIMO_DE_LA_RESOLUCION:
        raise ErrorDeCobertura("La resolución judicial no puede pesar más de 5 MB.")

    numero = len(cobertura.demandas) + 1
    ruta = storage.subir(
        f"coberturas/{cobertura.id}/resolucion-{numero}-{_marca(ahora())}.pdf",
        resolucion,
        "application/pdf",
    )
    demanda = DemandaReautorizacion(cobertura=cobertura, resolucion_path=ruta)
    db.session.add(demanda)
    cobertura.estado = EstadoCobertura.PENDIENTE
    # El alta anterior en el módulo ya tiene el rechazo: la demanda va en un alta nueva.
    cobertura.id_estudio_modulo = None
    db.session.flush()
    cambiar_estado(
        estudio,
        EstadoEstudio.PENDIENTE_AUTORIZACION,
        paciente,
        motivo="Demanda de reautorización con resolución judicial",
    )
    for administrativo in listar_activos_por_rol(roles.ADMINISTRATIVO):
        notificar(
            administrativo,
            "Reautorización pendiente",
            f"El paciente del estudio {estudio.codigo} cargó una resolución judicial favorable. "
            f"El pedido vuelve al módulo de {cobertura.obra_social.nombre}; si el módulo no "
            "responde, registrá la respuesta a mano.",
            "/coberturas",
            estudio=estudio,
        )
    return demanda


# --- G22 Módulo de obras sociales -------------------------------------------------------------


@dataclass
class ConsultaAlModulo:
    """Lo que dejó una corrida de consultar_respuestas()."""

    dadas_de_alta: int = 0
    autorizadas: int = 0
    rechazadas: int = 0
    sin_respuesta: int = 0
    # Códigos de los estudios cuya consulta falló: la próxima corrida los vuelve a consultar.
    con_error: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        partes = [
            f"{self.autorizadas} autorizadas",
            f"{self.rechazadas} rechazadas",
            f"{self.sin_respuesta} sin respuesta todavía",
        ]
        if self.dadas_de_alta:
            partes.append(f"{self.dadas_de_alta} dadas de alta en el módulo")
        if self.con_error:
            partes.append(f"el módulo falló con {', '.join(self.con_error)}")
        return ", ".join(partes) + "."


def dar_de_alta_en_modulo(cobertura: Cobertura, *, cliente: ClienteApi | None = None) -> str:
    """G22: da de alta el estudio en el módulo de obras sociales y guarda el id que devuelve.

    Van solo la obra social, el nombre del paciente y la fecha del pedido. Se llama después del
    commit del pedido (o de la demanda): si el módulo falla, lanza ErrorDeIntegracion, la
    cobertura queda pendiente sin id y consultar_respuestas la vuelve a dar de alta.
    """
    estudio = cobertura.estudio
    id_estudio = api_de_obras_sociales.alta_estudio(
        cobertura.obra_social_codigo,
        estudio.paciente.usuario.nombre_completo,
        _fecha_del_pedido(cobertura),
        cliente=cliente,
    )
    cobertura.id_estudio_modulo = id_estudio
    db.session.flush()
    return id_estudio


def consultar_respuestas(*, cliente: ClienteApi | None = None) -> ConsultaAlModulo:
    """G22: aplica las respuestas que las obras sociales cargaron en el módulo.

    Recorre las coberturas pendientes: las que no tienen id las da de alta en el módulo, y a las
    demás les consulta el estado y aplica autorizar o rechazar sin usuario. Cada cobertura va en
    su propio punto de guardado: si el módulo falla con una, esa no cambia y se siguen las demás.
    Una cobertura que ya respondió el administrativo a mano no está pendiente y no se consulta.
    Corre cada 30 minutos (tarea respuestas_obras_sociales de src/web/tareas.py).
    """
    consulta = ConsultaAlModulo()
    for cobertura in pendientes():
        codigo = cobertura.estudio.codigo
        try:
            with db.session.begin_nested():
                _consultar(cobertura, consulta, cliente)
        except (ErrorDeIntegracion, ErrorDeCobertura, TransicionInvalida) as error:
            log.warning("No se pudo consultar la cobertura del estudio %s: %s", codigo, error)
            consulta.con_error.append(codigo)
    return consulta


def _consultar(
    cobertura: Cobertura, consulta: ConsultaAlModulo, cliente: ClienteApi | None
) -> None:
    if cobertura.id_estudio_modulo is None:
        dar_de_alta_en_modulo(cobertura, cliente=cliente)
        consulta.dadas_de_alta += 1
        return
    respuesta = api_de_obras_sociales.estado_estudio(cobertura.id_estudio_modulo, cliente=cliente)
    if respuesta.estado == EstadoEnModulo.AUTORIZADO:
        autorizar(cobertura, None)
        consulta.autorizadas += 1
    elif respuesta.estado == EstadoEnModulo.RECHAZADO:
        rechazar(cobertura, None, respuesta.motivo)
        consulta.rechazadas += 1
    else:
        consulta.sin_respuesta += 1


def _fecha_del_pedido(cobertura: Cobertura) -> date:
    """La fecha del pedido: la de la última demanda de reautorización o, si no hay, la de la
    solicitud."""
    momento = cobertura.demandas[-1].cargada_en if cobertura.demandas else cobertura.solicitada_en
    return momento.astimezone(ZONA_HORARIA).date()


# --- helpers ----------------------------------------------------------------------------------


def _total(estudio: Estudio) -> Decimal:
    total = db.session.scalar(
        sa.select(Presupuesto.total_usd).where(Presupuesto.estudio_id == estudio.id)
    )
    if total is None:
        raise ErrorDeCobertura(f"El estudio {estudio.codigo} no tiene presupuesto.")
    return total


def _porcentaje(cobertura: Cobertura) -> str:
    return f"{cobertura.porcentaje.normalize():f} %"


def _marca(momento: datetime) -> str:
    return momento.strftime("%Y%m%d%H%M%S")
