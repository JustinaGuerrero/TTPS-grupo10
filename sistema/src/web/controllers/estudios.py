"""Alta de estudios por el médico tratante (E10).

Entra desde la ficha del paciente y desde "Mis pacientes". Un paciente ajeno responde 404.
La lógica está en src/core/estudios/alta.py; este controlador valida, llama a core y renderiza.
"""

import re

import sqlalchemy as sa
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.database import db
from src.core.estudios import Estudio
from src.core.estudios.alta import dar_de_alta_estudio, genes_para
from src.core.pacientes import ErrorDeValidacion, paciente_del_medico
from src.core.usuarios import roles
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("estudios", __name__, url_prefix="/estudios")

SEPARADOR_DE_GENES = re.compile(r"[\s,;]+")


@bp.get("/nuevo/<int:paciente_id>")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def nuevo(paciente_id: int):
    paciente = _paciente_o_404(paciente_id)
    if _ya_tiene_estudio(paciente):
        return redirect(url_for("pacientes.detalle", paciente_id=paciente.id))
    return _formulario(paciente)


@bp.post("/nuevo/<int:paciente_id>")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def crear(paciente_id: int):
    paciente = _paciente_o_404(paciente_id)
    if _ya_tiene_estudio(paciente):
        return redirect(url_for("pacientes.detalle", paciente_id=paciente.id))

    texto_genes = request.form.get("genes_a_mano", "")
    hallazgos = request.form.get("evalua_hallazgos_secundarios") == "on"
    try:
        estudio = dar_de_alta_estudio(
            paciente,
            g.usuario,
            genes_a_mano=SEPARADOR_DE_GENES.split(texto_genes),
            evalua_hallazgos_secundarios=hallazgos,
        )
    except ErrorDeValidacion as error:
        db.session.rollback()
        flash("Revisá los datos marcados; el estudio no se creó.", "error")
        return _formulario(paciente, texto_genes, hallazgos, error.errores), 400
    except ErrorDeIntegracion as error:
        db.session.rollback()
        flash(f"No se pudo dar de alta el estudio. {error.mensaje}", "error")
        return _formulario(paciente, texto_genes, hallazgos), 503
    codigo = estudio.codigo
    db.session.commit()
    flash(f"Se dio de alta el estudio {codigo}. Avisamos al administrativo.", "exito")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente.id))


def _paciente_o_404(paciente_id: int):
    paciente = paciente_del_medico(paciente_id, g.usuario)
    if paciente is None:
        abort(404)
    return paciente


def _ya_tiene_estudio(paciente) -> bool:
    if db.session.scalar(sa.select(Estudio.id).where(Estudio.paciente_id == paciente.id)) is None:
        return False
    flash("El paciente ya tiene un estudio; una sospecha nueva se pide por reanálisis.", "aviso")
    return True


def _formulario(paciente, genes_a_mano: str = "", hallazgos: bool = False, errores=None):
    patologias = [d.patologia for d in paciente.diagnosticos_presuntivos]
    genes, error_apigen = [], None
    try:
        genes = genes_para(patologias)
    except ErrorDeIntegracion as error:
        error_apigen = error.mensaje
    return render_template(
        "estudios/nuevo.html",
        paciente=paciente,
        patologias=patologias,
        genes=genes,
        error_apigen=error_apigen,
        genes_a_mano=genes_a_mano,
        hallazgos=hallazgos,
        errores=errores or {},
    )
