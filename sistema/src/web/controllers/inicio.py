"""Controlador de la página de inicio."""

from flask import Blueprint, render_template

bp = Blueprint("inicio", __name__)


# Pública por ahora: la sesión 4 agrega login_required y rol_requerido.
@bp.get("/")
def index():
    return render_template("inicio/index.html")
