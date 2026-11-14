"""Máquina de estados del estudio: las 21 transiciones del LEL y las que no están permitidas.

Las listas del LEL se escriben a mano a propósito, en vez de copiarlas de TRANSICIONES: si
alguien agrega o quita una transición en el código, estos tests lo detectan.
"""

import re
from collections import deque

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.database import db
from src.core.estudios import (
    TRANSICIONES,
    EstadoEstudio,
    Estudio,
    HistorialEstado,
    TransicionInvalida,
    cambiar_estado,
    puede_pasar,
)
from src.core.usuarios import roles

# Los 16 estados de "Estados del estudio" en docs/lel.md, con su código de docs/modelo-datos.md.
ESTADOS_DEL_LEL = {
    "creado": "Creado",
    "presupuestado": "Presupuestado",
    "pendiente_autorizacion": "Pendiente de autorización",
    "rechazado_obra_social": "Rechazado por obra social",
    "habilitado_turno": "Habilitado para turno",
    "turno_sacado": "Turno sacado",
    "listo_para_retirar": "Listo para retirar",
    "en_camino_laboratorio": "En camino al laboratorio central",
    "en_laboratorio_central": "En laboratorio central",
    "pendiente_autorizacion_ministerial": "Pendiente de autorización ministerial",
    "pendiente_envio": "Pendiente de envío",
    "en_viaje_corea": "En viaje a Corea",
    "en_area_bioinformatica": "En área de bioinformática",
    "en_analisis": "En análisis",
    "finalizado": "Finalizado",
    "requiere_nueva_extraccion": "Requiere nueva extracción",
}

# Un par (desde, hacia) por cada impacto de los estados del estudio en el LEL.
TRANSICIONES_DEL_LEL = [
    ("creado", "presupuestado"),  # El administrativo emite el presupuesto
    ("presupuestado", "habilitado_turno"),  # El paciente paga de forma particular
    ("presupuestado", "pendiente_autorizacion"),  # El paciente elige su obra social
    ("pendiente_autorizacion", "habilitado_turno"),  # El administrativo registra la autorización
    ("pendiente_autorizacion", "rechazado_obra_social"),  # El administrativo registra el rechazo
    ("rechazado_obra_social", "pendiente_autorizacion"),  # El paciente carga la demanda
    ("habilitado_turno", "turno_sacado"),  # El paciente reserva un turno
    ("turno_sacado", "listo_para_retirar"),  # El centro envía el mensaje de muestra tomada
    ("turno_sacado", "habilitado_turno"),  # El paciente cancela el turno
    ("listo_para_retirar", "en_camino_laboratorio"),  # El transportista retira las muestras
    ("en_camino_laboratorio", "en_laboratorio_central"),  # El transportista registra la llegada
    ("en_laboratorio_central", "pendiente_autorizacion_ministerial"),  # Se cierra el sample set
    ("en_laboratorio_central", "requiere_nueva_extraccion"),  # Volumen menor a 2 ml
    ("pendiente_autorizacion_ministerial", "pendiente_envio"),  # El Ministerio devuelve el PDF
    ("pendiente_envio", "en_viaje_corea"),  # FedEx retira el sample set
    ("en_viaje_corea", "en_area_bioinformatica"),  # El administrativo carga los datos crudos
    ("en_viaje_corea", "requiere_nueva_extraccion"),  # ADN insuficiente
    ("en_area_bioinformatica", "en_analisis"),  # El bioinformático toma el estudio
    ("en_analisis", "finalizado"),  # El bioinformático finaliza el análisis
    ("finalizado", "en_area_bioinformatica"),  # El médico tratante solicita un reanálisis
    ("requiere_nueva_extraccion", "turno_sacado"),  # El paciente reserva un nuevo turno
]

PARES_NO_PERMITIDOS = [
    (origen, destino)
    for origen in ESTADOS_DEL_LEL
    for destino in ESTADOS_DEL_LEL
    if (origen, destino) not in TRANSICIONES_DEL_LEL
]


def _ids(pares: list[tuple[str, str]]) -> list[str]:
    return [f"{origen}->{destino}" for origen, destino in pares]


