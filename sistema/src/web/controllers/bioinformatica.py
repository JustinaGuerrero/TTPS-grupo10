"""Controlador del área de bioinformática (E33 Tomar estudio), del bioinformático.

- GET /bioinformatica/pendientes: los estudios con datos crudos que nadie tomó, Pompe urgente
  primero y después por orden de llegada.
- POST /bioinformatica/analisis/<id>/tomar: toma el estudio, que pasa a En análisis. Si otro lo
  tomó antes, vuelve a la lista con el aviso.
- GET /bioinformatica/mis-analisis: los estudios que tomó y todavía no finalizó (#20 agrega
  las variantes y el resultado).

El controlador valida la forma del pedido, llama a core, decide el commit y renderiza.
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, url_for

from src.core.analisis import ErrorDeAnalisis, buscar_analisis, mis_analisis, pendientes, tomar
from src.core.database import db
from src.core.estudios import TransicionInvalida
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("bioinformatica", __name__, url_prefix="/bioinformatica")


@bp.get("/pendientes")
@login_required
@rol_requerido(roles.BIOINFORMATICO)
def lista_de_pendientes():
    """E33.1 y E33.2: la lista de estudios para analizar."""
    return render_template("bioinformatica/pendientes.html", analisis=pendientes())


@bp.post("/analisis/<int:analisis_id>/tomar")
@login_required
@rol_requerido(roles.BIOINFORMATICO)
def tomar_analisis(analisis_id: int):
    """E33.3 y E33.4: el bioinformático toma el estudio y lo saca de la lista de los demás."""
    analisis = buscar_analisis(analisis_id)
    if analisis is None:
        abort(404)
    try:
        tomar(analisis, g.usuario)
    except (ErrorDeAnalisis, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("bioinformatica.lista_de_pendientes"))
    db.session.commit()
    flash(f"Tomaste el estudio {analisis.estudio.codigo}: ya está En análisis.", "exito")
    return redirect(url_for("bioinformatica.mis"))


@bp.get("/mis-analisis")
@login_required
@rol_requerido(roles.BIOINFORMATICO)
def mis():
    """Los estudios que tomó el bioinformático y todavía no finalizó."""
    return render_template("bioinformatica/mis_analisis.html", analisis=mis_analisis(g.usuario))
