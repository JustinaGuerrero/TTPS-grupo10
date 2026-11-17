"""Cliente del módulo de optimización de recorridos (módulo 9), según el borrador
docs/apis/optimizacion.md.

El contrato todavía no está publicado: este cliente asume la interfaz del borrador, marcada
provisoria. Cuando llegue el contrato real, cambia solo este archivo.

- ordenar([Punto(id, direccion, latitud, longitud), ...]) → [id, id, ...] en el orden del recorrido

Lanza ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar. Con
USE_MOCKS=1 no llama al módulo: ordena los puntos por cercanía, empezando por el primero de la
lista (el vecino más cercano). Acepta `cliente=` para los tests.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "El módulo de optimización de recorridos"
RADIO_DE_LA_TIERRA_KM = 6371.0


@dataclass(frozen=True)
class Punto:
    """Un lugar del recorrido. `id` es el del centro de extracción en nuestra base."""

    id: int
    direccion: str
    latitud: Decimal
    longitud: Decimal


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("OPTIMIZACION_KEY")
    return ClienteApi(
        NOMBRE,
        config.get("OPTIMIZACION_URL"),
        headers={"apikey": clave} if clave else None,
        usar_mocks=bool(config.get("USE_MOCKS")),
    )


def ordenar(puntos: Sequence[Punto], *, cliente: ClienteApi | None = None) -> list[int]:
    """E23.2 y E23.3: manda los puntos al módulo y devuelve sus ids en el orden del recorrido.

    El orden es el que da el módulo y no se cambia. Lanza ErrorDeIntegracion si el módulo no
    responde o si la respuesta no trae exactamente los ids que se mandaron.
    """
    if not puntos:
        return []
    cliente = cliente or cliente_por_defecto()
    if cliente.usar_mocks:
        return por_cercania(puntos)
    cuerpo = {
        "puntos": [
            {
                "id": punto.id,
                "direccion": punto.direccion,
                "latitud": float(punto.latitud),
                "longitud": float(punto.longitud),
            }
            for punto in puntos
        ]
    }
    datos = cliente.post("recorridos", mock="ordenar", json=cuerpo).datos
    orden = datos.get("orden") if isinstance(datos, dict) else None
    enviados = [punto.id for punto in puntos]
    if (
        not isinstance(orden, list)
        or not all(isinstance(id_, int) and not isinstance(id_, bool) for id_ in orden)
        or sorted(orden) != sorted(enviados)
    ):
        raise cliente.formato_inesperado()
    return orden


def por_cercania(puntos: Sequence[Punto]) -> list[int]:
    """Mock del módulo: arranca en el primer punto y sigue siempre por el más cercano."""
    pendientes = list(puntos)
    actual = pendientes.pop(0)
    orden = [actual.id]
    while pendientes:
        actual = min(pendientes, key=lambda punto: (_distancia_km(actual, punto), punto.id))
        pendientes.remove(actual)
        orden.append(actual.id)
    return orden


def _distancia_km(a: Punto, b: Punto) -> float:
    """Distancia en línea recta sobre la superficie de la Tierra (fórmula del haversine)."""
    lat_a, lon_a, lat_b, lon_b = map(
        math.radians, (float(a.latitud), float(a.longitud), float(b.latitud), float(b.longitud))
    )
    h = (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    )
    return 2 * RADIO_DE_LA_TIERRA_KM * math.asin(math.sqrt(h))
