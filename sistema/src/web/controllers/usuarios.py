"""Controlador de usuarios (E03 Dar de alta usuario). Es el módulo de referencia.

Solo entra el administrador general. El controlador valida la forma del pedido, llama a core,
decide el commit y renderiza; las reglas de negocio están en src/core/usuarios.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.core.database import db
from src.core.provincias import listar_provincias
from src.core.usuarios import (
    LARGO_MAXIMO,
    BusquedaDeUsuarios,
    DatosDeAlta,
    ErrorDeValidacion,
    buscar_usuarios,
    dar_de_alta_usuario,
    enviar_credenciales,
    listar_roles,
    provincias_con_transportista,
    roles,
    roles_de_alta,
)
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@bp.get("")
@login_required
@rol_requerido(roles.ADMINISTRADOR_GENERAL)
def listar():
    """Grilla de usuarios: búsqueda, filtro por rol, orden y paginación en el servidor."""
    busqueda = BusquedaDeUsuarios.desde(request.args)
    return render_template(
        "usuarios/listar.html",
        busqueda=busqueda,
        pagina=buscar_usuarios(busqueda),
        roles=listar_roles(),
    )


@bp.get("/nuevo")
@login_required
@rol_requerido(roles.ADMINISTRADOR_GENERAL)
def nuevo():
    return _formulario(DatosDeAlta())


@bp.post("/nuevo")
@login_required
@rol_requerido(roles.ADMINISTRADOR_GENERAL)
def crear():
    """Episodios 1 a 4: valida, crea las credenciales de acceso y las manda por mail."""
    datos = DatosDeAlta.desde(request.form)
    try:
        alta = dar_de_alta_usuario(datos)
    except ErrorDeValidacion as error:
        flash("Revisá los datos marcados.", "error")
        return _formulario(datos, error.errores), 400

    if not enviar_credenciales(
        alta.usuario, alta.contrasena, url_for("autenticacion.iniciar_sesion")
    ):
        # Sin el mail nadie conoce la contraseña provisoria: la cuenta no serviría.
        db.session.rollback()
        flash(
            "No se pudo enviar el mail con las credenciales, así que no se creó el usuario. "
            "Probá de nuevo en unos minutos.",
            "error",
        )
        return _formulario(datos), 503

    db.session.commit()
    flash(
        f"Se dio de alta a {alta.usuario.nombre_completo} como {alta.usuario.rol.nombre}. "
        f"Le enviamos sus credenciales de acceso a {alta.usuario.email}.",
        "exito",
    )
    return redirect(url_for("usuarios.listar"))


def _formulario(datos: DatosDeAlta, errores: dict[str, str] | None = None) -> str:
    return render_template(
        "usuarios/nuevo.html",
        datos=datos,
        errores=errores or {},
        roles_de_alta=roles_de_alta(),
        roles_con_matricula=roles.CON_MATRICULA,
        provincias=listar_provincias(),
        provincias_ocupadas=provincias_con_transportista(),
        largo_maximo=LARGO_MAXIMO,
    )
