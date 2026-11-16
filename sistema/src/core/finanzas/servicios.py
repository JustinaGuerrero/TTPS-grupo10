"""Registro financiero (E41): registrar_asiento() y las consultas de caja y deuda.

Ninguna función hace commit: lo decide quien llama, junto con el pago y el cambio de estado.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import sqlalchemy as sa

from src.core.database import db
from src.core.estudios.modelos import Estudio
from src.core.finanzas.modelos import AsientoFinanciero, TipoAsiento
from src.core.obras_sociales import ObraSocial


class ConId(Protocol):
    """Cualquier modelo con id; registrar_asiento() solo necesita el id del pago."""

    id: int


_CON_OBRA_SOCIAL = (TipoAsiento.COBERTURA_OBRA_SOCIAL, TipoAsiento.COBRO_OBRA_SOCIAL)
_SIN_PAGO = (TipoAsiento.PRESUPUESTO_EMITIDO, TipoAsiento.COBRO_OBRA_SOCIAL)


@dataclass(frozen=True)
class DeudaDePaciente:
    paciente_id: int
    estudio_id: int
    importe_usd: Decimal


@dataclass(frozen=True)
class DeudaDeObraSocial:
    codigo: str
    nombre: str
    importe_usd: Decimal


def registrar_asiento(
    tipo: TipoAsiento | str,
    estudio: Estudio,
    importe: Decimal | int | str,
    pago: ConId | None = None,
    obra_social: ObraSocial | None = None,
) -> AsientoFinanciero:
    """Inserta un asiento. Sirve para los cinco tipos; controla lo mismo que los check de la base.

    `importe` es siempre positivo. `pago` es obligatorio salvo en presupuesto_emitido y
    cobro_obra_social; `obra_social` es obligatoria en cobertura_obra_social y cobro_obra_social
    y está prohibida en los demás. Lanza ValueError si no se cumple.
    """
    try:
        tipo = TipoAsiento(tipo)
    except ValueError:
        raise ValueError(f"«{tipo}» no es un tipo de asiento financiero.") from None
    importe = Decimal(str(importe))
    if importe <= 0:
        raise ValueError("El importe de un asiento tiene que ser mayor a cero.")
    if (tipo in _CON_OBRA_SOCIAL) != (obra_social is not None):
        raise ValueError(
            f"El asiento {tipo} {'exige' if tipo in _CON_OBRA_SOCIAL else 'no admite'} "
            "una obra social."
        )
    if tipo not in _SIN_PAGO and pago is None:
        raise ValueError(f"El asiento {tipo} exige el pago que lo originó.")

    asiento = AsientoFinanciero(
        tipo=tipo,
        estudio_id=estudio.id,
        pago_id=pago.id if pago is not None else None,
        obra_social_codigo=obra_social.codigo if obra_social is not None else None,
        importe_usd=importe,
    )
    db.session.add(asiento)
    db.session.flush()
    return asiento


def _suma(*tipos: TipoAsiento):
    return sa.func.coalesce(
        sa.func.sum(AsientoFinanciero.importe_usd).filter(AsientoFinanciero.tipo.in_(tipos)), 0
    )


def caja() -> Decimal:
    """Plata cobrada: pagos particulares más cobros a obras sociales."""
    consulta = sa.select(_suma(TipoAsiento.PAGO_PARTICULAR, TipoAsiento.COBRO_OBRA_SOCIAL))
    return Decimal(db.session.scalar(consulta))


def deuda_por_paciente() -> list[DeudaDePaciente]:
    """Estudios con deuda del paciente: presupuesto menos pagos, descuentos y cobertura.

    Solo los que deben algo, de mayor a menor deuda.
    """
    deuda = (
        _suma(TipoAsiento.PRESUPUESTO_EMITIDO)
        - _suma(
            TipoAsiento.PAGO_PARTICULAR,
            TipoAsiento.DESCUENTO_CUPON,
            TipoAsiento.COBERTURA_OBRA_SOCIAL,
        )
    ).label("deuda")
    consulta = (
        sa.select(Estudio.paciente_id, AsientoFinanciero.estudio_id, deuda)
        .join(Estudio, Estudio.id == AsientoFinanciero.estudio_id)
        .group_by(Estudio.paciente_id, AsientoFinanciero.estudio_id)
        .having(deuda > 0)
        .order_by(deuda.desc(), AsientoFinanciero.estudio_id)
    )
    return [
        DeudaDePaciente(paciente, estudio, Decimal(importe))
        for paciente, estudio, importe in db.session.execute(consulta)
    ]


def deuda_por_obra_social() -> list[DeudaDeObraSocial]:
    """Lo que cada obra social adeuda: cobertura autorizada menos lo que ya cobró el laboratorio."""
    deuda = (_suma(TipoAsiento.COBERTURA_OBRA_SOCIAL) - _suma(TipoAsiento.COBRO_OBRA_SOCIAL)).label(
        "deuda"
    )
    consulta = (
        sa.select(ObraSocial.codigo, ObraSocial.nombre, deuda)
        .join(AsientoFinanciero, AsientoFinanciero.obra_social_codigo == ObraSocial.codigo)
        .group_by(ObraSocial.codigo, ObraSocial.nombre)
        .having(deuda > 0)
        .order_by(deuda.desc(), ObraSocial.codigo)
    )
    return [
        DeudaDeObraSocial(codigo, nombre, Decimal(importe))
        for codigo, nombre, importe in db.session.execute(consulta)
    ]
