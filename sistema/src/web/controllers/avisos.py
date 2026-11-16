"""Controlador de "Mis avisos" (E39, episodio 4): el usuario consulta sus avisos y accede a la
tarea pendiente. Lo ven todos los roles; cada uno ve solo sus avisos."""

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from src.core.database import db
from src.core.notificaciones import avisos_de, marcar_leido
from src.core.usuarios import roles
from src.web.helpers.auth import destino_seguro, login_required, rol_requerido

bp = Blueprint("avisos", __name__, url_prefix="/avisos")


@bp.get("")
@login_required
@rol_requerido(*roles.TODOS)
def listar():
    pagina = request.args.get("pagina", 1, type=int)
    return render_template("avisos/listar.html", pagina=avisos_de(g.usuario, pagina))


@bp.post("/<int:aviso_id>/abrir")
@login_required
@rol_requerido(*roles.TODOS)
def abrir(aviso_id: int):
    """Marca el aviso como leído y lleva a la tarea pendiente."""
    aviso = marcar_leido(aviso_id, g.usuario)
    if aviso is None:
        # Inexistente o de otro usuario: no se distingue, para no revelar que existe.
        abort(404)
    db.session.commit()
    return redirect(destino_seguro(aviso.link) or url_for("avisos.listar"))
