"""Fábrica de la aplicación Flask."""

import os

from cachelib import FileSystemCache
from dotenv import load_dotenv
from flask import Flask
from flask_session import Session

from src.core import database
from src.web import comandos, errores
from src.web.config import CONFIGS
from src.web.controllers import autenticacion, inicio
from src.web.helpers import auth, menu
from src.web.helpers.csrf import csrf


def create_app(env: str | None = None) -> Flask:
    """Crea la app. `env` es development, testing o production (por defecto, APP_ENV)."""
    load_dotenv()
    env = env or os.getenv("APP_ENV", "development")
    if env not in CONFIGS:
        raise ValueError(f"APP_ENV desconocido: {env!r}. Opciones: {', '.join(CONFIGS)}")

    app = Flask(__name__)
    app.config.from_object(CONFIGS[env]())

    database.init_app(app)
    _init_sesion(app)
    auth.init_app(app)
    # Después de auth: si el token falla, la página de error ya conoce al usuario logueado.
    csrf.init_app(app)
    menu.init_app(app)
    comandos.registrar(app)
    # Sesión 6: Flask-Mail.

    app.register_blueprint(autenticacion.bp)
    app.register_blueprint(inicio.bp)
    errores.registrar(app)

    return app


def _init_sesion(app: Flask) -> None:
    """Flask-Session con cachelib. Por defecto, un archivo por sesión en instance/sesiones."""
    if app.config["SESSION_CACHELIB"] is None:
        carpeta = os.path.join(app.instance_path, "sesiones")
        app.config["SESSION_CACHELIB"] = FileSystemCache(carpeta, threshold=2000)
    Session(app)
