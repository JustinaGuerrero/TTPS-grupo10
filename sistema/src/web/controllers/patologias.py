"""Controlador de patologías (E36).

Solo entra el gerente médico. El controlador valida la forma del pedido, guarda los términos
SNOMED elegidos (guardar_termino), llama a core, decide el commit y renderiza. Cada término
viaja del formulario como "codigo|termino". El buscador de síntomas (E07) vive en
controllers/snomed.py para que lo reutilicen otros issues.
"""

import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.database import db
from src.core.patologias import (
    buscar_por_id,
    crear_patologia,
    listar_patologias,
    modificar_sintomas,
)
from src.core.snomed import SINTOMA, guardar_termino
from src.core.usuarios import roles
from src.integraciones import apigen
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("patologias", __name__, url_prefix="/patologias")


@bp.get("")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def listar():
    filas = [{"patologia": p, **_datos_de(p)} for p in listar_patologias()]
    return render_template("patologias/listar.html", filas=filas)


@bp.get("/nueva")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def nueva():
    return _formulario(
        {
            "nombre": "",
            "codigo_apigen": "",
            "herencia": "",
            "genes": "",
            "cardinal": [],
            "secundarios": [],
        }
    )


@bp.post("/nueva")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def crear():
    """E36.1 a E36.4: guarda los términos elegidos, valida, da de alta en Apigen y guarda."""
    datos = _leer_formulario()
    try:
        cardinales = _guardar_terminos(datos["cardinal"])
        secundarios = _guardar_terminos(datos["secundarios"])
        patologia = crear_patologia(
            datos["nombre"],
            datos["codigo_apigen"],
            cardinales,
            secundarios,
            g.usuario,
            herencia=datos["herencia"] or None,
            genes=_separar_genes(datos["genes"]),
        )
    except ErrorDeIntegracion as error:
        # Apigen falló antes de guardar la patología: tampoco queda ningún término.
        db.session.rollback()
        flash(f"No se guardó la patología. {error.mensaje}", "error")
        return _formulario(datos), 503
    except ValueError as error:  # PatologiaInvalida y los errores de guardar_termino
        db.session.rollback()
        flash(str(error), "error")
        return _formulario(datos), 400

    db.session.commit()
    flash(f"Se dio de alta la patología {patologia.nombre}.", "exito")
    return redirect(url_for("patologias.listar"))


@bp.get("/<int:patologia_id>/editar")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def editar(patologia_id: int):
    patologia = _o_404(patologia_id)
    return _formulario(_datos_de(patologia), patologia)


@bp.post("/<int:patologia_id>/editar")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def modificar(patologia_id: int):
    """E36.5: cambia el síntoma cardinal y los secundarios. Nombre y genes no se tocan."""
    patologia = _o_404(patologia_id)
    datos = _leer_formulario()
    try:
        cardinales = _guardar_terminos(datos["cardinal"])
        secundarios = _guardar_terminos(datos["secundarios"])
        modificar_sintomas(patologia, cardinales, secundarios)
    except ValueError as error:
        db.session.rollback()
        datos["nombre"] = patologia.nombre
        datos["codigo_apigen"] = patologia.codigo_apigen
        flash(str(error), "error")
        return _formulario(datos, patologia), 400

    db.session.commit()
    flash(f"Se actualizaron los síntomas de {patologia.nombre}.", "exito")
    return redirect(url_for("patologias.listar"))


@bp.post("/<int:patologia_id>/activa")
@login_required
@rol_requerido(roles.GERENTE_MEDICO)
def cambiar_activa(patologia_id: int):
    """Activa o desactiva la patología. No hay bajas: una inactiva no se ofrece en E08."""
    patologia = _o_404(patologia_id)
    patologia.activa = not patologia.activa
    db.session.commit()
    estado = "activada" if patologia.activa else "desactivada"
    flash(f"La patología {patologia.nombre} quedó {estado}.", "exito")
    return redirect(url_for("patologias.listar"))


# --- helpers ---------------------------------------------------------------------------------


def _o_404(patologia_id: int):
    patologia = buscar_por_id(patologia_id)
    if patologia is None:
        abort(404)
    return patologia


def _leer_terminos(campo: str) -> list[tuple[str, str]]:
    """Lee los valores "codigo|termino" del formulario. Los vacíos se ignoran."""
    terminos = []
    for valor in request.form.getlist(campo):
        if not valor.strip():
            continue
        codigo, _, texto = valor.partition("|")
        terminos.append((codigo.strip(), texto.strip()))
    return terminos


def _leer_formulario() -> dict:
    return {
        "nombre": request.form.get("nombre", "").strip(),
        "codigo_apigen": request.form.get("codigo_apigen", "").strip(),
        "herencia": request.form.get("herencia", "").strip(),
        "genes": request.form.get("genes", ""),
        "cardinal": _leer_terminos("cardinal"),
        "secundarios": _leer_terminos("secundarios"),
    }


def _guardar_terminos(terminos: list[tuple[str, str]]) -> list[str]:
    """_validar_sintomas exige que cada término ya esté en terminos_snomed: se guardan antes."""
    for codigo, texto in terminos:
        guardar_termino(codigo, texto, SINTOMA)
    return [codigo for codigo, _ in terminos]


def _separar_genes(texto: str) -> list[str]:
    return [gen.strip() for gen in re.split(r"[,;\n]", texto or "") if gen.strip()]


def _datos_de(patologia) -> dict:
    """Los datos de una patología en la forma que usan el formulario y el listado."""
    cardinal = [(f.termino_codigo, f.termino.termino) for f in patologia.sintomas if f.es_cardinal]
    secundarios = sorted(
        ((f.termino_codigo, f.termino.termino) for f in patologia.sintomas if not f.es_cardinal),
        key=lambda t: t[1],
    )
    return {
        "nombre": patologia.nombre,
        "codigo_apigen": patologia.codigo_apigen,
        "herencia": "",
        "genes": "",
        "cardinal": cardinal,
        "secundarios": secundarios,
    }


def _formulario(datos: dict, patologia=None) -> str:
    return render_template(
        "patologias/formulario.html",
        datos=datos,
        patologia=patologia,
        herencias=list(apigen.Herencia),
        url_busqueda=url_for("snomed.terminos"),
    )
