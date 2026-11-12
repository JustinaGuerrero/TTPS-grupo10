"""Páginas de error propias (403, 404 y 500)."""

from flask import Flask, render_template


def registrar(app: Flask) -> None:
    @app.errorhandler(403)
    def prohibido(error):
        return render_template("errores/403.html"), 403

    @app.errorhandler(404)
    def no_encontrado(error):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_interno(error):
        return render_template("errores/500.html"), 500
