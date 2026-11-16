"""Reglas de negocio de patologías (E36): alta, modificación de síntomas y activación.

Ninguna función hace commit: lo decide quien llama (el controlador o los seeds).
"""

import re
from collections.abc import Iterable

import sqlalchemy as sa

from src.core.database import db
from src.core.patologias.modelos import Patologia, PatologiaSintoma
from src.core.snomed import SINTOMA, TerminoSnomed
from src.core.usuarios import roles
from src.core.usuarios.modelos import Usuario
from src.integraciones import apigen
from src.integraciones.base import ClienteApi


class PatologiaInvalida(ValueError):
    """Los datos no cumplen las reglas de E36. El mensaje se puede mostrar tal cual."""


def listar_patologias(*, solo_activas: bool = False) -> list[Patologia]:
    consulta = sa.select(Patologia).order_by(Patologia.nombre)
    if solo_activas:
        # Una patología inactiva no se ofrece en el diagnóstico presuntivo.
        consulta = consulta.where(Patologia.activa)
    return list(db.session.scalars(consulta))


def buscar_por_id(patologia_id: int) -> Patologia | None:
    return db.session.get(Patologia, patologia_id)


def buscar_por_codigo(codigo: str) -> Patologia | None:
    consulta = sa.select(Patologia).where(Patologia.codigo_apigen == (codigo or "").strip().upper())
    return db.session.scalars(consulta).one_or_none()


def crear_patologia(
    nombre: str,
    codigo_apigen: str,
    cardinales: Iterable[str],
    secundarios: Iterable[str],
    creado_por: Usuario,
    *,
    herencia: apigen.Herencia | str | None = None,
    genes: Iterable[str] | None = None,
    alta_en_apigen: bool = True,
    cliente: ClienteApi | None = None,
) -> Patologia:
    """Da de alta una patología con su síntoma cardinal y sus secundarios (E36.1 a E36.4).

    `cardinales` y `secundarios` son códigos SNOMED ya guardados con guardar_termino. Se pide
    una lista de cardinales para que el servicio también rechace dos.

    Una patología del grupo se da de alta primero en Apigen (endpoint 9) con sus genes: si
    Apigen falla, lanza ErrorDeIntegracion y no se guarda nada. Las 5 patologías base ya
    existen en Apigen: sus seeds usan alta_en_apigen=False.
    """
    if not creado_por.tiene_rol(roles.GERENTE_MEDICO):
        raise PatologiaInvalida("Solo el gerente médico da de alta patologías.")
    nombre = (nombre or "").strip()
    if not nombre:
        raise PatologiaInvalida("Falta el nombre de la patología.")
    codigo = (codigo_apigen or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_]{2,30}", codigo):
        raise PatologiaInvalida("El código va en mayúsculas, números o _, de 2 a 30 caracteres.")
    if db.session.scalar(
        sa.select(Patologia.id).where(sa.func.lower(Patologia.nombre) == nombre.lower())
    ):
        raise PatologiaInvalida("Ya existe una patología con ese nombre.")
    if buscar_por_codigo(codigo) is not None:
        raise PatologiaInvalida("Ya existe una patología con ese código.")
    sintomas = _validar_sintomas(cardinales, secundarios)

    if alta_en_apigen:
        lista_de_genes = [gen for gen in (genes or []) if gen and gen.strip()]
        if not lista_de_genes:
            raise PatologiaInvalida("Elegí al menos un gen.")
        try:
            herencia = apigen.Herencia(herencia or apigen.Herencia.AUTOSOMICA_RECESIVA)
        except ValueError:
            raise PatologiaInvalida("La herencia no es válida.") from None
        # Antes de guardar: si Apigen no responde o rechaza el alta, no queda nada local.
        apigen.alta_patologia(codigo, nombre, lista_de_genes, herencia, cliente=cliente)

    patologia = Patologia(
        codigo_apigen=codigo,
        nombre=nombre,
        creador=creado_por,
        sintomas=[
            PatologiaSintoma(termino_codigo=codigo_snomed, es_cardinal=es_cardinal)
            for codigo_snomed, es_cardinal in sintomas.items()
        ],
    )
    db.session.add(patologia)
    db.session.flush()
    return patologia


def modificar_sintomas(
    patologia: Patologia, cardinales: Iterable[str], secundarios: Iterable[str]
) -> Patologia:
    """Cambia el síntoma cardinal y los secundarios (E36.5). No cambia nombre ni genes."""
    deseados = _validar_sintomas(cardinales, secundarios)
    actuales = {fila.termino_codigo: fila for fila in patologia.sintomas}

    # Primero se sacan los que sobran y se baja la marca de cardinal de los que quedan: el
    # índice único de un solo cardinal no admite dos a la vez ni siquiera de paso.
    for codigo, fila in actuales.items():
        if codigo not in deseados:
            patologia.sintomas.remove(fila)
        else:
            fila.es_cardinal = False
    db.session.flush()

    for codigo, es_cardinal in deseados.items():
        if codigo in actuales:
            actuales[codigo].es_cardinal = es_cardinal
        else:
            patologia.sintomas.append(
                PatologiaSintoma(termino_codigo=codigo, es_cardinal=es_cardinal)
            )
    patologia.actualizado_en = sa.func.now()
    db.session.flush()
    return patologia


def cambiar_activa(patologia: Patologia, activa: bool) -> Patologia:
    """Activa o desactiva la patología. No hay bajas."""
    patologia.activa = activa
    db.session.flush()
    return patologia


def _validar_sintomas(cardinales: Iterable[str], secundarios: Iterable[str]) -> dict[str, bool]:
    """Devuelve {código SNOMED: es_cardinal} o lanza PatologiaInvalida."""
    cardinales = _limpiar(cardinales)
    secundarios = _limpiar(secundarios)
    if not cardinales:
        raise PatologiaInvalida("Falta el síntoma cardinal.")
    if len(cardinales) > 1:
        raise PatologiaInvalida("Una patología tiene un solo síntoma cardinal.")
    if cardinales[0] in secundarios:
        raise PatologiaInvalida("El síntoma cardinal no puede estar también entre los secundarios.")
    sintomas = {cardinales[0]: True, **{codigo: False for codigo in secundarios}}
    for codigo in sintomas:
        termino = db.session.get(TerminoSnomed, codigo)
        if termino is None or termino.tipo != SINTOMA:
            raise PatologiaInvalida(f"Síntoma desconocido: {codigo}")
    return sintomas


def _limpiar(codigos: Iterable[str]) -> list[str]:
    """Sin vacíos ni repetidos, en el orden en que llegaron."""
    return list(dict.fromkeys(c.strip() for c in codigos if c and c.strip()))
