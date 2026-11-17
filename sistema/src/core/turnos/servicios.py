"""Reglas de los turnos de extracción: reservar (E19), cancelar (E20) y recordar (E21).

Ninguna función hace commit: el controlador (o la tarea programada) confirma o hace rollback, así
que el turno, el cambio de estado del estudio y el aviso van en una sola transacción. Todas las
validaciones van antes de escribir. `ahora` es para los tests; por defecto, la hora de Argentina.
"""

from datetime import date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.calendario import ZONA_HORARIA, dias_habiles, es_dia_habil, proximo_dia_habil
from src.core.calendario import ahora as ahora_en_argentina
from src.core.centros.modelos import CentroExtraccion
from src.core.database import db
from src.core.estudios import EstadoEstudio, cambiar_estado
from src.core.estudios.modelos import Estudio
from src.core.notificaciones import notificar
from src.core.pacientes.modelos import Paciente
from src.core.turnos.franjas import es_franja_valida, franjas_del_dia
from src.core.turnos.modelos import EstadoTurno, TurnoExtraccion
from src.core.usuarios import roles
from src.core.usuarios.modelos import Usuario

# E19: desde Habilitado para turno (pagó o la obra social autorizó) o desde Requiere nueva
# extracción, que reserva sin un nuevo pago (E27).
ESTADOS_QUE_RESERVAN = (EstadoEstudio.HABILITADO_TURNO, EstadoEstudio.REQUIERE_NUEVA_EXTRACCION)
# Estados del turno que ocupan la franja (el índice turnos_extraccion_franja_ocupada).
ESTADOS_QUE_OCUPAN = (EstadoTurno.RESERVADO, EstadoTurno.ASISTIDO)
# Cuántos días hábiles hacia adelante muestra el turnero.
DIAS_DEL_TURNERO = 20
LINK_DE_MI_TURNO = "/turnos/mio"


class ErrorDeTurno(ValueError):
    """No se puede reservar o cancelar el turno; el mensaje se muestra al paciente."""


# --- consultas -------------------------------------------------------------------------------


def estudio_del_paciente(usuario: Usuario) -> Estudio | None:
    """El estudio del paciente que usa esta cuenta (hay uno solo, O20), o None."""
    consulta = sa.select(Estudio).join(Paciente).where(Paciente.usuario_id == usuario.id)
    return db.session.scalar(consulta)


def puede_reservar(estudio: Estudio) -> bool:
    return estudio.estado in ESTADOS_QUE_RESERVAN


def turno_vigente(estudio: Estudio) -> TurnoExtraccion | None:
    """El turno reservado del estudio, o None. Hay uno como mucho (índice de la base)."""
    consulta = sa.select(TurnoExtraccion).where(
        TurnoExtraccion.estudio_id == estudio.id,
        TurnoExtraccion.estado == EstadoTurno.RESERVADO,
    )
    return db.session.scalar(consulta)


def buscar_turno(turno_id: int) -> TurnoExtraccion | None:
    return db.session.get(TurnoExtraccion, turno_id)


def dias_con_turnos(ahora: datetime | None = None) -> list[date]:
    """Los próximos DIAS_DEL_TURNERO días hábiles. Hoy entra si todavía queda alguna franja."""
    ahora = ahora or ahora_en_argentina()
    hoy = ahora.astimezone(ZONA_HORARIA).date()
    primero = hoy if franjas_del_dia(hoy)[-1] > ahora else hoy + timedelta(days=1)
    return dias_habiles(primero, DIAS_DEL_TURNERO)


def franjas_libres(
    centro: CentroExtraccion, fecha: date, ahora: datetime | None = None
) -> list[datetime]:
    """E19.3: las franjas del centro en `fecha` que no están ocupadas ni pasaron.

    Un sábado, un domingo o un feriado no tienen franjas.
    """
    ahora = ahora or ahora_en_argentina()
    if not es_dia_habil(fecha):
        return []
    franjas = franjas_del_dia(fecha)
    ocupadas = set(
        db.session.scalars(
            sa.select(TurnoExtraccion.inicio).where(
                TurnoExtraccion.centro_id == centro.id,
                TurnoExtraccion.estado.in_(ESTADOS_QUE_OCUPAN),
                TurnoExtraccion.inicio.between(franjas[0], franjas[-1]),
            )
        )
    )
    return [franja for franja in franjas if franja > ahora and franja not in ocupadas]


# --- E19 Reservar turno de extracción ---------------------------------------------------------


