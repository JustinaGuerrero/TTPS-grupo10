"""Fábrica de la aplicación Flask."""

import os

from dotenv import load_dotenv
from flask import Flask

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

    # Sesión 3: base de datos (Flask-SQLAlchemy-Lite).
    # Sesión 4: Flask-Session y comando `flask seeds`.
    # Sesión 6: Flask-Mail.

    app.register_blueprint(inicio.bp)
    errores.registrar(app)

    return app
