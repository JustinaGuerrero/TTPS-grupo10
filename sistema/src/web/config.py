"""Configuración por entorno. Los valores salen de variables de entorno (.env en desarrollo).

Las clases leen el entorno al instanciarse, no al importarse, para que create_app()
vea lo que cargó load_dotenv() y los tests puedan cambiar variables antes de crear la app.
"""

import os
from datetime import timedelta

from cachelib import SimpleCache

# Contraseña de los usuarios de prueba de `flask seeds` cuando SEEDS_CONTRASENA está vacía.
# Solo en desarrollo y tests; en producción hay que definirla.
CONTRASENA_DE_SEEDS_POR_DEFECTO = "prueba1234"


def _bool(nombre: str, por_defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None or valor == "":
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


class Config:
    DEBUG = False
    TESTING = False

    # Flask-Session: la sesión se guarda en el servidor (cachelib) y la cookie solo lleva su id.
    # create_app() usa un FileSystemCache en instance/sesiones si SESSION_CACHELIB no está.
    SESSION_TYPE = "cachelib"
    SESSION_CACHELIB = None
    SESSION_PERMANENT = True
    # Se renueva en cada request: la sesión vence tras 8 h sin uso (una jornada de 9 a 18).
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # El token CSRF vive en la sesión y vence con ella (no a la hora, como por defecto).
    WTF_CSRF_TIME_LIMIT = None

    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.DATABASE_URL = os.getenv("DATABASE_URL")

        self.MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
        self.MAIL_PORT = int(os.getenv("MAIL_PORT") or 25)
        self.MAIL_USE_TLS = _bool("MAIL_USE_TLS")
        self.MAIL_USERNAME = os.getenv("MAIL_USERNAME")
        self.MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
        self.MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
        self.MAIL_SUPPRESS_SEND = False

        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.APIGEN_URL = os.getenv("APIGEN_URL")
        self.APIGEN_KEY = os.getenv("APIGEN_KEY")
        self.USE_MOCKS = _bool("USE_MOCKS")
        self.SEEDS_CONTRASENA = os.getenv("SEEDS_CONTRASENA")


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self) -> None:
        super().__init__()
        # En desarrollo los mails no salen: se muestran por consola (sesión 6).
        self.MAIL_SUPPRESS_SEND = True
        if not self.SECRET_KEY:
            self.SECRET_KEY = "dev-no-usar-en-produccion"
        self.SEEDS_CONTRASENA = self.SEEDS_CONTRASENA or CONTRASENA_DE_SEEDS_POR_DEFECTO


class TestingConfig(Config):
    TESTING = True
    # Los tests de cada escenario postean sin token; tests/test_csrf.py la activa y la prueba.
    WTF_CSRF_ENABLED = False

    def __init__(self) -> None:
        super().__init__()
        # Los tests nunca usan la base compartida de Supabase.
        self.DATABASE_URL = os.getenv("DATABASE_URL_TEST")
        self.SECRET_KEY = "clave-de-tests"
        self.MAIL_SUPPRESS_SEND = True
        self.USE_MOCKS = True
        # Sesiones en memoria: cada app de test empieza sin sesiones y no deja archivos.
        self.SESSION_CACHELIB = SimpleCache()
        self.SEEDS_CONTRASENA = CONTRASENA_DE_SEEDS_POR_DEFECTO


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True

    def __init__(self) -> None:
        super().__init__()
        faltantes = [n for n in ("SECRET_KEY", "DATABASE_URL") if not getattr(self, n)]
        if faltantes:
            raise RuntimeError(
                f"Faltan variables de entorno para producción: {', '.join(faltantes)}"
            )


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
