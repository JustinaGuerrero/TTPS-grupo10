"""Cliente de la API de obras sociales (módulo 6), según el borrador docs/apis/obras_sociales.md.

El contrato todavía no está publicado: este cliente asume la interfaz del borrador, marcada
provisoria. Cuando llegue el contrato real, cambia solo este archivo.

- listar() → [ObraSocialEnApi(codigo, nombre, porcentaje)]
- alta_estudio(codigo_obra_social, nombre_paciente, fecha) → id del estudio en el módulo (G22)
- estado_estudio(id) → RespuestaDelModulo(estado, motivo): pendiente, autorizado o rechazado

Lanza ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar. Con
USE_MOCKS=1 responde con tests/fixtures/apis/obras_sociales/ (listar.json, alta_estudio.json y
estado_estudio_<id>.json o, si no hay, estado_estudio.json). Acepta `cliente=` para los tests.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from flask import current_app

from src.integraciones.base import CARPETA_DE_MOCKS, ClienteApi

NOMBRE = "La API de obras sociales"


@dataclass(frozen=True)
class ObraSocialEnApi:
    codigo: str
    nombre: str
    # Porcentaje del presupuesto que cubre, de 0 a 100.
    porcentaje: Decimal


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("OBRAS_SOCIALES_KEY")
    cliente = ClienteApi(
        NOMBRE,
        config.get("OBRAS_SOCIALES_URL"),
        headers={"apikey": clave} if clave else None,
        usar_mocks=bool(config.get("USE_MOCKS")),
    )
    cliente.carpeta_de_mocks = CARPETA_DE_MOCKS / "obras_sociales"
    return cliente


def listar(*, cliente: ClienteApi | None = None) -> list[ObraSocialEnApi]:
    """E16.2: las obras sociales con las que trabaja el laboratorio y su porcentaje de cobertura."""
    cliente = cliente or cliente_por_defecto()
    datos = cliente.get("obras_sociales", mock="listar").datos
    if not isinstance(datos, list):
        raise cliente.formato_inesperado()
    try:
        obras = [
            ObraSocialEnApi(
                str(item["codigo"]).strip(),
                str(item["nombre"]).strip(),
                Decimal(str(item["porcentaje_cobertura"])),
            )
            for item in datos
        ]
    except (KeyError, TypeError, InvalidOperation):
        raise cliente.formato_inesperado() from None
    if any(not o.codigo or not 0 <= o.porcentaje <= 100 for o in obras):
        raise cliente.formato_inesperado()
    return sorted(obras, key=lambda obra: obra.nombre)


class EstadoEnModulo(StrEnum):
    PENDIENTE = "pendiente"
    AUTORIZADO = "autorizado"
    RECHAZADO = "rechazado"


@dataclass(frozen=True)
class RespuestaDelModulo:
    estado: EstadoEnModulo
    # El motivo que cargó la obra social al rechazar, si lo cargó.
    motivo: str | None = None


def alta_estudio(
    codigo_obra_social: str,
    nombre_paciente: str,
    fecha: date,
    *,
    cliente: ClienteApi | None = None,
) -> str:
    """G22: da de alta el estudio en el módulo, para que la obra social lo autorice o lo rechace
    en su web. Solo van la obra social, el nombre del paciente y la fecha: ni DNI ni datos
    clínicos. Devuelve el id del estudio en el módulo."""
    cliente = cliente or cliente_por_defecto()
    cuerpo = {
        "obra_social": codigo_obra_social,
        "paciente": nombre_paciente,
        "fecha": fecha.isoformat(),
    }
    datos = cliente.post("estudios", mock="alta_estudio", json=cuerpo).datos
    id_estudio = datos.get("id") if isinstance(datos, dict) else None
    if not isinstance(id_estudio, str | int) or isinstance(id_estudio, bool) or not str(id_estudio):
        raise cliente.formato_inesperado()
    return str(id_estudio)


def estado_estudio(id_estudio: str, *, cliente: ClienteApi | None = None) -> RespuestaDelModulo:
    """G22: la respuesta de la obra social a un estudio dado de alta en el módulo."""
    cliente = cliente or cliente_por_defecto()
    datos = cliente.get(
        f"estudios/{id_estudio}", mock=[f"estado_estudio_{id_estudio}", "estado_estudio"]
    ).datos
    if not isinstance(datos, dict):
        raise cliente.formato_inesperado()
    try:
        estado = EstadoEnModulo(datos.get("estado"))
    except ValueError:
        raise cliente.formato_inesperado() from None
    motivo = datos.get("motivo")
    return RespuestaDelModulo(estado, str(motivo).strip() or None if motivo else None)
