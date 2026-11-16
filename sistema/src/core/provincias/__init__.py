"""Provincias: las 24 jurisdicciones del país, datos fijos de la migración de E03.

Las usan el transportista (una provincia cada uno), los centros de extracción y la orden del día.
"""

from src.core.provincias.modelos import Provincia
from src.core.provincias.servicios import buscar_provincia, listar_provincias

__all__ = ["Provincia", "buscar_provincia", "listar_provincias"]
