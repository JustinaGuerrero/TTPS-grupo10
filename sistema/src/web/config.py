"""Configuración por entorno. Los valores salen de variables de entorno (.env en desarrollo).

Las clases leen el entorno al instanciarse, no al importarse, para que create_app()
vea lo que cargó load_dotenv() y los tests puedan cambiar variables antes de crear la app.
"""

import os


def _bool(nombre: str, por_defecto: bool = False) -> bool:
    valor = os.getenv(nombre)
    if valor is None or valor == "":
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


class Config:
    DEBUG = False
    TESTING = False

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


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self) -> None:
        super().__init__()
        # En desarrollo los mails no salen: se muestran por consola (sesión 6).
        self.MAIL_SUPPRESS_SEND = True
        if not self.SECRET_KEY:
            self.SECRET_KEY = "dev-no-usar-en-produccion"


class TestingConfig(Config):
    TESTING = True

    def __init__(self) -> None:
        super().__init__()
        # Los tests nunca usan la base compartida de Supabase.
        self.DATABASE_URL = os.getenv("DATABASE_URL_TEST")
        self.SECRET_KEY = "clave-de-tests"
        self.MAIL_SUPPRESS_SEND = True
        self.USE_MOCKS = True


class ProductionConfig(Config):
    def __init__(self) -> None:
        super().__init__()
        faltantes = [n for n in ("SECRET_KEY", "DATABASE_URL") if not getattr(self, n)]
        if faltantes:
            raise RuntimeError(f"Faltan variables de entorno para producción: {', '.join(faltantes)}")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
