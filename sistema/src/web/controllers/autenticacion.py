"""Inicio y cierre de sesión, verificación de dispositivo y activación de pacientes (E04, E05)."""

import secrets

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from src.core.database import db
from src.core.usuarios import (
    buscar_por_id,
    cambiar_contrasena_provisoria,
    roles,
    validar_credenciales,
)
from src.core.usuarios.verificacion import (
    calcular_huella_hash,
    dispositivo_confiable,
    emitir_codigo,
    validar_codigo,
)
from src.integraciones import mail
from src.web.helpers import auth
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("autenticacion", __name__)

COOKIE_DISPOSITIVO = "exoma_dispositivo"
DURACION_COOKIE_DISPOSITIVO = 365 * 24 * 60 * 60


# Es la única ruta pública de acceso (junto con registro y los archivos estáticos).
@bp.route("/login", methods=["GET", "POST"])
def iniciar_sesion():
    siguiente = auth.destino_seguro(request.values.get("next"))
    if g.usuario is not None:
        flash(
            f"Ya iniciaste sesión como {g.usuario.nombre_completo}. "
            "Para entrar con otra cuenta, cerrá sesión.",
            "aviso",
        )
        return redirect(siguiente or url_for("inicio.index"))
    if auth.verificacion_pendiente() is not None:
        return redirect(url_for("autenticacion.verificar_codigo"))
    if request.method == "GET":
        return render_template("autenticacion/login.html", siguiente=siguiente)

    email = request.form.get("email", "").strip()
    contrasena = request.form.get("contrasena", "")
    if not email or not contrasena:
        flash("Completá el mail y la contraseña.", "error")
        return _formulario(email, siguiente), 400

    usuario = validar_credenciales(email, contrasena)
    if usuario is None:
        flash("El mail o la contraseña no son correctos.", "error")
        return _formulario(email, siguiente), 401

    cookie = request.cookies.get(COOKIE_DISPOSITIVO)
    if not cookie or len(cookie) > 128:
        cookie = secrets.token_urlsafe(32)
    huella_hash = calcular_huella_hash(
        cookie, request.remote_addr or "", current_app.config["SECRET_KEY"]
    )
    if dispositivo_confiable(usuario.id, huella_hash):
        db.session.commit()
        auth.iniciar_sesion_de(usuario)
        flash(f"Hola, {usuario.nombre}.", "exito")
        return _redirigir_con_cookie(_destino_despues_del_login(usuario, siguiente), cookie)

    codigo, valor = emitir_codigo(usuario.id, huella_hash)
    db.session.commit()
    auth.iniciar_verificacion_pendiente(usuario.id, codigo.id, huella_hash, cookie, siguiente)
    if _enviar_codigo(usuario, valor):
        flash("Te enviamos un código de verificación a tu mail.", "info")
    else:
        flash("No se pudo enviar el código. Podés intentar reenviarlo.", "error")
    return redirect(url_for("autenticacion.verificar_codigo"))


@bp.route("/verificar", methods=["GET", "POST"])
@login_required
@rol_requerido(*roles.TODOS)
def verificar_codigo():
    pendiente = auth.verificacion_pendiente()
    if pendiente is None:
        flash("Iniciá sesión para continuar.", "aviso")
        return redirect(url_for("autenticacion.iniciar_sesion"))
    if request.method == "GET":
        return render_template("autenticacion/verificacion.html", error=None)

    usuario = buscar_por_id(pendiente.usuario_id)
    if usuario is None or not usuario.activo:
        db.session.rollback()
        auth.cerrar_sesion()
        flash("El mail o la contraseña no son correctos.", "error")
        return redirect(url_for("autenticacion.iniciar_sesion"))

    valor = request.form.get("codigo", "").strip()
    valido = validar_codigo(pendiente.codigo_id, pendiente.usuario_id, pendiente.huella_hash, valor)
    db.session.commit()
    if not valido:
        return (
            render_template(
                "autenticacion/verificacion.html",
                error="El código no es válido o venció. Podés pedir uno nuevo.",
            ),
            400,
        )

    auth.iniciar_sesion_de(usuario)
    flash(f"Hola, {usuario.nombre}.", "exito")
    destino = _destino_despues_del_login(usuario, pendiente.siguiente)
    return _redirigir_con_cookie(destino, pendiente.cookie_dispositivo)


