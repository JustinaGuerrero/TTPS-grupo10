"""Cliente del chatbot de pacientes (módulo externo de GenLab), según docs/apis/chatbot.md.

    respuesta = chatbot.preguntar("¿Qué es un exoma clínico?")
    respuesta.texto            # se muestra tal cual, sea cual sea el tipo
    respuesta.conversacion_id  # se manda en la próxima pregunta para seguir la conversación

El sistema no guarda las conversaciones: solo el controlador conserva el conversacion_id en la
sesión del usuario para que el chatbot entienda las repreguntas.

Como el resto de las integraciones (src/integraciones/base.py), cualquier falla se convierte en
ErrorDeIntegracion con un mensaje para el paciente, y con USE_MOCKS=1 responde con
tests/fixtures/apis/chatbot/respuesta.json. Diferencias con las demás APIs:

- Timeout de 20 s y no de 5 s (decisión S18): el chatbot usa IA y el contrato lo recomienda.
- Los errores de configuración (401) no se le muestran al paciente: se loguean y el paciente ve
  que el chatbot no está disponible. Un 503 muestra el `detail` del chatbot tal cual.
- Un 429 no se reintenta solo: el paciente ve que tiene que esperar y vuelve a preguntar.

Configuración: CHATBOT_URL, CHATBOT_APIKEY (header apikey) y CHATBOT_TOKEN (header
x-chatbot-token, solo en .env: es el token de nuestro grupo y nunca va al navegador).
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

from flask import current_app

from src.integraciones.base import ClienteApi, ErrorDeIntegracion

NOMBRE = "Chatbot"
TIMEOUT_EN_SEGUNDOS = 20.0
LARGO_MAXIMO_DE_LA_PREGUNTA = 1000
LARGO_MAXIMO_DEL_ID = 200

NO_DISPONIBLE = "El chatbot no está disponible en este momento. Probá de nuevo en unos minutos."
DEMASIADAS_PREGUNTAS = "Hiciste muchas preguntas seguidas. Esperá un minuto y probá de nuevo."
APAGADO = "El chatbot está apagado por el momento. Probá de nuevo más tarde."
PREGUNTA_RECHAZADA = "El chatbot no aceptó la pregunta. Revisá que tenga hasta 1000 caracteres."

log = logging.getLogger(__name__)


class TipoDeRespuesta(StrEnum):
    """Los cuatro `tipo` del contrato. En todos se muestra el texto de la respuesta tal cual."""

    RESPUESTA = "respuesta"
    FUERA_DE_ALCANCE = "fuera_de_alcance"
    # Pide diagnóstico, interpretar un resultado o habla de síntomas o tratamientos: no se ofrece
    # contacto con el laboratorio.
    DERIVAR_MEDICO = "derivar_medico"
    SIN_INFORMACION = "sin_informacion"


@dataclass(frozen=True)
class RespuestaDelChatbot:
    texto: str
    conversacion_id: str | None
    tipo: TipoDeRespuesta


class PreguntaInvalida(ValueError):
    """La pregunta no cumple el contrato (vacía o de más de 1000 caracteres). No se manda."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class ClienteChatbot(ClienteApi):
    """ClienteApi con los mensajes de error que pide el contrato del chatbot."""

    def _error_http(self, status: int, mensaje_de_la_api: str | None) -> ErrorDeIntegracion:
        if status in (401, 403):
            log.error(
                "El chatbot rechazó CHATBOT_APIKEY o CHATBOT_TOKEN (%s): revisar .env", status
            )
            return self.error(NO_DISPONIBLE, status)
        log.warning("El chatbot respondió %s: %s", status, mensaje_de_la_api)
        if status == 422:
            return self.error(PREGUNTA_RECHAZADA, status)
        if status == 429:
            return self.error(DEMASIADAS_PREGUNTAS, status)
        if status == 503:
            # El contrato pide mostrar el detail tal cual.
            return self.error(mensaje_de_la_api or APAGADO, status)
        return self.error(NO_DISPONIBLE, status)


def cliente_por_defecto() -> ClienteChatbot:
    config = current_app.config
    return ClienteChatbot(
        NOMBRE,
        config.get("CHATBOT_URL"),
        headers={
            "apikey": config.get("CHATBOT_APIKEY") or "",
            "x-chatbot-token": config.get("CHATBOT_TOKEN") or "",
        },
        usar_mocks=bool(config.get("USE_MOCKS")),
        timeout=TIMEOUT_EN_SEGUNDOS,
    )


def validar_pregunta(texto: str | None) -> str:
    """La pregunta sin espacios en los extremos. Lanza PreguntaInvalida si no cumple el contrato."""
    pregunta = (texto or "").strip()
    if not pregunta:
        raise PreguntaInvalida("Escribí tu pregunta.")
    if len(pregunta) > LARGO_MAXIMO_DE_LA_PREGUNTA:
        raise PreguntaInvalida(
            f"La pregunta puede tener hasta {LARGO_MAXIMO_DE_LA_PREGUNTA} caracteres "
            f"(tiene {len(pregunta)})."
        )
    return pregunta


def preguntar(
    texto: str,
    conversacion_id: str | None = None,
    *,
    cliente: ClienteApi | None = None,
) -> RespuestaDelChatbot:
    """Le hace la pregunta al chatbot y devuelve su respuesta (E40, episodios 2 y 3).

    `conversacion_id` es el de la respuesta anterior, para seguir la misma conversación; sin él
    el chatbot abre una nueva. Lanza PreguntaInvalida sin llamar al chatbot si la pregunta está
    vacía o es muy larga, y ErrorDeIntegracion con un mensaje para el paciente si el chatbot
    falla o no responde.
    """
    pregunta = validar_pregunta(texto)
    if conversacion_id is not None and not (0 < len(conversacion_id) <= LARGO_MAXIMO_DEL_ID):
        conversacion_id = None
    cliente = cliente or cliente_por_defecto()
    try:
        # CHATBOT_URL es el endpoint completo: el pedido va a esa URL, sin ruta agregada.
        respuesta = cliente.post(
            cliente.url_base or "",
            json={"mensaje": pregunta, "conversacion_id": conversacion_id},
            mock="respuesta",
        )
    except ErrorDeIntegracion as error:
        if error.status is not None:
            raise
        # Sin respuesta, sin conexión o con datos fuera del contrato: el detalle queda en el log.
        log.warning("Falla del chatbot: %s", error.mensaje)
        raise ErrorDeIntegracion(NOMBRE, NO_DISPONIBLE) from None
    return _respuesta_de(respuesta.datos)


def _respuesta_de(datos) -> RespuestaDelChatbot:
    if not isinstance(datos, dict):
        return _formato_inesperado()
    texto = datos.get("respuesta")
    conversacion_id = datos.get("conversacion_id")
    if not isinstance(texto, str) or not texto.strip():
        return _formato_inesperado()
    if conversacion_id is not None and not isinstance(conversacion_id, str):
        return _formato_inesperado()
    try:
        tipo = TipoDeRespuesta(datos.get("tipo"))
    except ValueError:
        # Un tipo nuevo no impide mostrar la respuesta, que en todos los casos va tal cual.
        log.warning("El chatbot devolvió un tipo desconocido: %r", datos.get("tipo"))
        tipo = TipoDeRespuesta.RESPUESTA
    return RespuestaDelChatbot(texto, conversacion_id, tipo)


def _formato_inesperado():
    log.error("El chatbot respondió con un formato que no es el del contrato")
    raise ErrorDeIntegracion(NOMBRE, NO_DISPONIBLE)
