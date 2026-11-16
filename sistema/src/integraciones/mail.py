"""Envío de mails con Flask-Mail (decisión S11).

En desarrollo y en los tests (MAIL_SUPPRESS_SEND) el mail no sale: se muestra por consola con
current_app.logger, que en modo debug muestra los info. Los tests lo ven con
`mail.record_messages()`.

Uso:

    from src.integraciones import mail
    enviado = mail.enviar("ana@x.com", "Asunto", "Cuerpo en texto plano")
"""

import smtplib

from flask import Flask, current_app
from flask_mail import Connection, Mail, Message

from src.integraciones.base import TIMEOUT_EN_SEGUNDOS


class _ConexionConTimeout(Connection):
    """Conexión SMTP con el timeout de las integraciones (5 s).

    Flask-Mail 0.10 abre smtplib.SMTP sin timeout: un servidor que no responde dejaría colgado el
    request, y en E03 también la transacción del alta, que espera al mail antes del commit.
    Repite configure_host() de Flask-Mail agregando solo el timeout.
    """

    def configure_host(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        estado = self.mail
        if estado.use_ssl:
            host = smtplib.SMTP_SSL(estado.server, estado.port, timeout=TIMEOUT_EN_SEGUNDOS)
        else:
            host = smtplib.SMTP(estado.server, estado.port, timeout=TIMEOUT_EN_SEGUNDOS)
        host.set_debuglevel(int(estado.debug))
        if estado.use_tls:
            host.starttls()
        if estado.username and estado.password:
            host.login(estado.username, estado.password)
        return host


class _MailConTimeout(Mail):
    def connect(self) -> Connection:
        return _ConexionConTimeout(current_app.extensions["mail"])


mail = _MailConTimeout()


def init_app(app: Flask) -> None:
    mail.init_app(app)


def url_absoluta(ruta: str) -> str:
    """Link para un mail: URL_BASE más la ruta del sistema (por ejemplo, /avisos)."""
    return current_app.config["URL_BASE"] + ruta


def enviar(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Manda un mail en texto plano. Devuelve False si no se pudo, sin lanzar la excepción.

    Un mail que no sale no rompe el escenario que lo mandó: queda registrado en el log y quien
    llama decide qué hacer (notificar() deja mail_enviado_en en nulo).
    """
    mensaje = Message(subject=asunto, recipients=[destinatario], body=cuerpo)
    try:
        mail.send(mensaje)
    except Exception:
        # Cualquier falla: SMTP caído, credenciales mal, falta MAIL_DEFAULT_SENDER, etc.
        current_app.logger.exception("No se pudo mandar el mail «%s» a %s", asunto, destinatario)
        return False

    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        # Solo en desarrollo y tests: así se ve el mail sin un servidor de correo.
        current_app.logger.info(
            "Mail no enviado (MAIL_SUPPRESS_SEND)\nPara: %s\nAsunto: %s\n\n%s",
            destinatario,
            asunto,
            cuerpo,
        )
    return True
