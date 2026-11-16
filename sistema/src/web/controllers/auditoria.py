"""Controlador del registro de cambios (E43).

GET /auditoria es la lista completa, solo del administrador general. GET /auditoria/<entidad>/<id>
es el historial de un paciente, un estudio o un sample set y lo ven los roles de G17. Lo que el
usuario no puede ver responde 404, igual que lo que no existe, para no revelar qué hay.
"""

from flask import Blueprint, abort, g, render_template, request

from src.core.auditoria import (
    Entidad,
    FiltrosDeAuditoria,
    hay_registros_de,
    historial_de,
    listar,
    usuarios_con_registros,
)
from src.core.database import db
from src.core.estudios import Estudio
from src.core.pacientes import Paciente
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("auditoria", __name__, url_prefix="/auditoria")

# Roles que pueden pedir un historial (G17). Cada uno ve solo algunas entidades: ver _titulo_si_puede.
ROLES_DE_HISTORIAL = (roles.MEDICO_TRATANTE, roles.ADMINISTRATIVO, roles.ADMINISTRADOR_GENERAL)


@bp.get("")
@login_required
@rol_requerido(roles.ADMINISTRADOR_GENERAL)
def lista():
    """E43.3: todos los cambios, con filtros por entidad, usuario y fechas, paginados."""
    filtros = FiltrosDeAuditoria.desde_parametros(request.args)
    return render_template(
        "auditoria/lista.html",
        filtros=filtros,
        pagina=listar(filtros),
        entidades=list(Entidad),
        usuarios=usuarios_con_registros(),
    )


@bp.get("/<entidad>/<int:entidad_id>")
@login_required
@rol_requerido(*ROLES_DE_HISTORIAL)
def historial(entidad: str, entidad_id: int):
    """E43.2: línea de tiempo de una entidad, del cambio más nuevo al más viejo."""
    try:
        tipo = Entidad(entidad)
    except ValueError:
        abort(404)
    titulo = _titulo_si_puede(tipo, entidad_id)
    if titulo is None:
        abort(404)
    return render_template(
        "auditoria/historial.html",
        entidad=tipo,
        entidad_id=entidad_id,
        titulo=titulo,
        cambios=historial_de(tipo, entidad_id),
    )


def _titulo_si_puede(entidad: Entidad, entidad_id: int) -> str | None:
    """Cómo se llama lo que se consulta, o None si no existe o el usuario no puede verlo (G17)."""
    usuario = g.usuario
    es_administrador = usuario.tiene_rol(roles.ADMINISTRADOR_GENERAL)

    if entidad is Entidad.PACIENTE:
        paciente = db.session.get(Paciente, entidad_id)
        if paciente is None:
            return None
        if es_administrador or paciente.medico_tratante_id == usuario.id:
            return f"Paciente {paciente.usuario.nombre_completo} (DNI {paciente.dni})"
        return None

    if entidad is Entidad.ESTUDIO:
        estudio = db.session.get(Estudio, entidad_id)
        if estudio is None:
            return None
        if (
            es_administrador
            or usuario.tiene_rol(roles.ADMINISTRATIVO)
            or estudio.paciente.medico_tratante_id == usuario.id
        ):
            return f"Estudio {estudio.codigo}"
        return None

    # Sample set: la tabla sample_sets todavía no existe (E24), así que se lo da por existente
    # si tiene cambios registrados. Cuando exista, esta rama pasa a buscarlo con db.session.get.
    if usuario.tiene_rol(roles.ADMINISTRATIVO, roles.ADMINISTRADOR_GENERAL) and hay_registros_de(
        entidad, entidad_id
    ):
        return f"Sample set n.° {entidad_id}"
    return None
