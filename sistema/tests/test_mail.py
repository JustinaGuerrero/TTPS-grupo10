"""Envío de mails: la conexión SMTP tiene el timeout de las integraciones (CLAUDE.md, 5 s)."""

from src.integraciones import mail as modulo_mail
from src.integraciones.base import TIMEOUT_EN_SEGUNDOS
from src.integraciones.mail import mail


def test_la_conexion_smtp_usa_el_timeout_de_las_integraciones(app, monkeypatch):
    abiertas = []

    class SmtpFalso:
        def __init__(self, servidor, puerto, timeout=None):
            abiertas.append((servidor, puerto, timeout))

        def set_debuglevel(self, nivel):
            pass

        def starttls(self):
            pass

        def login(self, usuario, contrasena):
            pass

    monkeypatch.setattr(modulo_mail.smtplib, "SMTP", SmtpFalso)
    with app.app_context():
        conexion = mail.connect()
        conexion.configure_host()

    assert abiertas == [(app.config["MAIL_SERVER"], app.config["MAIL_PORT"], TIMEOUT_EN_SEGUNDOS)]


def test_un_servidor_que_no_responde_no_rompe_el_envio(app, monkeypatch):
    def colgado(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(mail, "send", colgado)
    with app.app_context():
        assert modulo_mail.enviar("ana@exoma.test", "Asunto", "Cuerpo") is False
