"""Controlador de cupones de descuento (E37, E38).

El gerente médico genera cupones para un médico tratante (E37); el médico tratante los asigna a sus
pacientes (E38); el paciente ve los suyos y los usa al pagar (E15, en controllers/pagos.py). El
controlador valida la forma del pedido, llama a core, decide el commit y renderiza.
"""

import io

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from src.core.cupones import (
    Cupon,
    ErrorDeCupon,
    asignar_a_paciente,
    cupones_del_medico,
    cupones_del_paciente,
    cupones_disponibles,
    cupones_generados,
    generar_cupones,
    medicos_tratantes,
    pacientes_del_medico,
)
from src.core.database import db
from src.core.pacientes.modelos import Paciente
from src.core.usuarios import roles
from src.integraciones import storage
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("cupones", __name__, url_prefix="/cupones")


# --- gerente médico (E37) ----------------------------------------------------------------------


@bp.get("")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def listar():
    """Cupones generados por el gerente médico."""
    return render_template("cupones/listar.html", cupones=cupones_generados(g.usuario))


@bp.get("/generar")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def generar_form():
    return _formulario_de_generacion({"porcentaje": "", "cantidad": "", "medico_id": ""})


@bp.post("/generar")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def generar():
    """E37.1 a E37.5: define descuento y cantidad, pide los cupones y los asigna al médico."""
    datos = {
        "porcentaje": request.form.get("porcentaje", ""),
        "cantidad": request.form.get("cantidad", ""),
        "medico_id": request.form.get("medico_id", ""),
    }
    medico = next((m for m in medicos_tratantes() if str(m.id) == datos["medico_id"]), None)
    try:
        cupones = generar_cupones(g.usuario, medico, datos["porcentaje"], datos["cantidad"])
    except ErrorDeCupon as error:
        db.session.rollback()
        flash(str(error), "error")
        return _formulario_de_generacion(datos), 400
    except ErrorDeIntegracion as error:
        db.session.rollback()
        flash(f"No se generaron los cupones. {error.mensaje}", "error")
        return _formulario_de_generacion(datos), 503
    db.session.commit()
    flash(
        f"Se generaron {len(cupones)} cupones y se asignaron a {medico.nombre_completo}.", "exito"
    )
    return redirect(url_for("cupones.listar"))


# --- médico tratante (E38) y paciente ------------------------------------------------------------


@bp.get("/mios")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE, roles.PACIENTE)
def mios():
    """Médico: sus cupones y a quién asignarlos (E38.1). Paciente: sus cupones vigentes (E38.5)."""
    if g.usuario.tiene_rol(roles.PACIENTE):
        return render_template("cupones/paciente.html", cupones=cupones_del_paciente(g.usuario))
    return render_template(
        "cupones/medico.html",
        cupones=cupones_del_medico(g.usuario),
        disponibles=cupones_disponibles(g.usuario),
        pacientes=pacientes_del_medico(g.usuario),
    )


@bp.post("/<int:cupon_id>/asignar")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def asignar(cupon_id: int):
    """E38.2 a E38.4: asigna el cupón a un paciente del médico y le avisa."""
    try:
        paciente_id = int(request.form.get("paciente_id", ""))
    except ValueError:
        flash("Elegí un paciente.", "error")
        return redirect(url_for("cupones.mios")), 303
    try:
        cupon = asignar_a_paciente(g.usuario, cupon_id, paciente_id)
    except ErrorDeCupon as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("cupones.mios")), 303
    except ErrorDeIntegracion as error:
        db.session.rollback()
        flash(f"No se asignó el cupón. {error.mensaje}", "error")
        return redirect(url_for("cupones.mios")), 303
    db.session.commit()
    flash(f"Asignaste el cupón {cupon.codigo} al paciente.", "exito")
    return redirect(url_for("cupones.mios"))


@bp.get("/<int:cupon_id>/pdf")
@login_required
@rol_requerido(roles.GERENTE_MEDICO, roles.MEDICO_TRATANTE, roles.PACIENTE)
def pdf(cupon_id: int):
    """El PDF del cupón, solo para quien lo generó, lo recibió o lo tiene asignado."""
    cupon = db.session.get(Cupon, cupon_id)
    if cupon is None or not _puede_ver(cupon):
        abort(404)
    try:
        contenido = storage.bajar(cupon.pdf_path)
    except ErrorDeIntegracion as error:
        flash(error.mensaje, "error")
        return redirect(
            url_for(
                "cupones.mios"
                if not g.usuario.tiene_rol(roles.GERENTE_MEDICO)
                else "cupones.listar"
            )
        )
    return send_file(
        io.BytesIO(contenido),
        mimetype="application/pdf",
        download_name=f"cupon-{cupon.codigo}.pdf",
    )


# --- helpers ---------------------------------------------------------------------------------


def _puede_ver(cupon: Cupon) -> bool:
    if g.usuario.tiene_rol(roles.GERENTE_MEDICO):
        return cupon.generado_por == g.usuario.id
    if g.usuario.tiene_rol(roles.MEDICO_TRATANTE):
        return cupon.medico_tratante_id == g.usuario.id
    if cupon.paciente_id is None:
        return False
    return db.session.get(Paciente, cupon.paciente_id).usuario_id == g.usuario.id


def _formulario_de_generacion(datos: dict):
    return render_template("cupones/generar.html", datos=datos, medicos=medicos_tratantes())
