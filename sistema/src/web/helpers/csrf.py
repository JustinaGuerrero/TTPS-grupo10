"""Protección CSRF de todos los formularios con CSRFProtect de Flask-WTF.

Todo request POST, PUT, PATCH o DELETE tiene que traer el token de la sesión; si no, responde 400.
- En un formulario:  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
- En un fetch():     el header X-CSRFToken con el valor de csrf_token().

Una ruta que llama un sistema externo sin sesión (por ejemplo FedEx en E31) se exime con
@csrf.exempt y valida a quien la llama de otra forma.
"""

from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