def _filas_del_historial(estudio_id: int) -> list[HistorialEstado]:
    consulta = (
        sa.select(HistorialEstado)
        .where(HistorialEstado.estudio_id == estudio_id)
        .order_by(HistorialEstado.creado_en, HistorialEstado.id)
    )
    return db.session.scalars(consulta).all()


# --- La tabla de transiciones, sin base de datos ---


def test_hay_un_estado_por_cada_estado_del_lel():
    assert {estado.value: estado.nombre for estado in EstadoEstudio} == ESTADOS_DEL_LEL


def test_las_transiciones_son_las_21_del_lel():
    pares = {(o.value, d.value) for o, destinos in TRANSICIONES.items() for d in destinos}

    assert len(TRANSICIONES_DEL_LEL) == 21
    assert pares == set(TRANSICIONES_DEL_LEL)
    impactos = [impacto for destinos in TRANSICIONES.values() for impacto in destinos.values()]
    assert all(impactos), "Cada transición nombra el impacto del LEL que la provoca"


def test_todo_estado_se_alcanza_desde_creado_y_tiene_salida():
    alcanzados = {"creado"}
    pendientes = deque(["creado"])
    while pendientes:
        actual = pendientes.popleft()
        for origen, destino in TRANSICIONES_DEL_LEL:
            if origen == actual and destino not in alcanzados:
                alcanzados.add(destino)
                pendientes.append(destino)

    assert alcanzados == set(ESTADOS_DEL_LEL)
    assert {origen for origen, _ in TRANSICIONES_DEL_LEL} == set(ESTADOS_DEL_LEL)


def test_la_tabla_de_transiciones_no_se_puede_modificar():
    with pytest.raises(TypeError):
        TRANSICIONES[EstadoEstudio.CREADO][EstadoEstudio.FINALIZADO] = "Atajo"


@pytest.mark.parametrize(
    ("origen", "destino"), TRANSICIONES_DEL_LEL, ids=_ids(TRANSICIONES_DEL_LEL)
)
def test_puede_pasar_acepta_las_transiciones_del_lel(origen, destino):
    assert puede_pasar(EstadoEstudio(origen), EstadoEstudio(destino))


@pytest.mark.parametrize(("origen", "destino"), PARES_NO_PERMITIDOS, ids=_ids(PARES_NO_PERMITIDOS))
def test_puede_pasar_rechaza_lo_que_el_lel_no_permite(origen, destino):
    assert not puede_pasar(EstadoEstudio(origen), EstadoEstudio(destino))


# --- cambiar_estado() contra la base de test ---


@pytest.mark.parametrize(
    ("origen", "destino"), TRANSICIONES_DEL_LEL, ids=_ids(TRANSICIONES_DEL_LEL)
)
def test_transicion_valida_del_lel(app, crear_estudio, usuario_rapido, origen, destino):
    with app.app_context():
        estudio = crear_estudio(estado=origen)
        quien = usuario_rapido(roles.ADMINISTRATIVO)

        cambio = cambiar_estado(estudio, destino, quien, motivo="  Motivo de prueba  ")
        assert (cambio.estado_anterior, estudio.estado) == (origen, destino)
        db.session.commit()
        estudio_id, quien_id = estudio.id, quien.id

    # Otro contexto de app es otra sesión: el estado se lee de la base, no de memoria.
    with app.app_context():
        estudio = db.session.get(Estudio, estudio_id)
        ultimo = _filas_del_historial(estudio_id)[-1]

        assert estudio.estado == destino
        assert (ultimo.estado_anterior, ultimo.estado_nuevo) == (origen, destino)
        assert ultimo.usuario_id == quien_id
        assert ultimo.motivo == "Motivo de prueba"
        assert ultimo.creado_en is not None


TRANSICIONES_INVALIDAS = [
    pytest.param("creado", "habilitado_turno", id="saltea el presupuesto"),
    pytest.param("creado", "creado", id="mismo estado"),
    pytest.param("finalizado", "creado", id="vuelve a Creado"),
    pytest.param("turno_sacado", "presupuestado", id="vuelve atras"),
    pytest.param("rechazado_obra_social", "habilitado_turno", id="saltea la reautorizacion"),
    pytest.param("turno_sacado", "en_laboratorio_central", id="saltea al transportista"),
    pytest.param("en_laboratorio_central", "en_viaje_corea", id="saltea al Ministerio"),
    pytest.param("en_area_bioinformatica", "finalizado", id="finaliza sin analisis"),
]


