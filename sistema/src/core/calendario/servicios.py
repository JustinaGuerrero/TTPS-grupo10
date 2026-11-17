"""Días hábiles del laboratorio: de lunes a viernes y fuera de feriados (E19, E21, E23, E30).

Las fechas y horas del circuito son de Argentina: un turno de las 9:00 es a las 9:00 de acá,
aunque la base guarde las horas en UTC.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from src.core.calendario.modelos import Feriado
from src.core.database import db

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")

# Un año sin días hábiles no existe: corta la búsqueda si la tabla de feriados quedó rota.
_MAXIMO_DE_DIAS_A_BUSCAR = 366


def ahora() -> datetime:
    """Fecha y hora actuales en Argentina. Los tests la reemplazan para fijar el día."""
    return datetime.now(ZONA_HORARIA)


def hoy() -> date:
    return ahora().date()


def es_feriado(fecha: date) -> bool:
    return db.session.get(Feriado, fecha) is not None


def feriados_entre(desde: date, hasta: date) -> set[date]:
    """Feriados entre `desde` y `hasta`, los dos incluidos."""
    consulta = sa.select(Feriado.fecha).where(Feriado.fecha.between(desde, hasta))
    return set(db.session.scalars(consulta))


def es_dia_habil(fecha: date) -> bool:
    """True de lunes a viernes, salvo los feriados."""
    return fecha.weekday() < 5 and not es_feriado(fecha)


def proximo_dia_habil(desde: date) -> date:
    """El primer día hábil después de `desde` (sin contar `desde`)."""
    fecha = desde
    for _ in range(_MAXIMO_DE_DIAS_A_BUSCAR):
        fecha += timedelta(days=1)
        if es_dia_habil(fecha):
            return fecha
    raise RuntimeError(f"No hay días hábiles en el año siguiente a {desde}: revisá los feriados.")


def dias_habiles(desde: date, cantidad: int) -> list[date]:
    """Los próximos `cantidad` días hábiles a partir de `desde` (incluido, si es hábil)."""
    feriados = feriados_entre(desde, desde + timedelta(days=cantidad * 2 + 30))
    dias = []
    fecha = desde
    while len(dias) < cantidad:
        if fecha.weekday() < 5 and fecha not in feriados:
            dias.append(fecha)
        fecha += timedelta(days=1)
    return dias
