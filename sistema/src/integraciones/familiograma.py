"""Generación del familiograma. Contrato provisorio; ver docs/apis/familiograma.md."""

import base64
import binascii
from collections.abc import Mapping, Sequence

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "Familiograma"


def cliente_por_defecto() -> ClienteApi:
    return ClienteApi(
        NOMBRE,
        current_app.config.get("FAMILIOGRAMA_URL"),
        usar_mocks=bool(current_app.config.get("USE_MOCKS")),
    )


def generar(familiares: Sequence[Mapping], *, cliente: ClienteApi | None = None) -> bytes:
    if not familiares:
        raise ValueError("El familiograma requiere al menos un familiar.")
    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.post(
        "generar",
        json={"familiares": list(familiares)},
        mock="generar",
    )
    archivo = respuesta.datos.get("pdf_base64") if isinstance(respuesta.datos, dict) else None
    try:
        contenido = base64.b64decode(archivo, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise cliente.formato_inesperado() from None
    if not contenido.startswith(b"%PDF-"):
        raise cliente.formato_inesperado()
    return contenido
