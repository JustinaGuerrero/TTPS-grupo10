"""Reglas de presupuesto y pago particular (E13, E14).

Cada función hace todo su trabajo (presupuesto o pago, asiento, cambio de estado y aviso) sin
hacer commit: el controlador confirma o hace rollback, así que es una sola transacción. Todas las
validaciones van antes de escribir.
"""

from decimal import Decimal, InvalidOperation

import sqlalchemy as sa

from src.core.database import db
from src.core.estudios import EstadoEstudio, cambiar_estado
from src.core.estudios.modelos import Estudio
from src.core.finanzas.modelos import Pago, TipoAsiento, TipoPago
from src.core.finanzas.servicios import registrar_asiento
from src.core.notificaciones import notificar
from src.core.pacientes.modelos import Paciente
from src.core.paginacion import Pagina, paginar
from src.core.pagos.modelos import Presupuesto
from src.core.usuarios import roles
from src.core.usuarios.modelos import Usuario

PRECIO_BASE_USD = Decimal("500.00")
GENES_INCLUIDOS = 5
PRECIO_GEN_ADICIONAL_USD = Decimal("30.00")
ESTUDIOS_POR_PAGINA = 20


class ErrorDePago(ValueError):
    """No se puede emitir el presupuesto o registrar el pago; el mensaje se muestra al usuario."""


def calcular_importe(cantidad_genes: int) -> Decimal:
    """500 USD hasta 5 genes y 30 USD por cada gen adicional, con la extracción incluida."""
    if cantidad_genes < 1:
        raise ValueError("El estudio necesita al menos un gen.")
    adicionales = max(0, cantidad_genes - GENES_INCLUIDOS)
    return PRECIO_BASE_USD + PRECIO_GEN_ADICIONAL_USD * adicionales


def cantidad_de_genes(estudio: Estudio) -> int:
    """Genes del análisis inicial. Los de hallazgos secundarios no se guardan ni cuentan (O13)."""
    return len(estudio.analisis[0].genes)


def estudios_en_creado(pagina: int = 1) -> Pagina[Estudio]:
    """E13.1: estudios Creado, los más viejos primero."""
    consulta = (
        sa.select(Estudio)
        .where(Estudio.estado == EstadoEstudio.CREADO)
        .order_by(Estudio.creado_en, Estudio.id)
    )
    return paginar(consulta, pagina, ESTUDIOS_POR_PAGINA)


def buscar_estudio(estudio_id: int) -> Estudio | None:
    return db.session.get(Estudio, estudio_id)


def estudio_del_paciente(usuario: Usuario) -> Estudio | None:
    """El estudio del paciente que usa esta cuenta (hay uno solo, O20), o None."""
    consulta = sa.select(Estudio).join(Paciente).where(Paciente.usuario_id == usuario.id)
    return db.session.scalar(consulta)


def presupuesto_de(estudio: Estudio) -> Presupuesto | None:
    return db.session.scalar(sa.select(Presupuesto).where(Presupuesto.estudio_id == estudio.id))


def importe_final(presupuesto: Presupuesto) -> Decimal:
    """Lo que paga el paciente. Hoy es el total; el issue de cupones le resta el descuento."""
    return presupuesto.total_usd


def emitir_presupuesto(estudio: Estudio, administrativo: Usuario) -> Presupuesto:
    """E13.2 a E13.5: calcula el importe, publica el presupuesto, pasa a Presupuestado y avisa.

    Lanza ErrorDePago si quien emite no es administrativo, si el estudio no está en Creado o si
    ya tiene presupuesto.
    """
    if not administrativo.tiene_rol(roles.ADMINISTRATIVO):
        raise ErrorDePago("Solo un administrativo puede emitir un presupuesto.")
    if presupuesto_de(estudio) is not None:
        raise ErrorDePago(f"El estudio {estudio.codigo} ya tiene presupuesto.")
    if estudio.estado != EstadoEstudio.CREADO:
        raise ErrorDePago(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: "
            "solo se presupuestan los estudios en Creado."
        )

    cantidad = cantidad_de_genes(estudio)
    presupuesto = Presupuesto(
        estudio_id=estudio.id,
        cantidad_genes=cantidad,
        total_usd=calcular_importe(cantidad),
        emitido_por=administrativo.id,
    )
    db.session.add(presupuesto)
    db.session.flush()
    registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, estudio, presupuesto.total_usd)
    cambiar_estado(estudio, EstadoEstudio.PRESUPUESTADO, administrativo)
    notificar(
        estudio.paciente.usuario,
        "Presupuesto de tu estudio",
        f"Ya está el presupuesto de tu estudio {estudio.codigo}: {presupuesto.total_usd} USD.",
        f"/estudios/{estudio.id}/presupuesto",
        estudio=estudio,
    )
    return presupuesto


def pagar_particular(estudio: Estudio, paciente: Usuario, importe: Decimal | str) -> Pago:
    """E14.4 a E14.6: pago único y simulado por el importe final; pasa a Habilitado para turno.

    Lanza ErrorDePago si quien paga no es el paciente del estudio, si el estudio no está
    Presupuestado, si ya hay un pago particular o si el importe no es exactamente el final.
    """
    if not paciente.tiene_rol(roles.PACIENTE) or estudio.paciente.usuario_id != paciente.id:
        raise ErrorDePago("Solo el paciente del estudio puede pagarlo.")
    presupuesto = presupuesto_de(estudio)
    if presupuesto is None or estudio.estado != EstadoEstudio.PRESUPUESTADO:
        raise ErrorDePago(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: "
            "solo se paga un estudio Presupuestado."
        )
    ya_pagado = db.session.scalar(
        sa.select(Pago.id).where(Pago.estudio_id == estudio.id, Pago.tipo == TipoPago.PARTICULAR)
    )
    if ya_pagado is not None:
        raise ErrorDePago("El estudio ya tiene un pago particular: no hay cuotas.")
    try:
        importe = Decimal(str(importe).strip().replace(",", "."))
    except InvalidOperation:
        raise ErrorDePago("El importe no es un número.") from None
    final = importe_final(presupuesto)
    if importe != final:
        raise ErrorDePago(f"El pago es único: tiene que ser por el importe final, {final} USD.")

    pago = Pago(estudio_id=estudio.id, tipo=TipoPago.PARTICULAR, importe_usd=final)
    db.session.add(pago)
    db.session.flush()
    registrar_asiento(TipoAsiento.PAGO_PARTICULAR, estudio, final, pago=pago)
    cambiar_estado(estudio, EstadoEstudio.HABILITADO_TURNO, paciente)
    notificar(
        paciente,
        "Pago registrado",
        f"Recibimos el pago de tu estudio {estudio.codigo}. Ya podés sacar tu turno de extracción.",
        f"/estudios/{estudio.id}/presupuesto",
        estudio=estudio,
    )
    return pago
