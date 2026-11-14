"""Controlador de la página de inicio: la vista que ve cada rol al entrar (E04, episodio 6)."""

from flask import Blueprint, render_template

from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("inicio", __name__)


@bp.get("/")
@login_required
@rol_requerido(*roles.TODOS)
def index():
    return render_template("inicio/index.html")
