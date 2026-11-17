"""Alta y consulta de pacientes del médico tratante (E06, E09)."""

import io
import logging

import sqlalchemy as sa
from flask import (
    Blueprint,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from src.core.database import db
from src.core.estudios.modelos import Estudio
from src.core.pacientes import (
    DatosDeAlta,
    ErrorDeValidacion,
    dar_de_alta,
    listar_del_medico,
    paciente_del_medico,
    reintentar_familiograma,
)
from src.core.pacientes.servicios import guardar_audio
from src.core.patologias import listar_patologias
from src.core.usuarios import enviar_credenciales, roles
from src.integraciones import storage, transcripcion
from src.integraciones.base import ErrorDeIntegracion
from src.web.helpers.auth import login_required, rol_requerido

MAXIMO_AUDIO_BYTES = 10 * 1024 * 1024
log = logging.getLogger(__name__)

bp = Blueprint("pacientes", __name__, url_prefix="/pacientes")


@bp.get("")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def listar():
    busqueda = request.args.get("q", "").strip()
    pacientes = listar_del_medico(g.usuario, busqueda)
    con_estudio = set(
        db.session.scalars(
            sa.select(Estudio.paciente_id).where(
                Estudio.paciente_id.in_([paciente.id for paciente in pacientes])
            )
        )
    )
    return render_template(
        "pacientes/listado.html", pacientes=pacientes, busqueda=busqueda, con_estudio=con_estudio
    )


@bp.get("/nuevo")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def nuevo():
    return _formulario(DatosDeAlta())


@bp.post("/nuevo")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def crear():
    try:
        datos = DatosDeAlta.desde(request.form)
        alta = dar_de_alta(datos, g.usuario)
    except ErrorDeValidacion as error:
        db.session.rollback()
        flash("Revisá los datos marcados; el paciente no se creó.", "error")
        try:
            datos = DatosDeAlta.desde(request.form)
        except ErrorDeValidacion:
            datos = DatosDeAlta()
        return _formulario(datos, error.errores), 400

    paciente = alta.paciente
    db.session.commit()

    audio = request.files.get("resumen_audio")
    if audio is not None:
        contenido_audio = audio.read(MAXIMO_AUDIO_BYTES + 1)
        if len(contenido_audio) > MAXIMO_AUDIO_BYTES:
            flash("El audio supera los 10 MB y no se guardó.", "aviso")
        else:
            if guardar_audio(paciente, contenido_audio):
                db.session.commit()

    hubo_familiograma = False
    if paciente.familiares:
        try:
            hubo_familiograma = reintentar_familiograma(paciente)
            if hubo_familiograma:
                db.session.commit()
        except ErrorDeIntegracion as error:
            log.warning(
                "No se pudo generar el familiograma del paciente %s: %s",
                paciente.id,
                error.mensaje,
            )

    envio = enviar_credenciales(
        paciente.usuario, alta.contrasena, url_for("autenticacion.iniciar_sesion")
    )
    if envio:
        flash(
            f"Se dio de alta a {paciente.usuario.nombre_completo}. "
            f"Enviamos sus credenciales a {paciente.usuario.email}.",
            "exito",
        )
    else:
        flash(
            "El paciente se creó, pero no se pudo enviar el mail con sus credenciales.",
            "error",
        )
    if paciente.familiares and not hubo_familiograma:
        flash("El familiograma quedó pendiente; podés reintentarlo desde el detalle.", "aviso")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente.id))


@bp.post("/transcribir")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def transcribir():
    archivo = request.files.get("audio")
    if archivo is None:
        return jsonify({"error": "Adjuntá un audio para transcribir."}), 400
    audio = archivo.read(MAXIMO_AUDIO_BYTES + 1)
    if not audio:
        return jsonify({"error": "El audio está vacío."}), 400
    if len(audio) > MAXIMO_AUDIO_BYTES:
        return jsonify({"error": "El audio no puede superar los 10 MB."}), 413
    try:
        texto = transcripcion.transcribir(audio)
    except ErrorDeIntegracion as error:
        return jsonify({"error": error.mensaje}), 503
    return jsonify({"texto": texto})


@bp.get("/<int:paciente_id>")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def detalle(paciente_id: int):
    paciente = _paciente_o_404(paciente_id)
    ids_vinculados = {
        familiar.paciente_vinculado_id
        for familiar in paciente.familiares
        if familiar.paciente_vinculado_id is not None
    }
    estudios = (
        db.session.scalars(sa.select(Estudio).where(Estudio.paciente_id.in_(ids_vinculados))).all()
        if ids_vinculados
        else []
    )
    estudio_por_paciente = {estudio.paciente_id: estudio for estudio in estudios}
    vinculados = {
        familiar.id: estudio_por_paciente.get(familiar.paciente_vinculado_id)
        for familiar in paciente.familiares
        if familiar.paciente_vinculado_id is not None
    }
    return render_template(
        "pacientes/detalle.html",
        paciente=paciente,
        estudio=db.session.scalar(sa.select(Estudio).where(Estudio.paciente_id == paciente.id)),
        estudios_vinculados=vinculados,
    )


@bp.post("/<int:paciente_id>/familiograma")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def regenerar_familiograma(paciente_id: int):
    paciente = _paciente_o_404(paciente_id)
    try:
        reintentar_familiograma(paciente)
        db.session.commit()
    except ErrorDeIntegracion as error:
        flash(f"No se pudo generar el familiograma. {error.mensaje}", "error")
    else:
        flash("Se generó el familiograma.", "exito")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente.id))


@bp.get("/<int:paciente_id>/familiograma.pdf")
@login_required
@rol_requerido(roles.MEDICO_TRATANTE)
def descargar_familiograma(paciente_id: int):
    paciente = _paciente_o_404(paciente_id)
    if not paciente.familiograma_path:
        abort(404)
    try:
        contenido = storage.bajar(paciente.familiograma_path)
    except ErrorDeIntegracion:
        log.exception("No se pudo descargar el familiograma del paciente %s", paciente.id)
        abort(503)
    return send_file(
        io.BytesIO(contenido),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"familiograma-{paciente.id}.pdf",
    )


def _paciente_o_404(paciente_id: int):
    paciente = paciente_del_medico(paciente_id, g.usuario)
    if paciente is None:
        abort(404)
    return paciente


def _formulario(datos: DatosDeAlta, errores: dict[str, str] | None = None):
    familiares = datos.familiares or (None,)
    return render_template(
        "pacientes/formulario.html",
        datos=datos,
        errores=errores or {},
        familiares=familiares,
        patologias_activas=listar_patologias(solo_activas=True),
        patologias=listar_patologias(),
        parentescos=(
            "madre",
            "padre",
            "hermano",
            "hermana",
            "hijo",
            "hija",
            "abuelo",
            "abuela",
            "nieto",
            "nieta",
            "tio",
            "tia",
            "primo",
            "prima",
            "otro",
        ),
        url_busqueda=url_for("snomed.terminos"),
        url_transcripcion=url_for("pacientes.transcribir"),
    )
