"""Registro de cambios (E43, G16): quién cambió qué de un paciente, un estudio o un sample set.

- modelos.py    RegistroDeCambio (tabla auditoria), Entidad y Accion.
- servicios.py  registrar() y diferencias(), que llaman las funciones de core que cambian datos.
- consultas.py  historial_de() de una entidad y listar() con filtros y páginas.

Regla para todo core: una función que cambia datos de un paciente, un estudio (aparte del estado)
o un sample set llama a registrar() en la misma transacción. registrar() no hace commit.
Este módulo no importa a los de pacientes ni estudios, que lo llaman a él.
"""

from src.core.auditoria.consultas import (
    REGISTROS_POR_PAGINA,
    USUARIO_SISTEMA,
    Cambio,
    FiltrosDeAuditoria,
    hay_registros_de,
    historial_de,
    listar,
    usuarios_con_registros,
)
from src.core.auditoria.modelos import Accion, Entidad, RegistroDeCambio
from src.core.auditoria.servicios import (
    FRAGMENTOS_SENSIBLES,
    como_texto,
    diferencias,
    es_campo_sensible,
    registrar,
)

__all__ = [
    "FRAGMENTOS_SENSIBLES",
    "REGISTROS_POR_PAGINA",
    "USUARIO_SISTEMA",
    "Accion",
    "Cambio",
    "Entidad",
    "FiltrosDeAuditoria",
    "RegistroDeCambio",
    "como_texto",
    "diferencias",
    "es_campo_sensible",
    "hay_registros_de",
    "historial_de",
    "listar",
    "registrar",
    "usuarios_con_registros",
]
