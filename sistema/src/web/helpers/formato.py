"""Filtros de Jinja para mostrar datos con el formato de Argentina.

{{ aviso.creada_en | fecha_hora }}   →  16/11/2026 14:05
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")


def fecha_hora(valor: datetime | None) -> str:
    """Fecha y hora en la zona horaria de Argentina. Vacío si no hay valor."""
    if valor is None:
        return ""
    return valor.astimezone(ZONA_HORARIA).strftime("%d/%m/%Y %H:%M")


def init_app(app: Flask) -> None:
    app.add_template_filter(fecha_hora)
