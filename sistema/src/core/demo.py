"""Pacientes de demo en cualquier estado del estudio, para probar a mano: `flask demo <estado>`.

Hay un solo estudio por paciente (O20), así que cada demo crea un paciente nuevo, con médico
tratante medico@exoma.test (lo crea `flask seeds`), y lleva su estudio desde Creado hasta el
estado pedido por el camino más corto, siempre con crear_estudio() y cambiar_estado().

Algunos estados necesitan filas de tablas que crean otros issues: un turno sacado necesita su
turno, una muestra lista para retirar necesita la muestra… El issue que crea esa tabla agrega una
línea en DATOS_POR_ESTADO con una función que crea esas filas; mientras falte, `flask demo` de ese
estado (o de uno posterior en el camino) falla con un mensaje que dice qué issue la agrega.

    DATOS_POR_ESTADO[EstadoEstudio.TURNO_SACADO] = crear_turno_de_demo   # en el issue #7
"""

import itertools
from collections import deque
from collections.abc import Callable
from datetime import date

import sqlalchemy as sa

from src.core.database import db
from src.core.estudios import TRANSICIONES, EstadoEstudio, Estudio, cambiar_estado, crear_estudio
from src.core.finanzas import Pago, TipoAsiento, TipoPago, registrar_asiento
from src.core.pacientes import Paciente, TipoSospecha
from src.core.pagos import Presupuesto, calcular_importe, cantidad_de_genes
from src.core.usuarios import Medico, buscar_por_email, crear_usuario, roles

MEDICO_DE_DEMO = "medico@exoma.test"
GENES_DE_DEMO = ("GAA",)

# Estado → función que crea, antes de que el estudio pase a ese estado, las filas que necesita.
# Recibe el estudio todavía en el estado anterior. Solo se AGREGAN líneas (guia-issues.md).
DATOS_POR_ESTADO: dict[EstadoEstudio, Callable[[Estudio], None]] = {}


def crear_presupuesto_de_demo(estudio: Estudio) -> None:
    """Presupuesto y asiento del estudio, emitidos por administrativo@exoma.test (E13)."""
    administrativo = buscar_por_email("administrativo@exoma.test")
    if administrativo is None:
        raise DemoImposible("Falta administrativo@exoma.test: corré `flask seeds`.")
    cantidad = cantidad_de_genes(estudio)
    presupuesto = Presupuesto(
        estudio_id=estudio.id,
        cantidad_genes=cantidad,
        total_usd=calcular_importe(cantidad),
        emitido_por=administrativo.id,
    )
    db.session.add(presupuesto)
    db.session.flush()
    registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, estudio, presupuesto.total_usd)


def crear_pago_de_demo(estudio: Estudio) -> None:
    """Pago particular y asiento del estudio Presupuestado (E14)."""
    total = db.session.scalar(
        sa.select(Presupuesto.total_usd).where(Presupuesto.estudio_id == estudio.id)
    )
    pago = Pago(estudio_id=estudio.id, tipo=TipoPago.PARTICULAR, importe_usd=total)
    db.session.add(pago)
    db.session.flush()
    registrar_asiento(TipoAsiento.PAGO_PARTICULAR, estudio, total, pago=pago)


DATOS_POR_ESTADO[EstadoEstudio.PRESUPUESTADO] = crear_presupuesto_de_demo
DATOS_POR_ESTADO[EstadoEstudio.HABILITADO_TURNO] = crear_pago_de_demo

# Estados que no tienen sentido sin filas de un issue posterior, y qué issue las agrega.
FILAS_DE_OTRO_ISSUE: dict[EstadoEstudio, str] = {
    EstadoEstudio.PENDIENTE_AUTORIZACION: "la cobertura de obra social (#17)",
    EstadoEstudio.TURNO_SACADO: "el turno de extracción (#7)",
    EstadoEstudio.LISTO_PARA_RETIRAR: "la muestra (#8)",
    EstadoEstudio.PENDIENTE_AUTORIZACION_MINISTERIAL: "el sample set (#14)",
}


