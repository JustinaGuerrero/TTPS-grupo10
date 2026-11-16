"""Auto registro E01/E02 y búsqueda pública de especialidades SNOMED."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from src.core.database import db
from src.core.usuarios import (
    ROLES_DE_REGISTRO,
    DatosDeRegistro,
    ErrorDeValidacion,
    registrar_usuario,
    roles_de_registro,
)
from src.integraciones import snomed as integracion_snomed
from src.integraciones.base import ErrorDeIntegracion

MINIMO_PARA_BUSCAR = 3

# El auto registro y el buscador de especialidades son públicos, igual que /login.
bp = Blueprint("registro", __name__, url_prefix="/registro")


@bp.get("")
def nuevo():
    return _formulario(DatosDeRegistro())


@bp.post("")
def crear():
    datos = _datos_del_formulario()
    try:
        usuario = registrar_usuario(datos)
    except ErrorDeValidacion as error:
        flash("Revisá los datos marcados.", "error")
        return _formulario(datos, error.errores), 400

    db.session.commit()
    flash(f"Tu cuenta quedó creada como {usuario.rol.nombre}. Ya podés iniciar sesión.", "exito")
    return redirect(url_for("autenticacion.iniciar_sesion"))


@bp.get("/especialidades")
def especialidades():
    """Busca especialidades en SNOMED para el formulario público de auto registro."""
    texto = request.args.get("q", "").strip()
    if len(texto) < MINIMO_PARA_BUSCAR:
        return jsonify([])

    try:
        encontrados = integracion_snomed.buscar_terminos(texto, "especialidad")
    except ErrorDeIntegracion as error:
        return jsonify({"error": error.mensaje}), 503

    return jsonify([{"codigo": t.codigo, "termino": t.termino} for t in encontrados])


def _datos_del_formulario() -> DatosDeRegistro:
    especialidades = []
    for valor in request.form.getlist("especialidad"):
        if not valor.strip():
            continue
        codigo, _, termino = valor.partition("|")
        especialidades.append((codigo.strip(), termino.strip()))
    return DatosDeRegistro.desde(request.form, especialidades)


def _formulario(datos: DatosDeRegistro, errores: dict[str, str] | None = None) -> str:
    return render_template(
        "registro/nuevo.html",
        datos=datos,
        errores=errores or {},
        roles_de_registro=roles_de_registro(),
        roles_medicos=ROLES_DE_REGISTRO[:2],
        especialidades=datos.especialidades,
    )
