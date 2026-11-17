"""Controlador de los datos crudos (E32) y de la nueva extracción (E27), del administrativo.

- GET /datos-crudos: los estudios En viaje a Corea, cada uno con la carga del .txt de datos
  crudos y el formulario para registrar que el laboratorio avisó que la muestra no sirve.
- POST /estudios/<id>/datos-crudos: carga los datos crudos. Un archivo inválido responde 400.
- POST /estudios/<id>/nueva-extraccion: devuelve el estudio a Requiere nueva extracción.

El controlador valida la forma del pedido, llama a core, decide el commit y renderiza.
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.analisis import (
    TAMANO_MAXIMO_DE_LOS_DATOS_CRUDOS,
    ErrorDeAnalisis,
    cargar_datos_crudos,
    estudios_en_viaje,
)
from src.core.database import db
from src.core.estudios import TransicionInvalida
from src.core.muestras.nueva_extraccion import (
    ErrorDeNuevaExtraccion,
    MotivoNuevaExtraccion,
    muestra_vigente,
    solicitar_nueva_extraccion,
)
from src.core.pagos import buscar_estudio
from src.core.usuarios import roles
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("datos_crudos", __name__)


@bp.get("/datos-crudos")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def listado():
    """E32.1: los estudios que esperan los datos crudos del laboratorio de Corea."""
    return _listado()


@bp.post("/estudios/<int:estudio_id>/datos-crudos")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def cargar(estudio_id: int):
    """E32.3 a E32.5: guarda el .txt y pasa el estudio a En área de bioinformática."""
    estudio = _estudio_o_404(estudio_id)
    archivo = request.files.get("datos_crudos")
    contenido = archivo.read(TAMANO_MAXIMO_DE_LOS_DATOS_CRUDOS + 1) if archivo else b""
    try:
        cargar_datos_crudos(estudio, g.usuario, contenido)
    except (ErrorDeAnalisis, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return _listado(400)
    except ErrorDeIntegracion as error:
        db.session.rollback()
        flash(error.mensaje, "error")
        return _listado(503)
    db.session.commit()
    flash(
        f"Cargaste los datos crudos del estudio {estudio.codigo}: ya está en el área de "
        "bioinformática.",
        "exito",
    )
    return redirect(url_for("datos_crudos.listado"))


@bp.post("/estudios/<int:estudio_id>/nueva-extraccion")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def nueva_extraccion(estudio_id: int):
    """E27.1 a E27.3: el laboratorio avisó que la muestra no sirve; hace falta otra extracción."""
    estudio = _estudio_o_404(estudio_id)
    muestra = muestra_vigente(estudio)
    if muestra is None:
        flash(f"El estudio {estudio.codigo} no tiene una muestra registrada.", "error")
        return redirect(url_for("datos_crudos.listado"))
    try:
        solicitar_nueva_extraccion(
            muestra, request.form.get("motivo", ""), g.usuario, request.form.get("detalle")
        )
    except (ErrorDeNuevaExtraccion, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("datos_crudos.listado"))
    db.session.commit()
    flash(
        f"El estudio {estudio.codigo} pasó a Requiere nueva extracción. Avisamos al paciente y "
        "a su médico.",
        "exito",
    )
    return redirect(url_for("datos_crudos.listado"))


def _listado(status: int = 200):
    return render_template(
        "datos_crudos/listado.html",
        estudios=estudios_en_viaje(),
        motivos=list(MotivoNuevaExtraccion),
    ), status


def _estudio_o_404(estudio_id: int):
    estudio = buscar_estudio(estudio_id)
    if estudio is None:
        abort(404)
    return estudio
