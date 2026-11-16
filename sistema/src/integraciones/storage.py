"""Archivos en un bucket privado de Supabase Storage: PDFs de resultados, órdenes, familiogramas…

    from src.integraciones import storage

    ruta = storage.subir(f"estudios/{estudio.id}/resultado.pdf", contenido_pdf)
    estudio.resultado_path = ruta          # en la base se guarda la ruta, no el archivo
    pdf = storage.bajar(estudio.resultado_path)

Como el resto de las integraciones (src/integraciones/base.py): timeout de 5 s, cualquier falla
se convierte en ErrorDeIntegracion con un mensaje para mostrar, y con USE_MOCKS=1 no llama a
Supabase: guarda y lee los archivos en instance/storage/ (o en STORAGE_CARPETA_MOCK).

Configuración: SUPABASE_URL, SUPABASE_KEY (clave de servicio, solo en .env) y SUPABASE_BUCKET.
"""

import logging
import re
from pathlib import Path

import httpx
from flask import current_app
from storage3.exceptions import StorageApiError
from supabase import ClientOptions, create_client

from src.integraciones.base import TIMEOUT_EN_SEGUNDOS, ErrorDeIntegracion

NOMBRE = "Supabase Storage"
BUCKET_POR_DEFECTO = "documentos"
TIPO_POR_DEFECTO = "application/pdf"

# Segmentos con letras, números, punto, guion y guion bajo, separados por "/": "estudios/42/a.pdf".
# Nada de "..", rutas absolutas ni barras invertidas, que podrían salirse de la carpeta del mock.
_RUTA_VALIDA = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9_-][A-Za-z0-9._-]*)*")

log = logging.getLogger(__name__)


def subir(
    ruta: str, contenido: bytes, tipo: str = TIPO_POR_DEFECTO, *, reemplazar: bool = False
) -> str:
    """Guarda `contenido` en `ruta` dentro del bucket y devuelve la ruta, para guardarla en la base.

    Si ya hay un archivo en esa ruta, da error salvo que `reemplazar` sea True.
    """
    ruta = _validar(ruta)
    if _usar_mocks():
        archivo = _carpeta_mock() / ruta
        if archivo.exists() and not reemplazar:
            raise _error(f"Ya hay un archivo en {ruta}.")
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)
        return ruta

    opciones = {"content-type": tipo, "upsert": "true" if reemplazar else "false"}
    _pedir(lambda bucket: bucket.upload(ruta, contenido, opciones), ruta)
    return ruta


def bajar(ruta: str) -> bytes:
    """El contenido del archivo guardado en `ruta`."""
    ruta = _validar(ruta)
    if _usar_mocks():
        archivo = _carpeta_mock() / ruta
        if not archivo.is_file():
            raise _error(f"No existe el archivo {ruta}.", 404)
        return archivo.read_bytes()
    return _pedir(lambda bucket: bucket.download(ruta), ruta)


# ---------------------------------------------------------------------------------------------


def _pedir(accion, ruta: str):
    config = current_app.config
    if not config.get("SUPABASE_URL") or not config.get("SUPABASE_KEY"):
        raise _error(f"Falta configurar {NOMBRE} (SUPABASE_URL y SUPABASE_KEY).")
    try:
        cliente = create_client(
            config["SUPABASE_URL"],
            config["SUPABASE_KEY"],
            options=ClientOptions(storage_client_timeout=int(TIMEOUT_EN_SEGUNDOS)),
        )
        bucket = cliente.storage.from_(config.get("SUPABASE_BUCKET") or BUCKET_POR_DEFECTO)
        return accion(bucket)
    except httpx.TimeoutException:
        log.warning("%s no respondió en %s s (%s)", NOMBRE, TIMEOUT_EN_SEGUNDOS, ruta)
        raise _error(f"{NOMBRE} no respondió a tiempo. Probá de nuevo en unos minutos.") from None
    except httpx.TransportError as error:
        log.warning("Sin conexión con %s (%s): %s", NOMBRE, ruta, error)
        raise _error(f"No se pudo conectar con {NOMBRE}. Probá de nuevo en unos minutos.") from None
    except StorageApiError as error:
        log.warning("%s respondió un error para %s: %s", NOMBRE, ruta, error)
        status = _status(error)
        if status == 404:
            raise _error(f"No existe el archivo {ruta}.", 404) from None
        if status == 409:
            raise _error(f"Ya hay un archivo en {ruta}.", 409) from None
        if status in (401, 403):
            raise _error(f"{NOMBRE} rechazó la clave de acceso del sistema.", status) from None
        raise _error(f"{NOMBRE} respondió con un error. Probá de nuevo en unos minutos.") from None
    except Exception:
        # Cualquier otra falla de la librería: que no rompa la pantalla que la usa.
        log.exception("Falla inesperada de %s (%s)", NOMBRE, ruta)
        raise _error(
            f"{NOMBRE} tuvo un error inesperado. Probá de nuevo en unos minutos."
        ) from None


def _validar(ruta: str) -> str:
    ruta = (ruta or "").strip()
    if not _RUTA_VALIDA.fullmatch(ruta) or ".." in ruta.split("/"):
        raise ValueError(f"Ruta de archivo inválida: {ruta!r}")
    return ruta


def _usar_mocks() -> bool:
    return bool(current_app.config.get("USE_MOCKS"))


def _carpeta_mock() -> Path:
    carpeta = current_app.config.get("STORAGE_CARPETA_MOCK")
    return Path(carpeta) if carpeta else Path(current_app.instance_path) / "storage"


def _status(error: StorageApiError) -> int | None:
    try:
        return int(getattr(error, "status", None) or 0) or None
    except (TypeError, ValueError):
        return None


def _error(mensaje: str, status: int | None = None) -> ErrorDeIntegracion:
    return ErrorDeIntegracion(NOMBRE, mensaje, status)
