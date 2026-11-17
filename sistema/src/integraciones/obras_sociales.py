"""Cliente de la API de obras sociales (módulo 6, grupo 9), según su contrato en
docs/apis/obras_sociales.md (OpenAPI en <OBRAS_SOCIALES_URL>/openapi.json).

- listar() → [ObraSocialEnApi(codigo, nombre, porcentaje, id_modulo)]
- alta_estudio(obra_social_id, nombre_paciente, fecha, referencia) → id de la solicitud (G22)
- estado_estudio(id) → RespuestaDelModulo(estado, porcentaje, motivo)
- presentar_demanda(id, pdf) → la solicitud vuelve a demanda_en_curso (E18)
- simular_autorizacion(id, porcentaje) y simular_rechazo(id, motivo): para probar, llaman a las
  URL de simulación que devuelve el módulo (hacen de la obra social)

La clave va en el header x-api-key (OBRAS_SOCIALES_KEY). Lanza ErrorDeIntegracion
(src/integraciones/base.py) con un mensaje para mostrar. Con USE_MOCKS=1 responde con
tests/fixtures/apis/obras_sociales/ (listar.json, alta_estudio.json, estado_estudio_<id>.json o
estado_estudio.json y presentar_demanda.json). Acepta `cliente=` para los tests.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from flask import current_app

from src.integraciones.base import CARPETA_DE_MOCKS, ClienteApi, Respuesta

NOMBRE = "La API de obras sociales"
# El módulo pagina de a 100 como máximo; hoy tiene 37 obras sociales.
POR_PAGINA = 100
PAGINAS_COMO_MAXIMO = 10


@dataclass(frozen=True)
class ObraSocialEnApi:
    # Código RNOS (Registro Nacional de Obras Sociales): es obras_sociales.codigo.
    codigo: str
    nombre: str
    # Porcentaje del presupuesto que cubre por defecto, de 0 a 100.
    porcentaje: Decimal
    # Id (UUID) de la obra social en el módulo: se manda al dar de alta la solicitud.
    id_modulo: str


class EstadoEnModulo(StrEnum):
    PENDIENTE = "pendiente"
    AUTORIZADA = "autorizada"
    RECHAZADA = "rechazada"
    # Rechazada con una demanda presentada: espera otra vez la respuesta.
    DEMANDA_EN_CURSO = "demanda_en_curso"


@dataclass(frozen=True)
class RespuestaDelModulo:
    estado: EstadoEnModulo
    # Solo si está autorizada. Puede no ser el de la lista: con una demanda puede cambiar.
    porcentaje: Decimal | None = None
    # Si está rechazada, el motivo que cargó la obra social.
    motivo: str | None = None


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("OBRAS_SOCIALES_KEY")
    cliente = ClienteApi(
        NOMBRE,
        config.get("OBRAS_SOCIALES_URL"),
        headers={"x-api-key": clave} if clave else None,
        usar_mocks=bool(config.get("USE_MOCKS")),
    )
    cliente.carpeta_de_mocks = CARPETA_DE_MOCKS / "obras_sociales"
    return cliente


def listar(*, cliente: ClienteApi | None = None) -> list[ObraSocialEnApi]:
    """E16.2: las obras sociales activas del módulo, con su porcentaje de cobertura."""
    cliente = cliente or cliente_por_defecto()
    obras: list[ObraSocialEnApi] = []
    pagina = 1
    while True:
        datos = cliente.get(
            "obras-sociales",
            mock="listar",
            params={"pagina": pagina, "por_pagina": POR_PAGINA},
        ).datos
        if not isinstance(datos, dict) or not isinstance(datos.get("datos"), list):
            raise cliente.formato_inesperado()
        obras += [_obra_social(item, cliente) for item in datos["datos"]]
        total_paginas = datos.get("total_paginas") or 1
        if cliente.usar_mocks or pagina >= min(total_paginas, PAGINAS_COMO_MAXIMO):
            break
        pagina += 1
    return sorted(obras, key=lambda obra: obra.nombre)


def _obra_social(item: Any, cliente: ClienteApi) -> ObraSocialEnApi:
    try:
        obra = ObraSocialEnApi(
            str(item["rnos_codigo"]).strip(),
            str(item["nombre"]).strip(),
            Decimal(str(item["porcentaje_cobertura"])),
            str(item["id"]).strip(),
        )
    except (KeyError, TypeError, InvalidOperation):
        raise cliente.formato_inesperado() from None
    if not obra.codigo or not obra.id_modulo or not 0 <= obra.porcentaje <= 100:
        raise cliente.formato_inesperado()
    return obra


def alta_estudio(
    obra_social_id: str,
    nombre_paciente: str,
    fecha: date,
    referencia: str,
    *,
    cliente: ClienteApi | None = None,
) -> str:
    """G22: da de alta la solicitud de autorización del estudio (POST /solicitudes).

    Van el id de la obra social en el módulo, el nombre del paciente, la fecha y el código del
    estudio como referencia: ni DNI ni datos clínicos. Devuelve el id de la solicitud.
    """
    cliente = cliente or cliente_por_defecto()
    cuerpo = {
        "obra_social_id": obra_social_id,
        "paciente_nombre": nombre_paciente,
        "fecha": fecha.isoformat(),
        "referencia_externa": referencia,
    }
    datos = cliente.post("solicitudes", mock="alta_estudio", json=cuerpo).datos
    return _solicitud(datos, cliente)[0]


def estado_estudio(id_solicitud: str, *, cliente: ClienteApi | None = None) -> RespuestaDelModulo:
    """G22: la respuesta de la obra social a la solicitud (GET /solicitudes/<id>)."""
    cliente = cliente or cliente_por_defecto()
    datos = cliente.get(
        f"solicitudes/{id_solicitud}",
        mock=[f"estado_estudio_{id_solicitud}", "estado_estudio"],
    ).datos
    return _solicitud(datos, cliente)[1]


def presentar_demanda(
    id_solicitud: str, pdf: bytes, *, cliente: ClienteApi | None = None
) -> RespuestaDelModulo:
    """E18 y G22: sube la resolución judicial como demanda sobre la solicitud rechazada
    (POST /solicitudes/<id>/demanda, PDF de hasta 5 MB en el campo `archivo`). La misma solicitud
    pasa a demanda_en_curso. Si no está rechazada, el módulo responde 409."""
    cliente = cliente or cliente_por_defecto()
    archivos = {"archivo": ("resolucion.pdf", pdf, "application/pdf")}
    # ClienteApi.post solo manda JSON; _pedir pasa `files` a httpx tal cual (multipart).
    respuesta: Respuesta = cliente._pedir(
        "POST", f"solicitudes/{id_solicitud}/demanda", "presentar_demanda", files=archivos
    )
    return _solicitud(respuesta.datos, cliente)[1]


def simular_autorizacion(
    id_solicitud: str, porcentaje: Decimal | None = None, *, cliente: ClienteApi | None = None
) -> RespuestaDelModulo:
    """Para probar: hace de la obra social y autoriza la solicitud con la URL de simulación.
    Sin porcentaje, el módulo usa el de la obra social."""
    cliente = cliente or cliente_por_defecto()
    url = _urls_de_simulacion(id_solicitud, cliente)["autorizar"]
    cuerpo = {"porcentaje": float(porcentaje)} if porcentaje is not None else None
    datos = cliente.post(url, mock="simular_autorizacion", json=cuerpo).datos
    return _solicitud(datos, cliente)[1]


def simular_rechazo(
    id_solicitud: str, motivo: str, *, cliente: ClienteApi | None = None
) -> RespuestaDelModulo:
    """Para probar: hace de la obra social y rechaza la solicitud con la URL de simulación."""
    cliente = cliente or cliente_por_defecto()
    url = _urls_de_simulacion(id_solicitud, cliente)["rechazar"]
    datos = cliente.post(url, mock="simular_rechazo", json={"motivo": motivo}).datos
    return _solicitud(datos, cliente)[1]


def _urls_de_simulacion(id_solicitud: str, cliente: ClienteApi) -> dict[str, str]:
    datos = cliente.get(
        f"solicitudes/{id_solicitud}",
        mock=[f"estado_estudio_{id_solicitud}", "estado_estudio"],
    ).datos
    urls = datos.get("urls_simulacion") if isinstance(datos, dict) else None
    if not isinstance(urls, dict) or not all(
        isinstance(urls.get(clave), str) for clave in ("autorizar", "rechazar")
    ):
        raise cliente.formato_inesperado()
    return urls


def _solicitud(datos: Any, cliente: ClienteApi) -> tuple[str, RespuestaDelModulo]:
    """El id y el estado de una Solicitud del contrato."""
    if not isinstance(datos, dict) or not datos.get("id"):
        raise cliente.formato_inesperado()
    try:
        estado = EstadoEnModulo(datos.get("estado"))
        porcentaje = datos.get("porcentaje_cobertura")
        porcentaje = Decimal(str(porcentaje)) if porcentaje is not None else None
    except (ValueError, InvalidOperation):
        raise cliente.formato_inesperado() from None
    motivo = datos.get("motivo_rechazo")
    motivo = str(motivo).strip() or None if motivo else None
    return str(datos["id"]), RespuestaDelModulo(estado, porcentaje, motivo)
