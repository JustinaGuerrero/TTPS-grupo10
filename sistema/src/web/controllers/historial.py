"""Controlador del historial de estudios (E11). Entran el paciente y el médico tratante.

El paciente ve solo su estudio y el médico tratante solo los de sus pacientes. Un estudio o un
análisis ajeno responde 404, igual que uno inexistente, para no revelar que existe. Las consultas
están en src/core/historial; este controlador no cambia datos.
"""

from io import BytesIO

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from src.core.historial import (
    BusquedaDeEstudios,
    analisis_visible,
    estudio_del_paciente,
    estudio_visible,
    estudios_del_medico,
)
from src.core.usuarios import roles
from src.integraciones import storage
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("historial", __name__, url_prefix="/historial")


@bp.get("")
@login_required
@rol_requerido(roles.PACIENTE, roles.MEDICO_TRATANTE)
def listar():
    """Episodios 1 y 2: cada estudio con su estado actual. El médico busca por DNI o nombre."""
    if g.usuario.tiene_rol(roles.PACIENTE):
        estudio = estudio_del_paciente(g.usuario)
        return render_template(
            "historial/listado.html", estudios=[estudio] if estudio else [], pagina=None
        )
    busqueda = BusquedaDeEstudios.desde(request.args)
    pagina = estudios_del_medico(g.usuario, busqueda)
    return render_template(
        "historial/listado.html", estudios=pagina.items, pagina=pagina, busqueda=busqueda
    )


@bp.get("/estudios/<int:estudio_id>")
@login_required
@rol_requerido(roles.PACIENTE, roles.MEDICO_TRATANTE)
def detalle(estudio_id: int):
    """Episodios 3 y 4: detalle, línea de tiempo de estados y análisis con su resultado."""
    estudio = estudio_visible(g.usuario, estudio_id)
    if estudio is None:
        abort(404)
    return render_template("historial/detalle.html", estudio=estudio)


@bp.get("/analisis/<int:analisis_id>/resultado")
@login_required
@rol_requerido(roles.PACIENTE, roles.MEDICO_TRATANTE)
def descargar_resultado(analisis_id: int):
    """Episodio 4: descarga el PDF del resultado del análisis desde Storage."""
    analisis = analisis_visible(g.usuario, analisis_id)
    if analisis is None or not analisis.resultado_path:
        abort(404)
    try:
        contenido = storage.bajar(analisis.resultado_path)
    except ErrorDeIntegracion as error:
        if error.status == 404:
            flash("El PDF del resultado todavía no está disponible.", "error")
        else:
            flash(error.mensaje, "error")
        return redirect(url_for("historial.detalle", estudio_id=analisis.estudio_id))
    return send_file(
        BytesIO(contenido),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{analisis.estudio.codigo}-resultado-{analisis.numero}.pdf",
    )