@bp.post("/verificar/reenviar")
@login_required
@rol_requerido(*roles.TODOS)
def reenviar_codigo():
    pendiente = auth.verificacion_pendiente()
    if pendiente is None:
        flash("Iniciá sesión para continuar.", "aviso")
        return redirect(url_for("autenticacion.iniciar_sesion"))

    usuario = buscar_por_id(pendiente.usuario_id)
    if usuario is None or not usuario.activo:
        db.session.rollback()
        auth.cerrar_sesion()
        flash("El mail o la contraseña no son correctos.", "error")
        return redirect(url_for("autenticacion.iniciar_sesion"))

    codigo, valor = emitir_codigo(usuario.id, pendiente.huella_hash)
    db.session.commit()
    auth.actualizar_codigo_pendiente(codigo.id)
    if _enviar_codigo(usuario, valor):
        flash("Te enviamos un nuevo código de verificación.", "info")
    else:
        flash("No se pudo enviar el código. Podés intentar reenviarlo.", "error")
    return redirect(url_for("autenticacion.verificar_codigo"))


@bp.route("/cambiar-contrasena", methods=["GET", "POST"])
@login_required
@rol_requerido(*roles.TODOS)
def cambiar_contrasena():
    if not g.usuario.debe_cambiar_contrasena:
        destino = (
            url_for("historial.listar")
            if g.usuario.tiene_rol(roles.PACIENTE)
            else url_for("inicio.index")
        )
        return redirect(destino)

    errores = {}
    if request.method == "POST":
        errores = cambiar_contrasena_provisoria(
            g.usuario,
            request.form.get("contrasena", ""),
            request.form.get("confirmar_contrasena", ""),
        )
        if not errores:
            db.session.commit()
            flash("Tu contraseña se actualizó.", "exito")
            return redirect(url_for("historial.listar"))
        flash("Revisá los datos de la contraseña.", "error")

    return render_template("autenticacion/cambiar_contrasena.html", errores=errores), (
        400 if errores else 200
    )


@bp.post("/logout")
@login_required
@rol_requerido(*roles.TODOS)
def cerrar_sesion():
    auth.cerrar_sesion()
    flash("Cerraste la sesión.", "info")
    return redirect(url_for("autenticacion.iniciar_sesion"))


def _enviar_codigo(usuario, codigo: str) -> bool:
    cuerpo = (
        f"Hola, {usuario.nombre}:\n\n"
        "Usá este código para confirmar el ingreso al sistema de exoma clínico:\n\n"
        f"  {codigo}\n\n"
        "El código vence en 10 minutos y se puede usar una sola vez. "
        "Si no intentaste ingresar, ignorá este mail.\n\n"
        "--\n"
        "Laboratorio central · Sistema de exoma clínico\n"
        "Este mail se envió automáticamente: no lo respondas.\n"
    )
    return mail.enviar(usuario.email, "Código de verificación", cuerpo)


def _destino_despues_del_login(usuario, siguiente: str | None) -> str:
    if siguiente:
        return siguiente
    if usuario.debe_cambiar_contrasena:
        return url_for("autenticacion.cambiar_contrasena")
    return url_for("inicio.index")


def _redirigir_con_cookie(destino: str, cookie: str):
    respuesta = redirect(destino)
    respuesta.set_cookie(
        COOKIE_DISPOSITIVO,
        cookie,
        max_age=DURACION_COOKIE_DISPOSITIVO,
        httponly=True,
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite="Lax",
        path="/",
    )
    return respuesta


def _formulario(email: str, siguiente: str | None) -> str:
    return render_template("autenticacion/login.html", email=email, siguiente=siguiente)
