"""Franjas del turnero: turnos de 15 minutos, de lunes a viernes de 9 a 18 y sin feriados (E19).

La última franja empieza a las 17:45. Las horas son de Argentina.
"""

from datetime import date, datetime, time

from src.core.calendario import ZONA_HORARIA, es_dia_habil
from src.core.turnos.modelos import DURACION_DEL_TURNO

HORA_DE_APERTURA = time(9, 0)
HORA_DE_CIERRE = time(18, 0)


def franjas_del_dia(fecha: date) -> list[datetime]:
    """Las 36 franjas de un día, de 9:00 a 17:45, sin mirar si el día es hábil."""
    franja = datetime.combine(fecha, HORA_DE_APERTURA, tzinfo=ZONA_HORARIA)
    cierre = datetime.combine(fecha, HORA_DE_CIERRE, tzinfo=ZONA_HORARIA)
    franjas = []
    while franja < cierre:
        franjas.append(franja)
        franja += DURACION_DEL_TURNO
    return franjas


def es_franja_valida(inicio: datetime) -> bool:
    """True si `inicio` es el comienzo de una franja de un día hábil (no mira si está ocupada)."""
    local = inicio.astimezone(ZONA_HORARIA)
    return local in franjas_del_dia(local.date()) and es_dia_habil(local.date())
