"""Controlador de la orden del día (E23 Generar orden del día, E24 Retirar muestras).

- Transportista: ve su orden de hoy en el celular y registra el retiro en cada centro, en el
  orden fijo del recorrido. Una parada que no es de su orden responde 404.
- Administrativo: ve las órdenes de una fecha y regenera las de hoy a mano, por ejemplo si el
  módulo de recorridos falló a la mañana (G5).

El controlador valida la forma del pedido, llama a core, decide el commit y renderiza.
"""

from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from src.core.calendario import hoy
from src.core.database import db
from src.core.estudios import TransicionInvalida
from src.core.logistica.servicios import (
    ErrorDeRetiro,
    buscar_parada,
    generar_ordenes,
    muestras_por_retirar,
    muestras_retiradas,
    orden_de_hoy,
    ordenes_de,
    registrar_retiro,
    siguiente_parada,
)
from src.core.usuarios import roles
from src.web.helpers.auth import login_required, rol_requerido

bp = Blueprint("logistica", __name__)


# --- transportista: E24 Retirar muestras ------------------------------------------------------


@bp.get("/orden-del-dia")
@login_required
@rol_requerido(roles.TRANSPORTISTA)
def orden_del_dia():
    """E23.5 y E24.1: la orden de hoy, con cada centro, su dirección y el botón de retiro."""
    orden = orden_de_hoy(g.usuario)
    return render_template(
        "logistica/orden_del_dia.html",
        orden=orden,
        siguiente=siguiente_parada(orden) if orden else None,
        muestras=_muestras_por_parada(orden) if orden else {},
    )


@bp.post("/orden-del-dia/paradas/<int:posicion>/retiro")
@login_required
@rol_requerido(roles.TRANSPORTISTA)
def registrar_retiro_de_parada(posicion: int):
    """E24.3 y E24.4: registra el retiro en la parada y pasa sus estudios a En camino."""
    orden = orden_de_hoy(g.usuario)
    parada = buscar_parada(orden, posicion) if orden else None
    if parada is None:
        abort(404)
    try:
        estudios = registrar_retiro(parada, g.usuario)
    except (ErrorDeRetiro, TransicionInvalida) as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("logistica.orden_del_dia"))
    db.session.commit()
    cantidad = f"{len(estudios)} muestra{'s' if len(estudios) != 1 else ''}"
    flash(f"Registraste el retiro de {cantidad} en {parada.centro.nombre}.", "exito")
    return redirect(url_for("logistica.orden_del_dia"))


# --- administrativo: E23 Generar orden del día ------------------------------------------------


@bp.get("/ordenes-del-dia")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def ordenes():
    """Las órdenes del día de una fecha (hoy, si no se elige otra), con el avance del retiro."""
    fecha = _fecha_del_pedido(request.args.get("fecha")) or hoy()
    return render_template(
        "logistica/ordenes.html", fecha=fecha, hoy=hoy(), ordenes=ordenes_de(fecha)
    )


@bp.post("/ordenes-del-dia/generar")
@login_required
@rol_requerido(roles.ADMINISTRATIVO)
def generar():
    """E23 a mano: genera las órdenes de hoy que falten (no duplica las que ya están)."""
    generacion = generar_ordenes()
    db.session.commit()
    if generacion.con_error or generacion.sin_transportista:
        categoria = "error"
    elif generacion.nuevas:
        categoria = "exito"
    else:
        categoria = "aviso"
    flash(f"Órdenes del día: {generacion}", categoria)
    return redirect(url_for("logistica.ordenes"))


# --- helpers ---------------------------------------------------------------------------------


def _muestras_por_parada(orden) -> dict[int, int]:
    """Por posición: las muestras que se llevó (parada retirada) o que hay para llevar."""
    return {
        parada.posicion: (
            muestras_retiradas(parada)
            if parada.retirado_en is not None
            else muestras_por_retirar(parada.centro)
        )
        for parada in orden.paradas
    }


def _fecha_del_pedido(texto: str | None) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None
