"""Controlador de los turnos de extracción del paciente (E19 Reservar, E20 Cancelar).

El paciente entra por "Mi turno": si ya tiene un turno lo ve, lo cancela y descarga la orden de
extracción y el consentimiento; si su estudio puede reservar, va al mapa de centros, elige un
centro y una franja libre. El controlador valida la forma del pedido, llama a core, decide el
commit y renderiza. Un turno de otro paciente responde 404.
"""

from datetime import date, datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.calendario import ZONA_HORARIA
from src.core.centros import buscar_centro, listar_centros_activos
from src.core.database import db
from src.core.estudios import EstadoEstudio, TransicionInvalida
from src.core.turnos import (
    ErrorDeTurno,
    EstadoTurno,
    buscar_turno,
    cancelar,
    dias_con_turnos,
    estudio_del_paciente,
    franjas_libres,
    puede_reservar,
    reservar,
    turno_vigente,
)
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido
from src.web.helpers.pdf import pdf_desde_plantilla, respuesta_pdf

bp = Blueprint("turnos", __name__)


@bp.get("/turnos/mio")
@login_required
@rol_requerido(roles.PACIENTE)
def mio():
    """E20.1: el turno del paciente, con la orden, el consentimiento y el botón de cancelar."""
    estudio = _estudio_o_volver_al_inicio()
    if estudio is None:
        return redirect(url_for("inicio.index"))
    return render_template(
        "turnos/mio.html",
        estudio=estudio,
        turno=turno_vigente(estudio),
        puede_reservar=puede_reservar(estudio),
        nueva_extraccion=estudio.estado == EstadoEstudio.REQUIERE_NUEVA_EXTRACCION,
    )


@bp.get("/turnos/centros")
@login_required
@rol_requerido(roles.PACIENTE)
def centros():
    """E19.1 y E19.2: el mapa y la lista de centros de extracción."""
    estudio = _estudio_que_reserva_o_none()
    if estudio is None:
        return redirect(url_for("turnos.mio"))
    centros_activos = listar_centros_activos()
    puntos = [
        {
            "lat": float(centro.latitud),
            "lon": float(centro.longitud),
            "titulo": centro.nombre,
            "texto": centro.direccion_completa,
            "url": url_for("turnos.franjas", centro_id=centro.id),
            "link": "Ver turnos",
        }
        for centro in centros_activos
    ]
    return render_template("turnos/centros.html", centros=centros_activos, puntos=puntos)


@bp.get("/turnos/centros/<int:centro_id>/franjas")
@login_required
@rol_requerido(roles.PACIENTE)
def franjas(centro_id: int):
    """E19.3: las franjas libres del centro en el día elegido (por defecto, el primero)."""
    estudio = _estudio_que_reserva_o_none()
    if estudio is None:
        return redirect(url_for("turnos.mio"))
    centro = buscar_centro(centro_id)
    if centro is None or not centro.activo:
        abort(404)
    dias = dias_con_turnos()
    fecha = _fecha_del_pedido(request.args.get("fecha")) or dias[0]
    if fecha not in dias:
        fecha = dias[0]
    return render_template(
        "turnos/franjas.html",
        centro=centro,
        dias=[(dia, _nombre_del_dia(dia)) for dia in dias],
        fecha=fecha,
        nombre_de_la_fecha=_nombre_del_dia(fecha),
        franjas=franjas_libres(centro, fecha),
    )


