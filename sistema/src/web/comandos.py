"""Comandos de consola de la app: `poetry run flask seeds`."""

import click
from flask import Flask, current_app

from src.core import seeds


def registrar(app: Flask) -> None:
    @app.cli.command("seeds")
    def cargar_seeds():
        """Carga los datos de prueba: un usuario por cada uno de los 7 roles del LEL."""
        contrasena = current_app.config.get("SEEDS_CONTRASENA")
        if not contrasena:
            raise click.ClickException(
                "Falta SEEDS_CONTRASENA: es la contraseña de los usuarios de prueba "
                "(ver .env.example)."
            )
        for email, rol, creado in seeds.cargar_usuarios_de_prueba(contrasena):
            estado = "creado    " if creado else "ya existía"
            click.echo(f"{estado}  {rol:<22} {email}")
        click.echo("Los usuarios creados entran con la contraseña de SEEDS_CONTRASENA.")
