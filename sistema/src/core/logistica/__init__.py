"""Logística de muestras: la orden del día del transportista y sus paradas (E23 a E26).

Las reglas (generar la orden del día, E23, y registrar los retiros, E24) están en
src.core.logistica.servicios. No se exportan acá: core/muestras importa estos modelos, y
exportar los servicios armaría un ciclo de imports con core/muestras.
"""

from src.core.logistica.modelos import OrdenDelDia, ParadaOrdenDelDia

__all__ = ["OrdenDelDia", "ParadaOrdenDelDia"]
