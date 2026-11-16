"""Escribir el registro de cambios (E43): registrar() y diferencias().

Toda función de core que cambia datos de un paciente, un estudio (aparte del estado) o un
sample set arma los cambios con diferencias() y los deja con registrar(), en la misma
transacción que el cambio. registrar() no hace commit: si el cambio se revierte, el registro
también (G16). No hay funciones para editar ni borrar: la base tampoco lo permite.

    antes = {"fecha_nacimiento": paciente.fecha_nacimiento}
    paciente.fecha_nacimiento = nueva
    registrar(
        Entidad.PACIENTE,
        paciente.id,
        usuario,
        Accion.MODIFICACION,
        diferencias(antes, {"fecha_nacimiento": nueva}, ["fecha_nacimiento"]),
    )
"""

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any

from src.core.auditoria.modelos import Accion, Entidad, RegistroDeCambio
from src.core.database import db
from src.core.usuarios.modelos import Usuario

# Un campo cuyo nombre contiene alguno de estos fragmentos no se guarda nunca: contraseñas,
# códigos de verificación, claves y tokens no deben quedar en un registro que se puede consultar.
FRAGMENTOS_SENSIBLES = (
    "contrasena",
    "password",
    "hash",
    "clave",
    "token",
    "secret",
    "api_key",
    "verificacion",
)

Cambios = Mapping[str, tuple[Any, Any]]


def es_campo_sensible(campo: str) -> bool:
    nombre = campo.lower()
    return any(fragmento in nombre for fragmento in FRAGMENTOS_SENSIBLES)


def como_texto(valor: Any) -> str | None:
    """Valor como se guarda: texto, o None si no hay (un texto vacío cuenta como no hay)."""
    if valor is None:
        return None
    if isinstance(valor, Enum):
        valor = valor.value
    elif isinstance(valor, bool):
        valor = "sí" if valor else "no"
    elif isinstance(valor, datetime):
        valor = valor.isoformat(sep=" ", timespec="seconds")
    elif isinstance(valor, date):
        valor = valor.isoformat()
    texto = str(valor).strip()
    return texto or None


def diferencias(antes: Any, despues: Any, campos: Iterable[str]) -> dict[str, tuple[Any, Any]]:
    """Los `campos` que cambiaron, como {campo: (valor anterior, valor nuevo)}.

    `antes` y `despues` son diccionarios o cualquier objeto con esos atributos (un modelo). Se
    comparan como texto, así que 1 y "1" son iguales y "" y None también. Los campos que no
    cambiaron no figuran, y un campo que falta en alguno de los dos cuenta como vacío.
    """
    cambios = {}
    for campo in campos:
        anterior = _leer(antes, campo)
        nuevo = _leer(despues, campo)
        if como_texto(anterior) != como_texto(nuevo):
            cambios[campo] = (anterior, nuevo)
    return cambios


def _leer(origen: Any, campo: str) -> Any:
    if isinstance(origen, Mapping):
        return origen.get(campo)
    return getattr(origen, campo, None)


def registrar(
    entidad: Entidad | str,
    entidad_id: int,
    usuario: Usuario | None,
    accion: Accion | str,
    cambios: Cambios,
    detalle: str | None = None,
) -> list[RegistroDeCambio]:
    """Guarda una fila por campo de `cambios` ({campo: (anterior, nuevo)}) y devuelve las filas.

    `usuario` es quien hizo el cambio, o None si lo hizo el sistema. No hace commit: las filas
    quedan en la transacción de quien llama. Si no hay cambios no guarda nada, y los campos
    sensibles (contraseñas, códigos, claves) se descartan. Un alta lleva el valor anterior
    vacío; una baja, el nuevo. El cambio de estado no se registra acá: lo deja cambiar_estado().
    Lanza ValueError si la entidad o la acción no son válidas, o si la entidad todavía no tiene id.
    """
    entidad = _como(Entidad, entidad, "entidad")
    accion = _como(Accion, accion, "acción")
    if accion is Accion.ESTADO:
        raise ValueError("El cambio de estado ya queda en historial_estados: no se registra acá.")
    if entidad_id is None:
        raise ValueError("La entidad necesita su id: hacé flush() antes de registrar.")

    filas = [
        RegistroDeCambio(
            entidad=entidad,
            entidad_id=entidad_id,
            accion=accion,
            campo=campo,
            valor_anterior=como_texto(anterior),
            valor_nuevo=como_texto(nuevo),
            usuario_id=usuario.id if usuario is not None else None,
            detalle=(detalle or "").strip() or None,
        )
        for campo, (anterior, nuevo) in cambios.items()
        if not es_campo_sensible(campo) and como_texto(anterior) != como_texto(nuevo)
    ]
    if filas:
        db.session.add_all(filas)
        # Asigna el id y la fecha sin confirmar nada: el commit lo decide quien llama.
        db.session.flush()
    return filas


def _como(tipo: type[Enum], valor: Any, nombre: str):
    try:
        return tipo(valor)
    except ValueError:
        raise ValueError(f"{valor!r} no es una {nombre} válida del registro de cambios.") from None
