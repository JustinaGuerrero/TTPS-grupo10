"""Notificaciones (decisión S11, E39): el aviso en la lista de pendientes y el mail.

Cualquier escenario que tenga que avisarle algo a un usuario llama a notificar():

    from src.core.notificaciones import notificar

    notificar(
        medico,
        "Resultado disponible",
        f"El estudio {estudio.codigo} ya tiene resultado.",
        url_for("estudios.ver", estudio_id=estudio.id),
        estudio=estudio,
    )
    db.session.commit()
"""

from src.core.notificaciones.modelos import Aviso
from src.core.notificaciones.servicios import (
    AVISOS_POR_PAGINA,
    avisos_de,
    contar_sin_leer,
    marcar_leido,
    notificar,
)

__all__ = [
    "AVISOS_POR_PAGINA",
    "Aviso",
    "avisos_de",
    "contar_sin_leer",
    "marcar_leido",
    "notificar",
]
