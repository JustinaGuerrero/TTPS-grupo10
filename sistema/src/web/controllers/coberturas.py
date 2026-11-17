"""Controlador de la cobertura de obra social (E16 Solicitar, E17 Autorizar, E18 Reautorización).

El paciente elige su obra social desde su presupuesto y, si la obra social rechaza, sube la
resolución judicial. El administrativo registra la respuesta de la obra social. El controlador
valida la forma del pedido, llama a core, decide el commit y renderiza. Un estudio de otro
paciente responde 404.
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.coberturas import (
    ErrorDeCobertura,
    autorizar,
    buscar_cobertura,
    cargar_demanda,
    cobertura_de,
    opciones,
    pendientes,
    rechazar,
    solicitar,
)
from src.core.coberturas.servicios import TAMANO_MAXIMO_DE_LA_RESOLUCION
from src.core.database import db
from src.core.estudios import EstadoEstudio, TransicionInvalida
from src.core.pagos import buscar_estudio, presupuesto_de
from src.core.usuarios import roles
from src.integraciones import storage
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido
from src.web.helpers.pdf import respuesta_pdf

bp = Blueprint("coberturas", __name__)


# --- paciente: E16 Solicitar cobertura ---------------------------------------------------------


@bp.get("/estudios/<int:estudio_id>/cobertura")
@login_required
@rol_requerido(roles.PACIENTE)
def elegir(estudio_id: int):
    """E16.1 y E16.2: las obras sociales de la API con su porcentaje de cobertura."""
    estudio = _estudio_propio_o_404(estudio_id)
    if estudio.estado != EstadoEstudio.PRESUPUESTADO:
        flash("La cobertura de la obra social se pide con el estudio Presupuestado.", "aviso")
        return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))
    try:
        obras = opciones()
    except ErrorDeIntegracion as error:
        flash(error.mensaje, "error")
        obras = None
    presupuesto = presupuesto_de(estudio)
    return render_template(
        "coberturas/elegir.html", estudio=estudio, presupuesto=presupuesto, obras=obras
    ), (200 if obras is not None else 503)


@bp.post("/estudios/<int:estudio_id>/cobertura")
@login_required
@rol_requerido(roles.PACIENTE)
def pedir(estudio_id: int):
    """E16.3 a E16.5: guarda la obra social elegida y pasa a Pendiente de autorización."""
    estudio = _estudio_propio_o_404(estudio_id)
    try:
        cobertura = solicitar(estudio, g.usuario, request.form.get("codigo", "").strip())
    except (ErrorDeCobertura, ErrorDeIntegracion, TransicionInvalida) as error:
        db.session.rollback()
        flash(error.mensaje if isinstance(error, ErrorDeIntegracion) else str(error), "error")
        return redirect(url_for("coberturas.elegir", estudio_id=estudio.id))
    db.session.commit()
    flash(
        f"Pediste la cobertura de {cobertura.obra_social.nombre}. Te avisamos cuando responda.",
        "exito",
    )
    return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))


# --- paciente: E18 Solicitar reautorización ---------------------------------------------------


@bp.get("/estudios/<int:estudio_id>/reautorizacion")
@login_required
@rol_requerido(roles.PACIENTE)
def reautorizacion(estudio_id: int):
    """E18.1: el formulario para subir la resolución judicial favorable."""
    estudio = _estudio_propio_o_404(estudio_id)
    return render_template(
        "coberturas/reautorizacion.html",
        estudio=estudio,
        cobertura=cobertura_de(estudio),
        puede_cargar=estudio.estado == EstadoEstudio.RECHAZADO_OBRA_SOCIAL,
    )


@bp.post("/estudios/<int:estudio_id>/reautorizacion")
@login_required
@rol_requerido(roles.PACIENTE)
def cargar_reautorizacion(estudio_id: int):
    """E18.2 a E18.4: guarda el PDF, vuelve a Pendiente de autorización y avisa."""
    estudio = _estudio_propio_o_404(estudio_id)
    archivo = request.files.get("resolucion")
    contenido = archivo.read(TAMANO_MAXIMO_DE_LA_RESOLUCION + 1) if archivo else b""
    try:
        cargar_demanda(estudio, g.usuario, contenido)
    except (ErrorDeCobertura, ErrorDeIntegracion, TransicionInvalida) as error:
        db.session.rollback()
        flash(error.mensaje if isinstance(error, ErrorDeIntegracion) else str(error), "error")
        return redirect(url_for("coberturas.reautorizacion", estudio_id=estudio.id))
    db.session.commit()
    flash("Cargaste la resolución judicial. Te avisamos cuando responda la obra social.", "exito")
    return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))


# --- administrativo: E17 Autorizar cobertura --------------------------------------------------


@bp.get("/coberturas")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def pendientes_de_respuesta():
    """Los pedidos que esperan la respuesta de la obra social, con lo que cubriría cada uno."""
    filas = []
    for cobertura in pendientes():
        presupuesto = presupuesto_de(cobertura.estudio)
        total = presupuesto.total_usd if presupuesto else None
        cubriria = round(total * cobertura.porcentaje / 100, 2) if total is not None else None
        filas.append((cobertura, total, cubriria))
    return render_template("coberturas/pendientes.html", filas=filas)


@bp.post("/coberturas/<int:cobertura_id>/autorizar")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def autorizar_cobertura(cobertura_id: int):
    """E17.1 a E17.3: registra la autorización, el pago de la obra social y su asiento."""
    cobertura = _cobertura_o_404(cobertura_id)
    try:
        pago = autorizar(cobertura, g.usuario)
    except (ErrorDeCobertura, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("coberturas.pendientes_de_respuesta"))
    db.session.commit()
    flash(
        f"Registraste la autorización del estudio {cobertura.estudio.codigo}: la obra social "
        f"cubre {pago.importe_usd} USD.",
        "exito",
    )
    return redirect(url_for("coberturas.pendientes_de_respuesta"))


@bp.post("/coberturas/<int:cobertura_id>/rechazar")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def rechazar_cobertura(cobertura_id: int):
    """E17.4 y E17.5: registra el rechazo y pasa el estudio a Rechazado por obra social."""
    cobertura = _cobertura_o_404(cobertura_id)
    try:
        rechazar(cobertura, g.usuario, request.form.get("motivo"))
    except (ErrorDeCobertura, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("coberturas.pendientes_de_respuesta"))
    db.session.commit()
    flash(f"Registraste el rechazo del estudio {cobertura.estudio.codigo}.", "exito")
    return redirect(url_for("coberturas.pendientes_de_respuesta"))


@bp.get("/coberturas/<int:cobertura_id>/resolucion.pdf")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def resolucion_pdf(cobertura_id: int):
    """La última resolución judicial que cargó el paciente, para pedir la reautorización."""
    cobertura = _cobertura_o_404(cobertura_id)
    if not cobertura.demandas:
        abort(404)
    try:
        pdf = storage.bajar(cobertura.demandas[-1].resolucion_path)
    except ErrorDeIntegracion as error:
        flash(error.mensaje, "error")
        return redirect(url_for("coberturas.pendientes_de_respuesta"))
    return respuesta_pdf(pdf, f"resolucion-{cobertura.estudio.codigo}.pdf")


# --- helpers ---------------------------------------------------------------------------------


def _estudio_propio_o_404(estudio_id: int):
    """El estudio, solo si es del paciente logueado. Si no existe o es de otro, 404."""
    estudio = buscar_estudio(estudio_id)
    if estudio is None or estudio.paciente.usuario_id != g.usuario.id:
        abort(404)
    return estudio


def _cobertura_o_404(cobertura_id: int):
    cobertura = buscar_cobertura(cobertura_id)
    if cobertura is None:
        abort(404)
    return cobertura
