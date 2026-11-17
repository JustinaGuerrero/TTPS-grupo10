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

# Remitente de los mails en desarrollo y tests cuando MAIL_DEFAULT_SENDER está vacío.
REMITENTE_DE_PRUEBA = "Exoma clínico <no-responder@exoma.test>"


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
        # Dirección pública del sistema, para los links absolutos de los mails.
        self.URL_BASE = (os.getenv("URL_BASE") or "http://localhost:5000").rstrip("/")

        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET") or "documentos"
        # Carpeta de los archivos de storage con USE_MOCKS=1. Vacía: instance/storage.
        self.STORAGE_CARPETA_MOCK = os.getenv("STORAGE_CARPETA_MOCK")
        self.APIGEN_URL = os.getenv("APIGEN_URL")
        self.APIGEN_KEY = os.getenv("APIGEN_KEY")
        self.APIGEN_GRUPO_ID = os.getenv("APIGEN_GRUPO_ID") or "grupo10"
        self.CHATBOT_URL = os.getenv("CHATBOT_URL")
        self.CHATBOT_APIKEY = os.getenv("CHATBOT_APIKEY")
        self.CHATBOT_TOKEN = os.getenv("CHATBOT_TOKEN")
        self.TRANSCRIPCION_URL = os.getenv("TRANSCRIPCION_URL")
        self.FAMILIOGRAMA_URL = os.getenv("FAMILIOGRAMA_URL")
        self.CUPONES_URL = os.getenv("CUPONES_URL")
        self.CUPONES_KEY = os.getenv("CUPONES_KEY")
        self.USE_MOCKS = _bool("USE_MOCKS")
        self.SEEDS_CONTRASENA = os.getenv("SEEDS_CONTRASENA")


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self) -> None:
        super().__init__()
        # Con DATABASE_URL_LOCAL, flask run usa la base local que arma `flask migrar-local`: se
        # prueban las migraciones nuevas sin tocar el Supabase compartido.
        self.DATABASE_URL = os.getenv("DATABASE_URL_LOCAL") or self.DATABASE_URL
        # En desarrollo los mails no salen: se muestran por consola (src/integraciones/mail.py).
        self.MAIL_SUPPRESS_SEND = True
        self.MAIL_DEFAULT_SENDER = self.MAIL_DEFAULT_SENDER or REMITENTE_DE_PRUEBA
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
        self.MAIL_DEFAULT_SENDER = REMITENTE_DE_PRUEBA
        self.URL_BASE = "http://exoma.test"
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
