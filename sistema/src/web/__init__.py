"""Fábrica de la aplicación Flask."""

import os

from dotenv import load_dotenv
from flask import Flask

from src.core import database
from src.web import errores
from src.web.config import CONFIGS
from src.web.controllers import inicio


def create_app(env: str | None = None) -> Flask:
    """Crea la app. `env` es development, testing o production (por defecto, APP_ENV)."""
    load_dotenv()
    env = env or os.getenv("APP_ENV", "development")
    if env not in CONFIGS:
        raise ValueError(f"APP_ENV desconocido: {env!r}. Opciones: {', '.join(CONFIGS)}")

    app = Flask(__name__)
    app.config.from_object(CONFIGS[env]())

    database.init_app(app)
    # Sesión 4: Flask-Session y comando `flask seeds`.
    # Sesión 6: Flask-Mail.

    app.register_blueprint(inicio.bp)
    errores.registrar(app)

    return app
