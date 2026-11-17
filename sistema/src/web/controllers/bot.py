"""Controlador del bot de mensajería (E22 Registrar toma de muestra).

- POST /bot/telegram: webhook que llama Telegram por cada mensaje que recibe el bot. Es una ruta
  sin sesión: está exenta de CSRF y se autentica con el header X-Telegram-Bot-Api-Secret-Token,
  que tiene que coincidir con TELEGRAM_WEBHOOK_SECRET. Sin el secreto responde 403 y no guarda
  nada; con el secreto responde siempre 200, aunque el mensaje tenga un error, para que Telegram
  no lo reintente. La respuesta al centro va en el cuerpo del 200 (método sendMessage del
  webhook, ver docs/apis/telegram.md).
- GET /bot/mensajes: el administrativo revisa los mensajes recibidos y los que fallaron.
"""

import hmac

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from src.core.database import db
from src.core.muestras import UpdateSinId, guardar_con_error, listar_mensajes, registrar_toma
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido
from src.web.helpers.csrf import csrf

bp = Blueprint("bot", __name__, url_prefix="/bot")

HEADER_DEL_SECRETO = "X-Telegram-Bot-Api-Secret-Token"


@bp.post("/telegram")
@csrf.exempt
def telegram():
    """E22.4 y E22.5: recibe el mensaje de muestra tomada y pasa el estudio a Listo para retirar."""
    if not _secreto_valido(request.headers.get(HEADER_DEL_SECRETO)):
        abort(403)
    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        current_app.logger.warning("El webhook del bot recibió un cuerpo que no es un update")
        return "", 200

    try:
        resultado = registrar_toma(update)
        db.session.commit()
    except UpdateSinId:
        db.session.rollback()
        current_app.logger.warning("El webhook del bot recibió un update sin update_id")
        return "", 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Falló el procesamiento del update %s", update.get("update_id")
        )
        _guardar_el_error(update)
        return "", 200

    if resultado.respuesta is None:
        return "", 200
    return jsonify(
        method="sendMessage", chat_id=resultado.mensaje.chat_id, text=resultado.respuesta
    )


@bp.get("/mensajes")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def mensajes():
    """Mensajes del bot, del más nuevo al más viejo, con el filtro "solo con error"."""
    solo_con_error = request.args.get("errores") == "1"
    pagina = request.args.get("pagina", 1, type=int)
    return render_template(
        "bot/mensajes.html",
        pagina=listar_mensajes(solo_con_error, pagina),
        solo_con_error=solo_con_error,
    )


def _secreto_valido(recibido: str | None) -> bool:
    """Compara en tiempo constante. Sin TELEGRAM_WEBHOOK_SECRET configurado, nadie pasa."""
    esperado = current_app.config.get("TELEGRAM_WEBHOOK_SECRET")
    if not esperado or not recibido:
        return False
    return hmac.compare_digest(recibido.encode(), esperado.encode())


def _guardar_el_error(update: dict) -> None:
    """Deja el update con un error genérico en la lista del administrativo, si se puede."""
    try:
        guardar_con_error(update)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Tampoco se pudo guardar el update con error")