def reservar(
    estudio: Estudio,
    paciente: Usuario,
    centro: CentroExtraccion,
    inicio: datetime,
    ahora: datetime | None = None,
) -> TurnoExtraccion:
    """E19.4 a E19.6: reserva la franja, pasa el estudio a Turno sacado y avisa al paciente.

    El aviso y el mail llevan a "Mi turno", donde el paciente descarga la orden de extracción y
    el consentimiento informado. Lanza ErrorDeTurno si quien reserva no es el paciente del
    estudio, si el estudio no puede reservar, si el centro no está activo, si la franja no es
    válida o ya pasó, o si otro paciente la reservó antes (también a la vez: lo frena el índice).
    """
    ahora = ahora or ahora_en_argentina()
    if not paciente.tiene_rol(roles.PACIENTE) or estudio.paciente.usuario_id != paciente.id:
        raise ErrorDeTurno("Solo el paciente del estudio puede reservar su turno.")
    if not puede_reservar(estudio):
        raise ErrorDeTurno(
            f"Tu estudio está {estudio.estado.nombre}: el turno se reserva cuando está "
            "Habilitado para turno o cuando se pide una nueva extracción."
        )
    if turno_vigente(estudio) is not None:
        raise ErrorDeTurno("Ya tenés un turno reservado: cancelalo antes de reservar otro.")
    if not centro.activo:
        raise ErrorDeTurno("Ese centro de extracción no está atendiendo.")
    if not es_franja_valida(inicio):
        raise ErrorDeTurno(
            "Los turnos son de 15 minutos, de lunes a viernes de 9 a 18 y sin feriados."
        )
    if inicio <= ahora:
        raise ErrorDeTurno("Ese horario ya pasó: elegí otro.")
    if _franja_ocupada(centro, inicio):
        raise ErrorDeTurno("Ese turno ya se reservó: elegí otro.")

    turno = TurnoExtraccion(estudio_id=estudio.id, centro_id=centro.id, inicio=inicio)
    try:
        # Si otro paciente reservó la misma franja entre la consulta y el insert, el índice
        # único lo frena acá. El savepoint deja la transacción usable para informar el error.
        with db.session.begin_nested():
            db.session.add(turno)
    except IntegrityError:
        raise ErrorDeTurno("Ese turno ya se reservó: elegí otro.") from None

    cambiar_estado(estudio, EstadoEstudio.TURNO_SACADO, paciente)
    notificar(
        paciente,
        "Turno de extracción reservado",
        f"Reservaste tu turno de extracción para el {_dia_y_hora(inicio)} en {centro.nombre} "
        f"({centro.direccion_completa}). Descargá la orden de extracción y el consentimiento "
        "informado, y llevalos el día del turno con el consentimiento firmado.",
        LINK_DE_MI_TURNO,
        estudio=estudio,
    )
    return turno


def _franja_ocupada(centro: CentroExtraccion, inicio: datetime) -> bool:
    consulta = sa.select(TurnoExtraccion.id).where(
        TurnoExtraccion.centro_id == centro.id,
        TurnoExtraccion.inicio == inicio,
        TurnoExtraccion.estado.in_(ESTADOS_QUE_OCUPAN),
    )
    return db.session.scalar(consulta) is not None


# --- E20 Cancelar turno -----------------------------------------------------------------------


def cancelar(
    turno: TurnoExtraccion, paciente: Usuario, ahora: datetime | None = None
) -> TurnoExtraccion:
    """E20.2 a E20.4: libera la franja y vuelve el estudio a Habilitado para turno. Sin costo.

    Lanza ErrorDeTurno si quien cancela no es el paciente del turno, si el turno no está
    reservado o si ya empezó.
    """
    ahora = ahora or ahora_en_argentina()
    if turno.estudio.paciente.usuario_id != paciente.id:
        raise ErrorDeTurno("Solo el paciente puede cancelar su turno.")
    if turno.estado != EstadoTurno.RESERVADO:
        raise ErrorDeTurno("Ese turno no está reservado.")
    if turno.inicio <= ahora:
        raise ErrorDeTurno("El turno ya empezó: no se puede cancelar.")

    turno.estado = EstadoTurno.CANCELADO
    turno.cancelado_en = ahora
    db.session.flush()
    cambiar_estado(turno.estudio, EstadoEstudio.HABILITADO_TURNO, paciente)
    return turno


# --- E21 Recordar turno -----------------------------------------------------------------------


def enviar_recordatorios(ahora: datetime | None = None) -> int:
    """E21: avisa por mail y en la lista de avisos a cada paciente con turno el próximo día hábil.

    Corre los días hábiles (tarea programada de src/web/tareas.py): el viernes avisa los turnos
    del lunes. Cada turno recibe un solo recordatorio. Devuelve cuántos mandó.
    """
    ahora = ahora or ahora_en_argentina()
    hoy = ahora.astimezone(ZONA_HORARIA).date()
    if not es_dia_habil(hoy):
        return 0
    dia = proximo_dia_habil(hoy)
    desde = datetime.combine(dia, datetime.min.time(), tzinfo=ZONA_HORARIA)
    # Marca los turnos antes de avisar, con un solo UPDATE: si la tarea corre dos veces a la vez,
    # cada turno queda marcado por una sola de las dos.
    marcados = db.session.scalars(
        sa.update(TurnoExtraccion)
        .where(
            TurnoExtraccion.estado == EstadoTurno.RESERVADO,
            TurnoExtraccion.inicio >= desde,
            TurnoExtraccion.inicio < desde + timedelta(days=1),
            TurnoExtraccion.recordatorio_enviado_en.is_(None),
        )
        .values(recordatorio_enviado_en=ahora)
        .returning(TurnoExtraccion.id)
    ).all()
    for turno_id in marcados:
        turno = db.session.get(TurnoExtraccion, turno_id)
        notificar(
            turno.estudio.paciente.usuario,
            "Recordatorio de tu turno de extracción",
            f"Te recordamos tu turno de extracción del {_dia_y_hora(turno.inicio)} en "
            f"{turno.centro.nombre} ({turno.centro.direccion_completa}). Llevá la orden de "
            "extracción y el consentimiento informado firmado.",
            LINK_DE_MI_TURNO,
            estudio=turno.estudio,
        )
    return len(marcados)


_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _dia_y_hora(inicio: datetime) -> str:
    """'martes 24/11/2026 a las 09:15', en hora de Argentina."""
    local = inicio.astimezone(ZONA_HORARIA)
    return f"{_DIAS[local.weekday()]} {local:%d/%m/%Y} a las {local:%H:%M}"
