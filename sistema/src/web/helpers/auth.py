"""Autenticación web (E04): usuario actual, login_required y rol_requerido(*roles).

Toda ruta lleva los dos decoradores, en este orden:

    from src.core.usuarios import roles
    from src.web.helpers.auth import login_required, rol_requerido

    @bp.get("/usuarios")
    @login_required
    @rol_requerido(roles.ADMINISTRADOR_GENERAL)
    def listar(): ...

En las vistas y plantillas, el usuario logueado está en `g.usuario` (None si no hay sesión).
"""

from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    request,
    session,
    url_for,
)

from src.core.usuarios import Usuario, buscar_por_id, roles

CLAVE_DE_SESION = "usuario_id"


def init_app(app: Flask) -> None:
    app.before_request(cargar_usuario_actual)
    app.after_request(no_guardar_en_el_navegador)


def no_guardar_en_el_navegador(respuesta: Response) -> Response:
    """Ninguna página queda guardada en el navegador; los archivos estáticos sí.

    Así, con el botón Atrás el navegador vuelve a pedir la página: después de cerrar sesión no
    se ven datos de pacientes, y después de entrar no aparece el login con un token vencido.
    """
    if request.endpoint != "static":
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def cargar_usuario_actual() -> None:
    """Antes de cada request deja en g.usuario al usuario de la sesión, o None."""
    g.usuario = None
    if request.endpoint == "static":
        return
    usuario_id = session.get(CLAVE_DE_SESION)
    if usuario_id is None:
        return
    usuario = buscar_por_id(usuario_id)
    if usuario is None or not usuario.activo:
        # Lo borraron o lo desactivaron después de que inició sesión.
        session.clear()
        return
    g.usuario = usuario


def iniciar_sesion_de(usuario: Usuario) -> None:
    session.clear()
    session[CLAVE_DE_SESION] = usuario.id
    # Id de sesión nuevo al entrar, para que nadie pueda fijar uno de antemano. Va después de
    # guardar el usuario porque Flask-Session no regenera una sesión vacía.
    current_app.session_interface.regenerate(session)
    g.usuario = usuario


def cerrar_sesion() -> None:
    session.clear()
    g.usuario = None


def login_required(vista):
    """Si no hay sesión, redirige al login y después vuelve a la página pedida."""

    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.get("usuario") is None:
            return _redirigir_al_login()
        return vista(*args, **kwargs)

    return envoltura


def rol_requerido(*codigos: str):
    """Deja pasar solo a los roles indicados; a los demás les responde 403."""
    if not codigos:
        raise ValueError("rol_requerido necesita al menos un rol (por ejemplo roles.PACIENTE).")
    desconocidos = set(codigos) - set(roles.TODOS)
    if desconocidos:
        raise ValueError(f"Roles desconocidos en rol_requerido: {sorted(desconocidos)}")

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario = g.get("usuario")
            if usuario is None:
                # Por si alguien olvidó @login_required o invirtió el orden.
                return _redirigir_al_login()
            if not usuario.tiene_rol(*codigos):
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def destino_seguro(destino: str | None) -> str | None:
    """Devuelve `destino` solo si es una ruta de este sitio; evita redirigir a otro dominio."""
    if not destino or not destino.startswith("/") or destino.startswith("//") or "\\" in destino:
        return None
    partes = urlsplit(destino)
    if partes.scheme or partes.netloc:
        return None
    return destino


def _redirigir_al_login():
    flash("Iniciá sesión para continuar.", "aviso")
    # Solo se vuelve a páginas pedidas por GET: un POST no se puede repetir con un redirect.
    siguiente = None
    if request.method == "GET":
        siguiente = request.full_path if request.query_string else request.path
    return redirect(url_for("autenticacion.iniciar_sesion", next=siguiente))
