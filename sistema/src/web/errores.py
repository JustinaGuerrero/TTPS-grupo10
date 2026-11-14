"""Páginas de error propias (403, 404 y 500, y la del token CSRF inválido)."""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError


def registrar(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def formulario_invalido(error):
        app.logger.warning("Formulario rechazado por CSRF: %s", error.description)
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
