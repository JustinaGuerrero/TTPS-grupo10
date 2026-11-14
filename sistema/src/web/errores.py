"""Páginas de error propias (403, 404 y 500, y la del token CSRF inválido)."""

from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError


def registrar(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def formulario_invalido(error):
        app.logger.warning("Formulario rechazado por CSRF: %s", error.description)
        if request.endpoint == "autenticacion.iniciar_sesion":
            return _login_vencido()
        return render_template("errores/csrf.html"), 400

    @app.errorhandler(403)
    def prohibido(error):
        return render_template("errores/403.html"), 403

    @app.errorhandler(404)
    def no_encontrado(error):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_interno(error):
        return render_template("errores/500.html"), 500


def _login_vencido():
    """El formulario de login era viejo: por ejemplo, quedó abierto en otra pestaña.

    No inicia sesión con nada de lo enviado; solo explica qué pasó y lleva a donde corresponde.
    """
    usuario = g.get("usuario")
    if usuario is not None:
        flash(
            f"Ya iniciaste sesión como {usuario.nombre_completo}. "
            "Para entrar con otra cuenta, cerrá la sesión.",
            "aviso",
        )
        return redirect(url_for("inicio.index"))
    flash("La página de ingreso venció. Ingresá de nuevo.", "aviso")
    return redirect(url_for("autenticacion.iniciar_sesion"))
