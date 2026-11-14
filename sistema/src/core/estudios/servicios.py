"""Reglas del estudio: el alta en estado Creado y la máquina de estados.

cambiar_estado() es la única forma de cambiar el estado de un estudio (decisión S9): solo permite
las transiciones del LEL (estados.py) y deja cada cambio en historial_estados con fecha y usuario.
Ninguna función hace commit: lo decide quien llama, como en src/core/usuarios.
"""

from collections.abc import Iterable

import sqlalchemy as sa

from src.core.database import db
from src.core.estudios.estados import EstadoEstudio, TransicionInvalida, puede_pasar
from src.core.estudios.modelos import Analisis, AnalisisGen, Estudio, HistorialEstado, TipoAnalisis
from src.core.pacientes.modelos import Paciente
from src.core.usuarios import roles
from src.core.usuarios.modelos import Medico, Usuario


def crear_estudio(
    paciente: Paciente,
    medico_tratante: Usuario,
    genes: Iterable[str],
    evalua_hallazgos_secundarios: bool,
    genes_agregados_a_mano: Iterable[str] = (),
    pompe_urgente: bool = False,
) -> Estudio:
    """Da de alta el estudio en Creado, con su análisis inicial y la primera fila del historial.

    Es la parte de core de E10 (episodios 2 a 5). `genes` son los que devolvió la API de
    bioinformática para el diagnóstico presuntivo; `genes_agregados_a_mano`, los que sumó el
    médico tratante. Un gen que está en las dos listas cuenta como de Apigen.
    Lanza ValueError si no se cumple una regla del alta.
    """
    if not medico_tratante.tiene_rol(roles.MEDICO_TRATANTE):
        raise ValueError("Solo un médico tratante puede dar de alta un estudio.")
    if db.session.get(Medico, medico_tratante.id) is None:
        raise ValueError("El médico tratante no tiene cargada su matrícula.")
    if paciente.id is not None and _tiene_estudio(paciente):
        raise ValueError(
            "El paciente ya tiene un estudio. Una sospecha nueva se pide como reanálisis."
        )

    de_apigen = _simbolos(genes)
    a_mano = _simbolos(genes_agregados_a_mano) - de_apigen
    if not de_apigen and not a_mano:
        raise ValueError("El estudio necesita al menos un gen para analizar.")

    analisis = Analisis(
        numero=1,
        tipo=TipoAnalisis.INICIAL,
        evalua_hallazgos_secundarios=evalua_hallazgos_secundarios,
        solicitado_por=medico_tratante.id,
        genes=[AnalisisGen(gen_simbolo=gen, agregado_a_mano=False) for gen in sorted(de_apigen)]
        + [AnalisisGen(gen_simbolo=gen, agregado_a_mano=True) for gen in sorted(a_mano)],
    )
    estudio = Estudio(
        paciente=paciente,
        medico_tratante_id=medico_tratante.id,
        estado=EstadoEstudio.CREADO,
        pompe_urgente=pompe_urgente,
        analisis=[analisis],
        historial=[
            HistorialEstado(
                estado_anterior=None,
                estado_nuevo=EstadoEstudio.CREADO,
                usuario_id=medico_tratante.id,
            )
        ],
    )
    db.session.add(estudio)
    # Asigna el id y el código, y deja el estudio en la base para cambiar_estado().
    db.session.flush()
    return estudio


def cambiar_estado(
    estudio: Estudio,
    nuevo_estado: EstadoEstudio | str,
    usuario: Usuario | None,
    motivo: str | None = None,
) -> HistorialEstado:
    """Pasa el estudio a `nuevo_estado` y deja el cambio en historial_estados.

    `usuario` es quien provoca el cambio, o None si lo hace el sistema (bot de mensajería,
    FedEx, tareas programadas). `motivo` es opcional, por ejemplo "volumen de 1,5 ml".
    Lanza TransicionInvalida si el LEL no permite pasar del estado actual al nuevo.

    No controla el rol de `usuario`: lo controlan la ruta (@rol_requerido) y la función del
    escenario que llama, porque una misma transición la provocan actores distintos.
    """
    try:
        destino = EstadoEstudio(nuevo_estado)
    except ValueError:
        raise TransicionInvalida(f"«{nuevo_estado}» no es un estado del estudio.") from None

    # Relee el estado y bloquea la fila hasta el commit. Si dos pedidos cambian el mismo estudio
    # a la vez, el segundo espera al primero y decide sobre el estado que dejó, no sobre uno viejo.
    # El flush va antes porque refresh() descartaría un cambio anterior todavía sin escribir.
    db.session.flush()
    db.session.refresh(estudio, ["estado"], with_for_update=True)
    origen = estudio.estado
    if not puede_pasar(origen, destino):
        raise TransicionInvalida(
            f"El estudio {estudio.codigo} no puede pasar de {origen.nombre} a {destino.nombre}."
        )

    estudio.estado = destino
    cambio = HistorialEstado(
        estudio=estudio,
        estado_anterior=origen,
        estado_nuevo=destino,
        usuario_id=usuario.id if usuario is not None else None,
        motivo=(motivo or "").strip() or None,
    )
    db.session.add(cambio)
    return cambio


def _tiene_estudio(paciente: Paciente) -> bool:
    consulta = sa.select(Estudio.id).where(Estudio.paciente_id == paciente.id)
    return db.session.scalar(consulta) is not None


def _simbolos(genes: Iterable[str]) -> set[str]:
    return {gen.strip() for gen in genes if gen and gen.strip()}