class DemoImposible(Exception):
    """No se puede armar el paciente de demo; el mensaje dice qué hacer."""


def camino_desde_creado(destino: EstadoEstudio | str) -> list[EstadoEstudio]:
    """Estados que recorre un estudio desde Creado hasta `destino`, por el camino más corto."""
    destino = EstadoEstudio(destino)
    anteriores: dict[EstadoEstudio, EstadoEstudio | None] = {EstadoEstudio.CREADO: None}
    pendientes = deque([EstadoEstudio.CREADO])
    while pendientes:
        actual = pendientes.popleft()
        for siguiente in TRANSICIONES[actual]:
            if siguiente not in anteriores:
                anteriores[siguiente] = actual
                pendientes.append(siguiente)
    if destino not in anteriores:
        raise ValueError(f"No se llega a {destino} desde Creado")
    camino = []
    estado: EstadoEstudio | None = destino
    while estado is not None:
        camino.append(estado)
        estado = anteriores[estado]
    return camino[::-1]


def datos_que_faltan(destino: EstadoEstudio | str) -> list[str]:
    """Filas de otros issues que el camino hasta `destino` necesita y todavía nadie crea."""
    return [
        FILAS_DE_OTRO_ISSUE[estado]
        for estado in camino_desde_creado(destino)
        if estado in FILAS_DE_OTRO_ISSUE and estado not in DATOS_POR_ESTADO
    ]


def crear_paciente_de_demo(
    estado: EstadoEstudio | str,
    contrasena: str,
    fecha_nacimiento: date = date(1990, 5, 17),
) -> Estudio:
    """Crea un paciente nuevo con su estudio en `estado` y el historial completo. No hace commit.

    El paciente entra con su mail (demo.N@exoma.test) y `contrasena`. Lanza DemoImposible si
    falta el médico de los seeds o si el camino necesita filas de un issue que todavía no está.
    """
    estado = EstadoEstudio(estado)
    faltan = datos_que_faltan(estado)
    if faltan:
        raise DemoImposible(
            f"Para un estudio en {estado.nombre} falta {', '.join(faltan)}: "
            "la agrega ese issue en DATOS_POR_ESTADO de src/core/demo.py."
        )
    medico = buscar_por_email(MEDICO_DE_DEMO)
    if medico is None or db.session.get(Medico, medico.id) is None:
        raise DemoImposible(f"Falta el médico tratante {MEDICO_DE_DEMO}: corré `flask seeds`.")

    numero = _proximo_numero()
    usuario = crear_usuario(
        f"demo.{numero}@exoma.test", contrasena, "Paciente", f"Demo {numero}", roles.PACIENTE
    )
    paciente = Paciente(
        usuario=usuario,
        dni=f"8{numero:07d}",
        fecha_nacimiento=fecha_nacimiento,
        tipo_sospecha=TipoSospecha.CLINICA,
        resumen_historia_clinica=f"Paciente de demo para probar el estado {estado.nombre}.",
        medico_tratante_id=medico.id,
    )
    db.session.add(paciente)
    db.session.flush()

    estudio = crear_estudio(
        paciente, medico, genes=GENES_DE_DEMO, evalua_hallazgos_secundarios=False
    )
    for siguiente in camino_desde_creado(estado)[1:]:
        if siguiente in DATOS_POR_ESTADO:
            DATOS_POR_ESTADO[siguiente](estudio)
        cambiar_estado(estudio, siguiente, None, motivo="Paciente de demo (flask demo)")
    return estudio


def _proximo_numero() -> int:
    """El primer N libre para demo.N@exoma.test y su DNI."""
    for numero in itertools.count(1):
        email_usado = buscar_por_email(f"demo.{numero}@exoma.test") is not None
        dni_usado = db.session.scalar(
            sa.select(Paciente.id).where(Paciente.dni == f"8{numero:07d}")
        )
        if not email_usado and dni_usado is None:
            return numero
    raise AssertionError("itertools.count no termina")
