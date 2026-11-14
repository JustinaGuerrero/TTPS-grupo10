"""Controlador de iniciar y cerrar sesión (E04, sin el código por dispositivo nuevo)."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from src.core.usuarios import roles, validar_credenciales
from src.web.helpers import auth
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("autenticacion", __name__)


# Es la única ruta pública (junto con los archivos estáticos): es la puerta de entrada.
@bp.route("/login", methods=["GET", "POST"])
def iniciar_sesion():
    siguiente = auth.destino_seguro(request.values.get("next"))
    if g.usuario is not None:
        return redirect(siguiente or url_for("inicio.index"))
    if request.method == "GET":
        return render_template("autenticacion/login.html", siguiente=siguiente)

    email = request.form.get("email", "").strip()
    contrasena = request.form.get("contrasena", "")
    if not email or not contrasena:
        flash("Completá el mail y la contraseña.", "error")
        return _formulario(email, siguiente), 400

    usuario = validar_credenciales(email, contrasena)
    if usuario is None:
        flash("El mail o la contraseña no son correctos.", "error")
        return _formulario(email, siguiente), 401

    auth.iniciar_sesion_de(usuario)
    flash(f"Hola, {usuario.nombre}.", "exito")
    return redirect(siguiente or url_for("inicio.index"))


@bp.post("/logout")
@login_required
@rol_requerido(*roles.TODOS)
def cerrar_sesion():
    auth.cerrar_sesion()
    flash("Cerraste la sesión.", "info")
    return redirect(url_for("autenticacion.iniciar_sesion"))


def _formulario(email: str, siguiente: str | None) -> str:
    return render_template("autenticacion/login.html", email=email, siguiente=siguiente)
