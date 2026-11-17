"""Cliente de la API de obras sociales (módulo 6), según el borrador docs/apis/obras_sociales.md.

El contrato todavía no está publicado: este cliente asume la interfaz del borrador, marcada
provisoria. Cuando llegue el contrato real, cambia solo este archivo.

- listar() → [ObraSocialEnApi(codigo, nombre, porcentaje)]

Lanza ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar. Con
USE_MOCKS=1 responde con tests/fixtures/apis/obras_sociales/listar.json. Acepta `cliente=` para
los tests.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from flask import current_app

from src.integraciones.base import CARPETA_DE_MOCKS, ClienteApi

NOMBRE = "La API de obras sociales"


@dataclass(frozen=True)
class ObraSocialEnApi:
    codigo: str
    nombre: str
    # Porcentaje del presupuesto que cubre, de 0 a 100.
    porcentaje: Decimal


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("OBRAS_SOCIALES_KEY")
    cliente = ClienteApi(
        NOMBRE,
        config.get("OBRAS_SOCIALES_URL"),
        headers={"apikey": clave} if clave else None,
        usar_mocks=bool(config.get("USE_MOCKS")),
    )
    cliente.carpeta_de_mocks = CARPETA_DE_MOCKS / "obras_sociales"
    return cliente


def listar(*, cliente: ClienteApi | None = None) -> list[ObraSocialEnApi]:
    """E16.2: las obras sociales con las que trabaja el laboratorio y su porcentaje de cobertura."""
    cliente = cliente or cliente_por_defecto()
    datos = cliente.get("obras_sociales", mock="listar").datos
    if not isinstance(datos, list):
        raise cliente.formato_inesperado()
    try:
        obras = [
            ObraSocialEnApi(
                str(item["codigo"]).strip(),
                str(item["nombre"]).strip(),
                Decimal(str(item["porcentaje_cobertura"])),
            )
            for item in datos
        ]
    except (KeyError, TypeError, InvalidOperation):
        raise cliente.formato_inesperado() from None
    if any(not o.codigo or not 0 <= o.porcentaje <= 100 for o in obras):
        raise cliente.formato_inesperado()
    return sorted(obras, key=lambda obra: obra.nombre)
