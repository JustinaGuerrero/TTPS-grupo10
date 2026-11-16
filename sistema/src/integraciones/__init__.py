"""Clientes de las APIs externas: uno por API en src/integraciones/<api>.py (decisión S10).

base.py tiene el cliente común (timeout de 5 s, ErrorDeIntegracion con mensaje legible y modo
mock con USE_MOCKS=1); mail.py manda los mails de las notificaciones con Flask-Mail.
"""
