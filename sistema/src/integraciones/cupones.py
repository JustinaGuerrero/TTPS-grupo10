"""Cliente del módulo de cupones (módulo externo), según docs/apis/cupones.md (borrador).

El contrato todavía no existe: esto es lo que el sistema necesita y se ajusta cuando llegue.

- generar(20, 3)       → [CuponGenerado(codigo, pdf), ...]   (POST /cupones)
- consultar("123456")  → EstadoEnModulo(codigo, estado, descuento_porcentaje)  (GET /cupones/<codigo>)
- vencer("123456")     → None                                 (POST /cupones/<codigo>/vencer)

Todas lanzan ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar. Con
USE_MOCKS=1 responden con los archivos de tests/fixtures/apis/cupones/. Cada función acepta
`cliente=` para los tests; si no se pasa, se arma con CUPONES_URL, CUPONES_KEY y USE_MOCKS.
"""

import base64
import binascii
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "Cupones"
_CODIGO_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,64}")


@dataclass(frozen=True)
class CuponGenerado:
    codigo: str
    # Contenido del PDF con el código QR y el código numérico.
    pdf: bytes


@dataclass(frozen=True)
class EstadoEnModulo:
    codigo: str
    # "vigente" o "utilizado": el módulo es el que manda.
    estado: str
    descuento_porcentaje: Decimal

    @property
    def vigente(self) -> bool:
        return self.estado == "vigente"


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    return ClienteApi(
        NOMBRE,
        config.get("CUPONES_URL"),
        headers={"apikey": config.get("CUPONES_KEY") or ""},
        usar_mocks=bool(config.get("USE_MOCKS")),
    )


def generar(
    descuento: int | Decimal, cantidad: int, *, cliente: ClienteApi | None = None
) -> list[CuponGenerado]:
    """Pide `cantidad` cupones con ese descuento porcentual."""
    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.post(
        "cupones",
        json={"descuento": float(descuento), "cantidad": cantidad},
        mock="generar",
    )
    datos = respuesta.datos
    if not isinstance(datos, list) or len(datos) < cantidad:
        raise cliente.formato_inesperado()
    cupones = []
    for item in datos[:cantidad]:
        try:
            codigo = _codigo(item["codigo"])
            pdf = base64.b64decode(item["pdf_base64"], validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error):
            raise cliente.formato_inesperado() from None
        cupones.append(CuponGenerado(codigo, pdf))
    return cupones


def consultar(codigo: str, *, cliente: ClienteApi | None = None) -> EstadoEnModulo:
    """Estado del cupón en el módulo."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    respuesta = cliente.get(f"cupones/{codigo}", mock=[f"consultar_{codigo}", "consultar"])
    datos = respuesta.datos
    try:
        estado = datos["estado"]
        if estado not in ("vigente", "utilizado"):
            raise ValueError(estado)
        return EstadoEnModulo(codigo, estado, Decimal(str(datos["descuento_porcentaje"])))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise cliente.formato_inesperado() from None


def vencer(codigo: str, *, cliente: ClienteApi | None = None) -> None:
    """Informa al módulo que el cupón se usó, para que lo venza."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    cliente.post(f"cupones/{codigo}/vencer", mock=[f"vencer_{codigo}", "vencer"])


def _codigo(codigo: str) -> str:
    codigo = str(codigo or "").strip()
    if not _CODIGO_VALIDO.fullmatch(codigo):
        raise ValueError(f"Código de cupón inválido: {codigo!r}")
    return codigo
