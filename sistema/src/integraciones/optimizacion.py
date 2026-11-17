"""Cliente del módulo de optimización de recorridos (módulo 9), según su contrato en
docs/apis/optimizacion.md (documentación en https://optimizacionapi.vercel.app/).

- ordenar([Punto(id, direccion, latitud, longitud), ...], partida=Coordenada(...)) → [id, ...]
  en el orden del recorrido

El módulo recibe solo coordenadas: la primera es el punto de partida, la última el destino y
ordena las del medio. El sistema manda la partida, los centros y la llegada, y reconoce cada
centro en la respuesta por sus coordenadas. No pide clave.

Lanza ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar. Con
USE_MOCKS=1 no llama al módulo: ordena los puntos por cercanía, empezando por el más cercano a la
partida (el vecino más cercano). Acepta `cliente=` para los tests.
"""

import math
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "El módulo de optimización de recorridos"
RADIO_DE_LA_TIERRA_KM = 6371.0
# Los centros guardan latitud y longitud con 6 decimales (numeric(9,6)).
DECIMALES = 6


@dataclass(frozen=True)
class Coordenada:
    latitud: Decimal
    longitud: Decimal


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


def ordenar(
    puntos: Sequence[Punto],
    *,
    partida: Coordenada,
    llegada: Coordenada | None = None,
    cliente: ClienteApi | None = None,
) -> list[int]:
    """E23.2 y E23.3: manda los puntos al módulo y devuelve sus ids en el orden del recorrido.

    `partida` y `llegada` son los extremos fijos del recorrido (sin `llegada`, vuelve a la
    partida). El orden es el que da el módulo y no se cambia. Lanza ErrorDeIntegracion si el
    módulo no responde o si la respuesta no trae exactamente los puntos que se mandaron.
    """
    if not puntos:
        return []
    llegada = llegada or partida
    cliente = cliente or cliente_por_defecto()
    if cliente.usar_mocks:
        return por_cercania(puntos, desde=partida)
    cuerpo = {
        "coordenadas": [_coordenada(partida), *map(_coordenada, puntos), _coordenada(llegada)]
    }
    datos = cliente.post("optimizacion", mock="ordenar", json=cuerpo).datos
    devueltas = datos.get("coordenadas") if isinstance(datos, dict) else None
    if not isinstance(devueltas, list) or len(devueltas) != len(puntos) + 2:
        raise cliente.formato_inesperado()
    claves = [_clave(item, cliente) for item in devueltas]
    if claves[0] != _clave_de(partida) or claves[-1] != _clave_de(llegada):
        raise cliente.formato_inesperado()
    return _ids_en_orden(puntos, claves[1:-1], cliente)


def _ids_en_orden(
    puntos: Sequence[Punto], claves: list[tuple[float, float]], cliente: ClienteApi
) -> list[int]:
    """Reconoce cada centro por sus coordenadas. Dos centros en el mismo lugar se toman en el
    orden en que se mandaron: da lo mismo cuál va primero."""
    ids_por_lugar: dict[tuple[float, float], deque[int]] = defaultdict(deque)
    for punto in puntos:
        ids_por_lugar[_clave_de(punto)].append(punto.id)
    orden = []
    for clave in claves:
        if not ids_por_lugar.get(clave):
            raise cliente.formato_inesperado()
        orden.append(ids_por_lugar[clave].popleft())
    return orden


def _coordenada(lugar: Coordenada | Punto) -> dict[str, float]:
    return {"lat": float(lugar.latitud), "lon": float(lugar.longitud)}


def _clave_de(lugar: Coordenada | Punto) -> tuple[float, float]:
    return round(float(lugar.latitud), DECIMALES), round(float(lugar.longitud), DECIMALES)


def _clave(item: Any, cliente: ClienteApi) -> tuple[float, float]:
    """Las coordenadas de un punto de la respuesta, redondeadas como las guarda la base."""
    if not isinstance(item, dict):
        raise cliente.formato_inesperado()
    lat, lon = item.get("lat"), item.get("lon")
    if not all(
        isinstance(valor, int | float) and not isinstance(valor, bool) for valor in (lat, lon)
    ):
        raise cliente.formato_inesperado()
    return round(float(lat), DECIMALES), round(float(lon), DECIMALES)


def por_cercania(puntos: Sequence[Punto], *, desde: Coordenada | None = None) -> list[int]:
    """Mock del módulo: va siempre al punto más cercano, empezando por el más cercano a `desde`
    (sin `desde`, por el primero de la lista)."""
    pendientes = list(puntos)
    actual: Coordenada | Punto = desde or pendientes[0]
    orden = []
    while pendientes:
        actual = min(pendientes, key=lambda punto: (_distancia_km(actual, punto), punto.id))
        pendientes.remove(actual)
        orden.append(actual.id)
    return orden


def _distancia_km(a: Coordenada | Punto, b: Coordenada | Punto) -> float:
    """Distancia en línea recta sobre la superficie de la Tierra (fórmula del haversine)."""
    lat_a, lon_a, lat_b, lon_b = map(
        math.radians, (float(a.latitud), float(a.longitud), float(b.latitud), float(b.longitud))
    )
    h = (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    )
    return 2 * RADIO_DE_LA_TIERRA_KM * math.asin(math.sqrt(h))