@bp.post("/turnos")
@login_required
@rol_requerido(roles.PACIENTE)
def reservar_turno():
    """E19.4 a E19.6: reserva la franja elegida y pasa el estudio a Turno sacado."""
    estudio = estudio_del_paciente(g.usuario)
    if estudio is None:
        abort(404)
    centro = buscar_centro(request.form.get("centro_id", type=int) or 0)
    inicio = _inicio_del_pedido(request.form.get("inicio"))
    if centro is None or inicio is None:
        flash("Elegí un centro y un horario de la lista.", "error")
        return redirect(url_for("turnos.centros"))
    try:
        turno = reservar(estudio, g.usuario, centro, inicio)
    except (ErrorDeTurno, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        fecha = inicio.astimezone(ZONA_HORARIA).date().isoformat()
        return redirect(url_for("turnos.franjas", centro_id=centro.id, fecha=fecha))
    db.session.commit()
    flash(
        f"Reservaste tu turno en {turno.centro.nombre}. Descargá la orden de extracción y el "
        "consentimiento informado.",
        "exito",
    )
    return redirect(url_for("turnos.mio"))


@bp.post("/turnos/<int:turno_id>/cancelar")
@login_required
@rol_requerido(roles.PACIENTE)
def cancelar_turno(turno_id: int):
    """E20.2 a E20.4: cancela el turno sin costo y el estudio vuelve a Habilitado para turno."""
    turno = _turno_propio_o_404(turno_id)
    try:
        cancelar(turno, g.usuario)
    except (ErrorDeTurno, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("turnos.mio"))
    db.session.commit()
    flash("Cancelaste tu turno. Podés reservar otro cuando puedas asistir.", "exito")
    return redirect(url_for("turnos.mio"))


@bp.get("/turnos/<int:turno_id>/orden.pdf")
@login_required
@rol_requerido(roles.PACIENTE)
def orden_pdf(turno_id: int):
    """E19.6: la orden de extracción, con el código del estudio que el centro manda al bot."""
    turno = _turno_propio_o_404(turno_id)
    if turno.estado != EstadoTurno.RESERVADO:
        abort(404)
    pdf = pdf_desde_plantilla("pdf/orden_extraccion.html", turno=turno, estudio=turno.estudio)
    return respuesta_pdf(pdf, f"orden-de-extraccion-{turno.estudio.codigo}.pdf")


@bp.get("/turnos/consentimiento.pdf")
@login_required
@rol_requerido(roles.PACIENTE)
def consentimiento_pdf():
    """E19.6: el consentimiento informado, con los datos del paciente, para firmar."""
    estudio = estudio_del_paciente(g.usuario)
    if estudio is None:
        abort(404)
    pdf = pdf_desde_plantilla("pdf/consentimiento.html", estudio=estudio)
    return respuesta_pdf(pdf, f"consentimiento-informado-{estudio.codigo}.pdf")


# --- helpers ---------------------------------------------------------------------------------


def _estudio_o_volver_al_inicio():
    estudio = estudio_del_paciente(g.usuario)
    if estudio is None:
        flash("Todavía no tenés un estudio.", "aviso")
    return estudio


def _estudio_que_reserva_o_none():
    """El estudio del paciente si puede reservar; si no, deja un aviso y devuelve None."""
    estudio = estudio_del_paciente(g.usuario)
    if estudio is None:
        flash("Todavía no tenés un estudio.", "aviso")
        return None
    if not puede_reservar(estudio):
        if turno_vigente(estudio) is None:
            flash(
                f"Tu estudio está {estudio.estado.nombre}: vas a poder sacar turno cuando esté "
                "Habilitado para turno.",
                "aviso",
            )
        return None
    return estudio


def _turno_propio_o_404(turno_id: int):
    """El turno, solo si es del paciente logueado. Si no existe o es de otro, 404."""
    turno = buscar_turno(turno_id)
    if turno is None or turno.estudio.paciente.usuario_id != g.usuario.id:
        abort(404)
    return turno


_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _nombre_del_dia(dia: date) -> str:
    """'martes 24/11'."""
    return f"{_DIAS[dia.weekday()]} {dia:%d/%m}"


def _fecha_del_pedido(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _inicio_del_pedido(texto: str | None) -> datetime | None:
    """El inicio de la franja que mandó el formulario, en ISO con zona horaria."""
    try:
        inicio = datetime.fromisoformat(texto) if texto else None
    except ValueError:
        return None
    if inicio is not None and inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=ZONA_HORARIA)
    return inicio
