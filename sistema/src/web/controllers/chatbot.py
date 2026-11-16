"""Controlador del chatbot de pacientes (E40). Solo entra el paciente.

El sistema no guarda las conversaciones: la página muestra la última pregunta y su respuesta, y
en la sesión (del servidor) queda solo el conversacion_id, para que el chatbot entienda las
repreguntas como «¿y cómo se hereda?». "Nueva conversación" lo borra.
"""

from flask import Blueprint, redirect, render_template, request, session, url_for

from src.core.usuarios import roles
from src.integraciones import chatbot
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

CLAVE_DE_CONVERSACION = "chatbot_conversacion_id"


@bp.get("")
@login_required
@rol_requerido(roles.PACIENTE)
def conversacion():
    return _pantalla()


@bp.post("")
@login_required
@rol_requerido(roles.PACIENTE)
def preguntar():
    """Episodios 1 a 3: el paciente pregunta, el sistema delega en el chatbot y muestra la respuesta."""
    pregunta = request.form.get("pregunta", "")
    try:
        respuesta = chatbot.preguntar(pregunta, session.get(CLAVE_DE_CONVERSACION))
    except chatbot.PreguntaInvalida as error:
        return _pantalla(pregunta=pregunta, error_de_pregunta=error.mensaje), 400
    except ErrorDeIntegracion as error:
        # La pregunta queda escrita para volver a enviarla cuando el chatbot responda.
        return _pantalla(pregunta=pregunta, error_del_chatbot=error.mensaje)

    if respuesta.conversacion_id:
        session[CLAVE_DE_CONVERSACION] = respuesta.conversacion_id
    return _pantalla(pregunta_enviada=pregunta.strip(), respuesta=respuesta)


@bp.post("/nueva")
@login_required
@rol_requerido(roles.PACIENTE)
def nueva_conversacion():
    session.pop(CLAVE_DE_CONVERSACION, None)
    return redirect(url_for("chatbot.conversacion"))


def _pantalla(
    pregunta: str = "",
    pregunta_enviada: str | None = None,
    respuesta: chatbot.RespuestaDelChatbot | None = None,
    error_de_pregunta: str | None = None,
    error_del_chatbot: str | None = None,
) -> str:
    return render_template(
        "chatbot/conversacion.html",
        pregunta=pregunta,
        pregunta_enviada=pregunta_enviada,
        respuesta=respuesta,
        errores={"pregunta": error_de_pregunta} if error_de_pregunta else {},
        error_del_chatbot=error_del_chatbot,
        hay_conversacion=CLAVE_DE_CONVERSACION in session,
        largo_maximo=chatbot.LARGO_MAXIMO_DE_LA_PREGUNTA,
    )
