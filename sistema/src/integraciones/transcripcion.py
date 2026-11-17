"""Transcripción de audio del resumen clínico. Contrato provisorio; ver docs/apis/transcripcion.md."""

import base64

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "Transcripcion"


def cliente_por_defecto() -> ClienteApi:
    return ClienteApi(
        NOMBRE,
        current_app.config.get("TRANSCRIPCION_URL"),
        usar_mocks=bool(current_app.config.get("USE_MOCKS")),
    )


def transcribir(audio: bytes, *, cliente: ClienteApi | None = None) -> str:
    if not audio:
        raise ValueError("El audio está vacío.")
    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.post(
        "transcribir",
        json={"audio_base64": base64.b64encode(audio).decode("ascii")},
        mock="transcribir",
    )
    texto = respuesta.datos.get("texto") if isinstance(respuesta.datos, dict) else None
    if not isinstance(texto, str) or not texto.strip():
        raise cliente.formato_inesperado()
    return texto.strip()
