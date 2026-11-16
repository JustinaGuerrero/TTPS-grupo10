"""Cliente base para las APIs externas (decisión S10).

Cada API tiene su módulo en src/integraciones/<api>.py, que arma un ClienteApi y expone
funciones con nombres del dominio. El cliente base resuelve lo común:

- Timeout de 5 segundos en cada pedido.
- Cualquier falla (sin respuesta, sin conexión, error HTTP, respuesta que no es JSON) se
  convierte en ErrorDeIntegracion, cuyo `mensaje` se puede mostrar tal cual en pantalla.
- Modo mock (USE_MOCKS=1): no llama a la API y lee la respuesta de
  tests/fixtures/apis/<api>/<clave>.json. Si existe <clave>.error.json, con
  {"status": 400, "message": "..."}, simula ese error.

Un controlador que usa una integración atrapa ErrorDeIntegracion y muestra `error.mensaje`:

    try:
        genes = apigen.genes_de_patologia("POMPE")
    except ErrorDeIntegracion as error:
        flash(error.mensaje, "error")
"""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

TIMEOUT_EN_SEGUNDOS = 5.0
CARPETA_DE_MOCKS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "apis"

log = logging.getLogger(__name__)


class ErrorDeIntegracion(Exception):
    """Falla al usar una API externa. `mensaje` es legible para el usuario."""

    def __init__(self, api: str, mensaje: str, status: int | None = None) -> None:
        super().__init__(mensaje)
        self.api = api
        self.mensaje = mensaje
        # Código HTTP de la respuesta, o None si no hubo respuesta.
        self.status = status


@dataclass(frozen=True)
class Respuesta:
    datos: Any
    headers: Mapping[str, str] = field(default_factory=dict)


class ClienteApi:
    """Hace los pedidos a una API y convierte sus fallas en ErrorDeIntegracion.

    `nombre` es el de la API para los mensajes ("Apigen") y la carpeta de sus mocks en
    minúsculas (tests/fixtures/apis/apigen). `transport` es para los tests: un
    httpx.MockTransport responde sin salir a la red.
    """

    def __init__(
        self,
        nombre: str,
        url_base: str | None,
        headers: Mapping[str, str] | None = None,
        usar_mocks: bool = False,
        timeout: float = TIMEOUT_EN_SEGUNDOS,
        carpeta_de_mocks: Path = CARPETA_DE_MOCKS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.nombre = nombre
        self.url_base = url_base
        self.headers = dict(headers or {})
        self.usar_mocks = usar_mocks
        self.timeout = timeout
        self.carpeta_de_mocks = carpeta_de_mocks / nombre.lower()
        self.transport = transport

    def get(
        self,
        ruta: str,
        *,
        mock: str | Sequence[str],
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Respuesta:
        return self._pedir("GET", ruta, mock, params=params, headers=headers)

    def post(
        self,
        ruta: str,
        *,
        mock: str | Sequence[str],
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Respuesta:
        return self._pedir("POST", ruta, mock, json=json, headers=headers)

    def error(self, mensaje: str, status: int | None = None) -> ErrorDeIntegracion:
        return ErrorDeIntegracion(self.nombre, mensaje, status)

    def formato_inesperado(self) -> ErrorDeIntegracion:
        """Para los módulos de cada API cuando la respuesta no tiene la forma del contrato."""
        log.error("%s respondió con un formato que no es el del contrato", self.nombre)
        return self.error(f"{self.nombre} respondió con datos que el sistema no entiende.")

    # ------------------------------------------------------------------ pedidos reales

    def _pedir(self, metodo: str, ruta: str, mock: str | Sequence[str], **opciones) -> Respuesta:
        if self.usar_mocks:
            return self._leer_mock(mock)
        if not self.url_base:
            raise self.error(f"Falta configurar la URL de {self.nombre}.")

        try:
            with httpx.Client(
                base_url=self.url_base,
                headers=self.headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as cliente:
                respuesta = cliente.request(metodo, ruta, **opciones)
        except httpx.TimeoutException:
            log.warning("%s no respondió en %s s: %s %s", self.nombre, self.timeout, metodo, ruta)
            raise self.error(
                f"{self.nombre} no respondió a tiempo. Probá de nuevo en unos minutos."
            ) from None
        except httpx.TransportError as error:
            log.warning("Sin conexión con %s (%s %s): %s", self.nombre, metodo, ruta, error)
            raise self.error(
                f"No se pudo conectar con {self.nombre}. Probá de nuevo en unos minutos."
            ) from None

        if respuesta.is_error:
            raise self._error_http(respuesta.status_code, _mensaje_de(respuesta))
        try:
            datos = respuesta.json()
        except ValueError:
            raise self.formato_inesperado() from None
        return Respuesta(datos, respuesta.headers)

    def _error_http(self, status: int, mensaje_de_la_api: str | None) -> ErrorDeIntegracion:
        log.warning("%s respondió %s: %s", self.nombre, status, mensaje_de_la_api)
        if status in (401, 403):
            mensaje = f"{self.nombre} rechazó la clave de acceso del sistema."
        elif status >= 500:
            mensaje = f"{self.nombre} tuvo un error interno. Probá de nuevo en unos minutos."
        elif mensaje_de_la_api:
            # Los 400 de las APIs traen el texto para mostrar, por ejemplo
            # "Patología inexistente: XYZ".
            mensaje = mensaje_de_la_api
        else:
            mensaje = f"{self.nombre} respondió con un error ({status})."
        return self.error(mensaje, status)

    # ------------------------------------------------------------------------- mocks

    def _leer_mock(self, claves: str | Sequence[str]) -> Respuesta:
        """Lee la primera clave que tenga archivo: <clave>.json o <clave>.error.json."""
        if isinstance(claves, str):
            claves = [claves]
        for clave in claves:
            nombre = _nombre_de_archivo(clave)
            error = self.carpeta_de_mocks / f"{nombre}.error.json"
            if error.is_file():
                contenido = _leer_json(error)
                raise self._error_http(int(contenido.get("status", 400)), contenido.get("message"))
            archivo = self.carpeta_de_mocks / f"{nombre}.json"
            if archivo.is_file():
                return Respuesta(_leer_json(archivo))
        raise self.error(
            f"No hay respuesta simulada de {self.nombre} para «{claves[0]}» "
            f"(USE_MOCKS=1; ver {self.carpeta_de_mocks})."
        )


def _mensaje_de(respuesta: httpx.Response) -> str | None:
    """El texto del cuerpo de error: `message` (PostgREST) o `detail` cuando es un texto (chatbot)."""
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return None
    if not isinstance(cuerpo, dict):
        return None
    for clave in ("message", "detail"):
        if isinstance(cuerpo.get(clave), str):
            return cuerpo[clave]
    return None


def _nombre_de_archivo(clave: str) -> str:
    """Una clave de mock como nombre de archivo seguro: solo letras, números, _ y -."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", clave)


def _leer_json(archivo: Path) -> Any:
    return json.loads(archivo.read_text(encoding="utf-8"))
