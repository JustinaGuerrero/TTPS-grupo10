"""Estudio y máquina de estados (decisión S9).

El estado de un estudio cambia SOLO con cambiar_estado(), que permite las 21 transiciones del LEL
(TRANSICIONES en estados.py) y guarda cada cambio en historial_estados con fecha y usuario.
"""

from src.core.estudios.estados import (
    TRANSICIONES,
    EstadoEstudio,
    TransicionInvalida,
    puede_pasar,
)
from src.core.estudios.modelos import Analisis, AnalisisGen, Estudio, HistorialEstado, TipoAnalisis
from src.core.estudios.servicios import cambiar_estado, crear_estudio

__all__ = [
    "TRANSICIONES",
    "Analisis",
    "AnalisisGen",
    "EstadoEstudio",
    "Estudio",
    "HistorialEstado",
    "TipoAnalisis",
    "TransicionInvalida",
    "cambiar_estado",
    "crear_estudio",
    "puede_pasar",
]
