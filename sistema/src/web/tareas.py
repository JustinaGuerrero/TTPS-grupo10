"""Tareas programadas con APScheduler (S12): lo que el sistema hace solo, a una hora fija.

Cada issue agrega su tarea a TAREAS con una línea (es un registro de una línea: solo se agregan):

    Tarea("recordatorios_de_turno", enviar_recordatorios, {"day_of_week": "mon-fri", "hour": 10}),

`funcion` no recibe argumentos y corre dentro de un app_context. No hace commit: ejecutar()
confirma si termina bien y hace rollback si falla. `cuando` son los argumentos de CronTrigger
(day_of_week, hour, minute…), en hora de Argentina.

El planificador no arranca en los tests ni en los comandos de consola (flask seeds, flask demo…):
solo en el proceso que atiende la app. Con `flask run --debug` arranca en el proceso hijo del
recargador, para que cada tarea no corra dos veces. Para correr una tarea a mano sin esperar la
hora: `flask tarea <id>`.
"""

import atexit
import os
from collections.abc import Callable
from typing import Any, NamedTuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask

from src.core.calendario import ZONA_HORARIA
from src.core.database import db
from src.core.muestras import procesar_inasistencias
from src.core.turnos import enviar_recordatorios


class Tarea(NamedTuple):
    id: str
    funcion: Callable[[], Any]
    cuando: dict[str, Any]


# Tareas del sistema. #7 agrega los recordatorios de turno, #8 las inasistencias y #13 la orden
# del día.
TAREAS: list[Tarea] = [
    # E21: los días hábiles a las 10, el recordatorio de los turnos del próximo día hábil.
    Tarea("recordatorios_de_turno", enviar_recordatorios, {"day_of_week": "mon-fri", "hour": 10}),
    # O7: los días hábiles a las 18:30, libera los turnos del día sin mensaje de muestra tomada.
    Tarea(
        "inasistencias",
        procesar_inasistencias,
        {"day_of_week": "mon-fri", "hour": 18, "minute": 30},
    ),
]

_planificador: BackgroundScheduler | None = None


def buscar_tarea(tarea_id: str) -> Tarea | None:
    return next((tarea for tarea in TAREAS if tarea.id == tarea_id), None)


def ejecutar(app: Flask, tarea: Tarea) -> Any:
    """Corre la tarea en un app_context: commit si termina bien, rollback y log si falla."""
    with app.app_context():
        try:
            resultado = tarea.funcion()
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Falló la tarea programada %s", tarea.id)
            raise
        return resultado


def debe_arrancar(app: Flask) -> bool:
    """True solo en el proceso que atiende la app (ver el docstring del módulo)."""
    if app.testing:
        return False
    if app.debug:
        # El recargador de `flask run --debug` marca así al proceso hijo, que es el que atiende.
        # Los comandos de consola en desarrollo no la tienen.
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    return True


def init_app(app: Flask) -> None:
    global _planificador
    if _planificador is not None or not debe_arrancar(app):
        return
    planificador = BackgroundScheduler(timezone=ZONA_HORARIA)
    for tarea in TAREAS:
        planificador.add_job(
            ejecutar,
            CronTrigger(timezone=ZONA_HORARIA, **tarea.cuando),
            args=[app, tarea],
            id=tarea.id,
            # Si la app estuvo apagada a la hora de la tarea, corre una sola vez al volver.
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
    planificador.start()
    atexit.register(lambda: planificador.shutdown(wait=False))
    _planificador = planificador
    app.logger.info("Tareas programadas: %s", ", ".join(t.id for t in TAREAS) or "ninguna")