@pytest.mark.parametrize(("origen", "destino"), TRANSICIONES_INVALIDAS)
def test_transicion_invalida_no_cambia_nada(app, crear_estudio, origen, destino):
    nombres = f"de {ESTADOS_DEL_LEL[origen]} a {ESTADOS_DEL_LEL[destino]}"
    with app.app_context():
        estudio = crear_estudio(estado=origen)
        estudio_id = estudio.id
        filas = len(_filas_del_historial(estudio_id))

        with pytest.raises(TransicionInvalida, match=re.escape(nombres)):
            cambiar_estado(estudio, destino, None)
        db.session.commit()

    with app.app_context():
        assert db.session.get(Estudio, estudio_id).estado == origen
        assert len(_filas_del_historial(estudio_id)) == filas


def test_rechaza_un_estado_que_no_existe(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()

        with pytest.raises(TransicionInvalida, match="«archivado» no es un estado"):
            cambiar_estado(estudio, "archivado", None)

        assert estudio.estado == EstadoEstudio.CREADO
        assert len(_filas_del_historial(estudio.id)) == 1


def test_decide_con_el_estado_de_la_base_y_no_con_uno_viejo(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()
        assert estudio.estado == EstadoEstudio.CREADO

        # Otro pedido, con su propia sesión, emite el presupuesto mientras este todavía tiene
        # el estudio en memoria en Creado.
        with db.sessionmaker() as otra:
            otra.execute(
                sa.update(Estudio)
                .where(Estudio.id == estudio.id)
                .values(estado=EstadoEstudio.PRESUPUESTADO)
            )
            otra.commit()

        with pytest.raises(TransicionInvalida, match="de Presupuestado a Presupuestado"):
            cambiar_estado(estudio, EstadoEstudio.PRESUPUESTADO, None)
        assert estudio.estado == EstadoEstudio.PRESUPUESTADO


def test_el_sistema_cambia_el_estado_sin_usuario(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.TURNO_SACADO)

        cambiar_estado(estudio, EstadoEstudio.LISTO_PARA_RETIRAR, None)
        db.session.commit()

        ultimo = _filas_del_historial(estudio.id)[-1]
        assert ultimo.estado_nuevo == EstadoEstudio.LISTO_PARA_RETIRAR
        assert ultimo.usuario_id is None
        assert ultimo.motivo is None


def test_el_historial_guarda_todo_el_recorrido(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.HABILITADO_TURNO)
        estudio_id = estudio.id

    with app.app_context():
        recorrido = [
            (fila.estado_anterior, fila.estado_nuevo) for fila in _filas_del_historial(estudio_id)
        ]

    assert recorrido == [
        (None, EstadoEstudio.CREADO),
        (EstadoEstudio.CREADO, EstadoEstudio.PRESUPUESTADO),
        (EstadoEstudio.PRESUPUESTADO, EstadoEstudio.HABILITADO_TURNO),
    ]


# --- Lo que controla la base ---


def test_la_base_guarda_el_codigo_del_estado(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.PENDIENTE_AUTORIZACION)
        guardado = db.session.scalar(
            sa.text("select estado from estudios where id = :id"), {"id": estudio.id}
        )

    assert guardado == "pendiente_autorizacion"


def test_la_base_rechaza_un_estado_desconocido(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()

        with pytest.raises(IntegrityError, match="estado_estudio_valido"):
            db.session.execute(
                sa.text("update estudios set estado = 'archivado' where id = :id"),
                {"id": estudio.id},
            )


def test_la_base_solo_acepta_sin_estado_anterior_la_fila_de_creado(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()
        db.session.add(
            HistorialEstado(
                estudio_id=estudio.id,
                estado_anterior=None,
                estado_nuevo=EstadoEstudio.PRESUPUESTADO,
            )
        )

        with pytest.raises(IntegrityError, match="historial_estados_primera_fila"):
            db.session.flush()
