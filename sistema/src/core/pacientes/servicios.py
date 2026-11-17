"""Integraciones posteriores al alta del paciente (familiograma y archivo de audio)."""

import logging

from src.core.auditoria import Accion, Entidad, registrar
from src.core.pacientes.modelos import Paciente
from src.integraciones import familiograma, storage
from src.integraciones.base import ErrorDeIntegracion

log = logging.getLogger(__name__)


def reintentar_familiograma(paciente: Paciente) -> bool:
    """Pide y guarda el PDF del familiograma. Lanza ErrorDeIntegracion ante una falla."""
    if not paciente.familiares:
        return False
    contenido = familiograma.generar(
        [
            {
                "parentesco": fila.parentesco,
                "nombre": fila.nombre,
                "sintomas": [
                    {"codigo": sintoma.termino.codigo, "termino": sintoma.termino.termino}
                    for sintoma in fila.sintomas
                ],
                "patologias": [
                    fila_patologia.patologia.nombre for fila_patologia in fila.patologias
                ],
            }
            for fila in paciente.familiares
        ]
    )
    ruta = storage.subir(f"pacientes/{paciente.id}/familiograma.pdf", contenido, reemplazar=True)
    anterior = paciente.familiograma_path
    paciente.familiograma_path = ruta
    registrar(
        Entidad.PACIENTE,
        paciente.id,
        None,
        Accion.MODIFICACION,
        {"familiograma_path": (anterior, ruta)},
    )
    return True


def guardar_audio(paciente: Paciente, contenido: bytes) -> bool:
    """Guarda el audio original del resumen sin impedir el alta si Storage no está disponible."""
    if not contenido:
        return False
    try:
        ruta = storage.subir(
            f"pacientes/{paciente.id}/resumen-audio.webm",
            contenido,
            tipo="audio/webm",
            reemplazar=True,
        )
    except ErrorDeIntegracion:
        log.exception("No se pudo guardar el audio del resumen del paciente %s", paciente.id)
        return False
    anterior = paciente.resumen_audio_path
    paciente.resumen_audio_path = ruta
    registrar(
        Entidad.PACIENTE,
        paciente.id,
        None,
        Accion.MODIFICACION,
        {"resumen_audio_path": (anterior, ruta)},
    )
    return True
