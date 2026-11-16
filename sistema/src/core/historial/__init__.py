"""Historial de estudios (E11): consultas de solo lectura para el paciente y el médico tratante.

- consultas.py  el estudio del paciente, los estudios del médico con búsqueda y paginación, y
                quién puede ver un estudio o un análisis (uno ajeno da None → 404).

No cambia datos: el estado y el historial los escribe solo src/core/estudios.
"""

from src.core.historial.consultas import (
    ESTUDIOS_POR_PAGINA,
    BusquedaDeEstudios,
    analisis_visible,
    estudio_del_paciente,
    estudio_visible,
    estudios_del_medico,
    puede_ver,
)

__all__ = [
    "ESTUDIOS_POR_PAGINA",
    "BusquedaDeEstudios",
    "analisis_visible",
    "estudio_del_paciente",
    "estudio_visible",
    "estudios_del_medico",
    "puede_ver",
]
