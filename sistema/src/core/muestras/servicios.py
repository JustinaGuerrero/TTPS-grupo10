"""Reglas de la toma de muestra (E22) y de la inasistencia al turno (supuesto O7).

El centro de extracción no opera el sistema: avisa por el bot de mensajería (Telegram) que tomó
la muestra, con un mensaje que trae el código del estudio (formato provisorio en
docs/apis/telegram.md). Cada update se guarda en mensajes_bot, se pueda procesar o no, y uno
repetido no hace nada.

Ninguna función hace commit: lo decide el controlador, el comando o la tarea programada. Todas
las validaciones van antes de escribir, así que un mensaje con error solo deja su fila en
mensajes_bot. `ahora` es para los tests; por defecto, la hora de Argentina.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.calendario import ZONA_HORARIA
from src.core.calendario import ahora as ahora_en_argentina
from src.core.centros.modelos import CentroExtraccion
from src.core.centros.servicios import buscar_por_chat
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, cambiar_estado
from src.core.muestras.modelos import MensajeBot, Muestra
from src.core.notificaciones import notificar
from src.core.paginacion import Pagina, paginar
from src.core.provincias.modelos import Provincia
from src.core.turnos import TurnoExtraccion, marcar_asistido, marcar_ausentes, turno_vigente
from src.core.turnos.servicios import LINK_DE_MI_TURNO

# Código del estudio como lo genera la base: EX-2026-00042 (ver la migración de estudios).
PATRON_DE_CODIGO = re.compile(r"\bEX-(\d{4})-(\d{5,})\b", re.IGNORECASE)
MENSAJES_POR_PAGINA = 25

# Errores que se guardan en mensajes_bot.error y se le responden al centro.
SIN_TEXTO = "El mensaje no trae texto."
CHAT_DESCONOCIDO = "El chat no es de un centro de extracción registrado."
SIN_CODIGO = "El mensaje no trae el código del estudio (por ejemplo EX-2026-00042)."
ERROR_INTERNO = "Error interno al procesar el mensaje."


class UpdateSinId(ValueError):
    """El update no tiene un update_id entero: no se puede guardar en mensajes_bot."""


class ErrorDeMensaje(ValueError):
    """El mensaje del bot no se puede procesar; el texto se guarda y se le responde al centro."""


@dataclass(frozen=True)
class ResultadoDelMensaje:
    """Lo que dejó un update. `mensaje` es None si el update ya se había recibido.

    `respuesta` es el texto para el centro, o None si no hay que responder (update repetido o
    chat que no es de un centro).
    """

    mensaje: MensajeBot | None
    respuesta: str | None

    @property
    def repetido(self) -> bool:
        return self.mensaje is None

    @property
    def procesado(self) -> bool:
        """True si el mensaje pasó el estudio a Listo para retirar."""
        return self.mensaje is not None and self.mensaje.error is None


# --- E22 Registrar toma de muestra ------------------------------------------------------------


def registrar_toma(update: dict[str, Any], ahora: datetime | None = None) -> ResultadoDelMensaje:
    """E22.4 a E22.6: guarda el update y, si está todo bien, registra la muestra.

    Con un mensaje válido crea la muestra del turno, pasa el turno a asistido y el estudio a
    Listo para retirar; desde ahí el centro entra en la próxima orden del día de su provincia
    (centros_con_muestras_listas). Si el chat no es de un centro, el código no existe, el estudio
    no está en Turno sacado o el turno es de otro centro, guarda el error y no cambia nada.
    Lanza UpdateSinId si el update no tiene un update_id entero (no se puede guardar).
    """
    ahora = ahora or ahora_en_argentina()
    update_id = update.get("update_id") if isinstance(update, dict) else None
    if not isinstance(update_id, int) or isinstance(update_id, bool):
        raise UpdateSinId("El update de Telegram no trae un update_id entero.")

    chat_id, texto = _chat_y_texto(update)
    mensaje = MensajeBot(telegram_update_id=update_id, chat_id=chat_id, texto=texto)
    if not _guardar_si_es_nuevo(mensaje):
        return ResultadoDelMensaje(None, None)

    centro = buscar_por_chat(chat_id) if chat_id is not None else None
    mensaje.centro_id = centro.id if centro is not None else None
    try:
        if centro is None:
            raise ErrorDeMensaje(CHAT_DESCONOCIDO)
        estudio = _tomar_muestra(centro, texto, mensaje, ahora)
    except ErrorDeMensaje as error:
        mensaje.error = str(error)
        mensaje.procesado_en = ahora
        db.session.flush()
        # A un chat desconocido no se le contesta: puede ser cualquiera que encontró el bot.
        respuesta = None if centro is None else f"No se registró la muestra: {error}"
        return ResultadoDelMensaje(mensaje, respuesta)

    mensaje.procesado_en = ahora
    db.session.flush()
    return ResultadoDelMensaje(
        mensaje, f"Muestra registrada: el estudio {estudio.codigo} está Listo para retirar."
    )


def guardar_con_error(update: dict[str, Any], error: str = ERROR_INTERNO) -> MensajeBot | None:
    """Guarda el update con `error` cuando registrar_toma() falló de forma inesperada.

    El controlador la llama después del rollback, para que el administrativo vea el mensaje en
    la lista. Devuelve None si el update no se puede guardar o ya estaba.
    """
    update_id = update.get("update_id") if isinstance(update, dict) else None
    if not isinstance(update_id, int) or isinstance(update_id, bool):
        return None
    chat_id, texto = _chat_y_texto(update)
    mensaje = MensajeBot(telegram_update_id=update_id, chat_id=chat_id, texto=texto, error=error)
    return mensaje if _guardar_si_es_nuevo(mensaje) else None


def _tomar_muestra(
    centro: CentroExtraccion, texto: str | None, mensaje: MensajeBot, ahora: datetime
) -> Estudio:
    """Valida el mensaje del centro y, si está bien, registra la muestra. Lanza ErrorDeMensaje."""
    if not texto:
        raise ErrorDeMensaje(SIN_TEXTO)
    codigo = codigo_del_estudio(texto)
    if codigo is None:
        raise ErrorDeMensaje(SIN_CODIGO)
    estudio = db.session.scalar(sa.select(Estudio).where(Estudio.codigo == codigo))
    if estudio is None:
        raise ErrorDeMensaje(f"No existe el estudio {codigo}.")
    mensaje.estudio_id = estudio.id
    if estudio.estado != EstadoEstudio.TURNO_SACADO:
        raise ErrorDeMensaje(
            f"El estudio {codigo} está {estudio.estado.nombre}, no en Turno sacado."
        )
    turno = turno_vigente(estudio)
    if turno is None:
        raise ErrorDeMensaje(f"El estudio {codigo} no tiene un turno reservado.")
    if turno.centro_id != centro.id:
        raise ErrorDeMensaje(f"El turno del estudio {codigo} es de otro centro de extracción.")

    marcar_asistido(turno)
    db.session.add(Muestra(estudio_id=estudio.id, turno_id=turno.id, tomada_en=ahora))
    db.session.flush()
    cambiar_estado(
        estudio,
        EstadoEstudio.LISTO_PARA_RETIRAR,
        None,
        motivo=f"Mensaje de muestra tomada de {centro.nombre}",
    )
    return estudio


def update_simulado(chat_id: str, texto: str) -> dict[str, Any]:
    """Un update como el de Telegram, para `flask bot simular` (docs/apis/telegram.md).

    Usa update_id negativos: Telegram los da siempre positivos, así que uno simulado nunca hace
    que se ignore un mensaje real por repetido.
    """
    menor = db.session.scalar(sa.select(sa.func.min(MensajeBot.telegram_update_id)))
    update_id = min(menor or 0, 0) - 1
    return {
        "update_id": update_id,
        "message": {
            "message_id": -update_id,
            "date": int(ahora_en_argentina().timestamp()),
            "chat": {"id": chat_id, "type": "private"},
            "text": texto,
        },
    }


def codigo_del_estudio(texto: str) -> str | None:
    """El primer código de estudio del texto, normalizado (EX-2026-00042), o None."""
    encontrado = PATRON_DE_CODIGO.search(texto)
    if encontrado is None:
        return None
    return f"EX-{encontrado.group(1)}-{encontrado.group(2)}"


def _chat_y_texto(update: dict[str, Any]) -> tuple[str | None, str | None]:
    """El chat y el texto del mensaje del update. Los dos son None si no trae un mensaje."""
    mensaje = update.get("message") or update.get("edited_message") or update.get("channel_post")
    if not isinstance(mensaje, dict):
        return None, None
    chat = mensaje.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    texto = mensaje.get("text")
    return (
        str(chat_id) if chat_id is not None else None,
        texto.strip() if isinstance(texto, str) and texto.strip() else None,
    )


def _guardar_si_es_nuevo(mensaje: MensajeBot) -> bool:
    """Inserta el mensaje; False si ya había uno con el mismo update_id (también a la vez)."""
    existe = db.session.scalar(
        sa.select(MensajeBot.id).where(MensajeBot.telegram_update_id == mensaje.telegram_update_id)
    )
    if existe is not None:
        return False
    try:
        # Si el mismo update llegó dos veces a la vez, el índice único frena al segundo acá. El
        # savepoint deja la transacción usable.
        with db.session.begin_nested():
            db.session.add(mensaje)
    except IntegrityError:
        return False
    return True


# --- E22.6 y E23: centros para la orden del día -----------------------------------------------


def centros_con_muestras_listas(provincia: Provincia | int) -> list[CentroExtraccion]:
    """Los centros de la provincia con muestras para retirar, ordenados por id.

    Son las muestras de estudios Listo para retirar que todavía no tienen orden del día y que
    no se marcaron como insuficientes. La usa la orden del día (E23, issue #13).
    """
    provincia_id = provincia.id if isinstance(provincia, Provincia) else provincia
    con_muestras = (
        sa.select(TurnoExtraccion.centro_id)
        .join(Muestra, Muestra.turno_id == TurnoExtraccion.id)
        .join(Estudio, Estudio.id == Muestra.estudio_id)
        .where(
            Estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR,
            Muestra.orden_del_dia_id.is_(None),
            Muestra.insuficiente_en.is_(None),
        )
    )
    consulta = (
        sa.select(CentroExtraccion)
        .where(
            CentroExtraccion.provincia_id == provincia_id,
            CentroExtraccion.id.in_(con_muestras),
        )
        .order_by(CentroExtraccion.id)
    )
    return list(db.session.scalars(consulta))


# --- O7 Inasistencia al turno -----------------------------------------------------------------


def procesar_inasistencias(ahora: datetime | None = None) -> int:
    """O7: al cierre del día, libera los turnos de hoy (o anteriores) sin mensaje de muestra.

    Cada turno reservado que empezó antes de mañana y cuyo estudio sigue en Turno sacado pasa a
    ausente, el estudio vuelve a Habilitado para turno y el paciente recibe un aviso para
    reservar otro. La inasistencia no se penaliza. Corre a las 18:30 los días hábiles (tarea
    programada de src/web/tareas.py). Devuelve cuántos turnos liberó.
    """
    ahora = ahora or ahora_en_argentina()
    manana = ahora.astimezone(ZONA_HORARIA).date() + timedelta(days=1)
    hasta = datetime.combine(manana, datetime.min.time(), tzinfo=ZONA_HORARIA)
    ausentes = marcar_ausentes(hasta)
    for turno in ausentes:
        estudio = turno.estudio
        cambiar_estado(
            estudio,
            EstadoEstudio.HABILITADO_TURNO,
            None,
            motivo="Inasistencia: no llegó el mensaje de muestra tomada",
        )
        notificar(
            estudio.paciente.usuario,
            "No registramos tu extracción",
            f"No recibimos el aviso de muestra tomada de tu turno en {turno.centro.nombre}. "
            "Liberamos el turno sin costo: reservá uno nuevo cuando puedas asistir.",
            LINK_DE_MI_TURNO,
            estudio=estudio,
        )
    return len(ausentes)


# --- Lista del administrativo -----------------------------------------------------------------


def listar_mensajes(solo_con_error: bool = False, pagina: int = 1) -> Pagina[MensajeBot]:
    """Los mensajes del bot, del más nuevo al más viejo; con `solo_con_error`, los que fallaron."""
    consulta = sa.select(MensajeBot).order_by(MensajeBot.recibido_en.desc(), MensajeBot.id.desc())
    if solo_con_error:
        consulta = consulta.where(MensajeBot.error.is_not(None))
    return paginar(consulta, pagina, MENSAJES_POR_PAGINA)
