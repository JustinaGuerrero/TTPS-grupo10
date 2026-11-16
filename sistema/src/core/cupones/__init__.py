"""Cupones de descuento (E37, E38) y su validación al pagar (E15).

El modelo lo comparten pagos y finanzas; las reglas están en servicios.py. Ninguna función hace
commit: lo decide el controlador.
"""

from src.core.cupones.modelos import Cupon, EstadoCupon
from src.core.cupones.servicios import (
    ErrorDeCupon,
    asignar_a_paciente,
    calcular_descuento,
    codigo_desde_pdf,
    consumir_cupon,
    cupones_del_medico,
    cupones_del_paciente,
    cupones_disponibles,
    cupones_generados,
    generar_cupones,
    medicos_tratantes,
    pacientes_del_medico,
    resolver_cupon,
)

__all__ = [
    "Cupon",
    "ErrorDeCupon",
    "EstadoCupon",
    "asignar_a_paciente",
    "calcular_descuento",
    "codigo_desde_pdf",
    "consumir_cupon",
    "cupones_del_medico",
    "cupones_del_paciente",
    "cupones_disponibles",
    "cupones_generados",
    "generar_cupones",
    "medicos_tratantes",
    "pacientes_del_medico",
    "resolver_cupon",
]
