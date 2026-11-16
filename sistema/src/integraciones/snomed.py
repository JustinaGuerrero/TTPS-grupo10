"""Cliente del módulo SNOMED (búsqueda de términos), según docs/apis/snomed.md (borrador).

Función que usa el sistema:

- buscar_terminos("fieb", "sintoma")  → [TerminoSnomed("386661006", "Fiebre"), ...]

Lanza ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar si el módulo
no responde, rechaza el pedido o devuelve algo fuera del contrato. Con USE_MOCKS=1 responde con
tests/fixtures/apis/snomed/terminos_<tipo>.json.

Si no se pasa `cliente=`, se arma con SNOMED_URL, SNOMED_KEY y USE_MOCKS de la configuración.
"""

from dataclasses import dataclass

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "SNOMED"
TIPOS = ("sintoma", "especialidad")
MINIMO_DE_LETRAS = 3
LIMITE_POR_DEFECTO = 15


@dataclass(frozen=True)
class TerminoSnomed:
    codigo: str
    termino: str


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("SNOMED_KEY") or ""
    return ClienteApi(
        NOMBRE,
        config.get("SNOMED_URL"),
        headers={"apikey": clave} if clave else {},
        usar_mocks=bool(config.get("USE_MOCKS")),
    )


def buscar_terminos(
    texto: str,
    tipo: str = "sintoma",
    *,
    limite: int = LIMITE_POR_DEFECTO,
    cliente: ClienteApi | None = None,
) -> list[TerminoSnomed]:
    """Términos de SNOMED que coinciden con `texto`, para el buscador de síntomas (E07).

    Con menos de 3 letras devuelve una lista vacía sin llamar al módulo.
    Con USE_MOCKS=1 se devuelve terminos_<tipo>.json entero, sin filtrar por `texto`.
    """
    if tipo not in TIPOS:
        raise ValueError(f"El tipo va como {' o '.join(TIPOS)}.")
    texto = (texto or "").strip()
    if len(texto) < MINIMO_DE_LETRAS:
        return []

    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.get(
        "terminos",
        params={"q": texto, "tipo": tipo, "limite": limite},
        mock=f"terminos_{tipo}",
    )
    try:
        return [
            TerminoSnomed(codigo=str(fila["codigo"]), termino=str(fila["termino"]))
            for fila in respuesta.datos
        ]
    except (KeyError, TypeError):
        raise cliente.formato_inesperado() from None
