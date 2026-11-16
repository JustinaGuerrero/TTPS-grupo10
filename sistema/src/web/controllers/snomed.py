"""Buscador de términos SNOMED (E07).

Vive acá y no en patologias.py para que lo reutilicen otros issues
(alta de paciente, registro de médicos).
"""

from flask import Blueprint, jsonify, request

from src.core.usuarios import roles
from src.integraciones import snomed as integracion_snomed
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

MINIMO_PARA_BUSCAR = 3

bp = Blueprint("snomed", __name__, url_prefix="/snomed")


@bp.get("/terminos")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE, roles.GERENTE_MEDICO)
def terminos():
    """E07.2 y E07.3: términos SNOMED que coinciden con lo escrito."""
    texto = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "sintoma")

    if len(texto) < MINIMO_PARA_BUSCAR:
        return jsonify([])

    try:
        encontrados = integracion_snomed.buscar_terminos(texto, tipo)
    except ErrorDeIntegracion as error:
        return jsonify({"error": error.mensaje}), 503

    return jsonify([{"codigo": t.codigo, "termino": t.termino} for t in encontrados])
