"""Punto de entrada: `poetry run flask run --debug` encuentra `app` acá."""

from src.web import create_app

app = create_app()
