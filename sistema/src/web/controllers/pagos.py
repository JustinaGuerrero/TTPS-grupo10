"""Controlador de presupuesto y pago particular (E13, E14).

El administrativo emite los presupuestos de los estudios en Creado; el paciente consulta el suyo
y lo paga (pago simulado). El controlador valida la forma del pedido, llama a core, decide el
commit y renderiza. Un paciente solo ve y paga su propio estudio: el de otro responde 404.
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.database import db
from src.core.estudios import TransicionInvalida
from src.core.pagos import (
    ErrorDePago,
    buscar_estudio,
    calcular_importe,
    cantidad_de_genes,
    emitir_presupuesto,
    estudio_del_paciente,
    estudios_en_creado,
    importe_final,
    pagar_particular,
    presupuesto_de,
)
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("pagos", __name__)


# --- administrativo (E13) --------------------------------------------------------------------


@bp.get("/presupuestos")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def pendientes():
    """E13.1: estudios en Creado, con el importe que calcula el sistema."""
    pagina = request.args.get("pagina", 1, type=int)
    pagina = estudios_en_creado(pagina)
    filas = [
        (estudio, cantidad_de_genes(estudio), calcular_importe(cantidad_de_genes(estudio)))
        for estudio in pagina.items
    ]
    return render_template("pagos/pendientes.html", pagina=pagina, filas=filas)


@bp.post("/presupuestos/<int:estudio_id>")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def emitir(estudio_id: int):
    """E13.3 a E13.5: emite el presupuesto, pasa el estudio a Presupuestado y avisa al paciente."""
    estudio = buscar_estudio(estudio_id)
    if estudio is None:
        abort(404)
    try:
        presupuesto = emitir_presupuesto(estudio, g.usuario)
    except (ErrorDePago, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("pagos.pendientes"))
    db.session.commit()
    flash(
        f"Se emitió el presupuesto del estudio {estudio.codigo}: {presupuesto.total_usd} USD.",
        "exito",
    )
    return redirect(url_for("pagos.pendientes"))


# --- paciente (E14) --------------------------------------------------------------------------


@bp.get("/mi-presupuesto")
@login_required
@rol_requerido(roles.PACIENTE)
def mi_presupuesto():
    """Entrada del menú: lleva al presupuesto del estudio del paciente."""
    estudio = estudio_del_paciente(g.usuario)
    if estudio is None:
        flash("Todavía no tenés un estudio.", "aviso")
        return redirect(url_for("inicio.index"))
    return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))


@bp.get("/estudios/<int:estudio_id>/presupuesto")
@login_required
@rol_requerido(roles.PACIENTE)
def presupuesto(estudio_id: int):
    """E14.1: el paciente consulta el presupuesto de su estudio."""
    estudio = _estudio_propio_o_404(estudio_id)
    return render_template(
        "pagos/presupuesto.html",
        estudio=estudio,
        presupuesto=presupuesto_de(estudio),
    )


@bp.get("/estudios/<int:estudio_id>/pago")
@login_required
@rol_requerido(roles.PACIENTE)
def pagar(estudio_id: int):
    """E14.2: confirmación con el importe final."""
    estudio = _estudio_propio_o_404(estudio_id)
    presupuesto = presupuesto_de(estudio)
    if presupuesto is None:
        flash("Tu estudio todavía no tiene presupuesto.", "aviso")
        return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))
    return _formulario_de_pago(estudio, presupuesto)


@bp.post("/estudios/<int:estudio_id>/pago")
@login_required
@rol_requerido(roles.PACIENTE)
def confirmar_pago(estudio_id: int):
    """E14.4 a E14.6: pago simulado por el importe final; habilita el turno."""
    estudio = _estudio_propio_o_404(estudio_id)
    try:
        pagar_particular(estudio, g.usuario, request.form.get("importe", ""))
    except (ErrorDePago, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        presupuesto = presupuesto_de(estudio)
        if presupuesto is None:
            return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id)), 400
        return _formulario_de_pago(estudio, presupuesto), 400
    db.session.commit()
    flash("Pagaste tu estudio. Ya podés sacar tu turno de extracción.", "exito")
    return redirect(url_for("pagos.presupuesto", estudio_id=estudio.id))


# --- helpers ---------------------------------------------------------------------------------


def _estudio_propio_o_404(estudio_id: int):
    """El estudio, solo si es del paciente logueado. Si no existe o es de otro, 404."""
    estudio = buscar_estudio(estudio_id)
    if estudio is None or estudio.paciente.usuario_id != g.usuario.id:
        abort(404)
    return estudio


def _formulario_de_pago(estudio, presupuesto):
    return render_template(
        "pagos/pagar.html",
        estudio=estudio,
        presupuesto=presupuesto,
        importe_final=importe_final(presupuesto),
    )
