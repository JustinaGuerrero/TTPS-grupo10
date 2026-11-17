"""E19 Reservar turno, E20 Cancelar turno y E21 Recordar turno.

Primera parte: las tablas (feriados, centros y turnos), el calendario de días hábiles, las
franjas del turnero, los centros de prueba, `flask demo turno_sacado` y las tareas programadas.
Segunda parte: reservar, cancelar, recordar y las pantallas del paciente.
"""

from datetime import date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.calendario import (
    ZONA_HORARIA,
    dias_habiles,
    es_dia_habil,
    es_feriado,
    proximo_dia_habil,
)
from src.core.centros import CentroExtraccion, buscar_por_chat, listar_centros_activos
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.finanzas import Pago
from src.core.notificaciones import Aviso
from src.core.pacientes import Paciente
from src.core.turnos import (
    ErrorDeTurno,
    EstadoTurno,
    TurnoExtraccion,
    cancelar,
    dias_con_turnos,
    enviar_recordatorios,
    franjas_libres,
    reservar,
    turno_vigente,
)
from src.core.turnos import servicios as servicios_de_turnos
from src.core.turnos.franjas import es_franja_valida, franjas_del_dia
from src.core.turnos.servicios import DIAS_DEL_TURNERO
from src.core.usuarios import buscar_por_email, roles
from src.integraciones.mail import mail
from src.web import tareas


def _hora(texto: str) -> datetime:
    """'2026-11-24 09:15' en hora de Argentina."""
    return datetime.fromisoformat(texto).replace(tzinfo=ZONA_HORARIA)


# --- Calendario: días hábiles y feriados ---


def test_la_migracion_carga_los_feriados_nacionales_de_2026(app):
    with app.app_context():
        assert es_feriado(date(2026, 11, 23))  # Día de la Soberanía Nacional, trasladado
        assert es_feriado(date(2026, 12, 25))
        # Los días no laborables con fines turísticos no son feriados: hay turnos.
        assert not es_feriado(date(2026, 12, 7))


@pytest.mark.parametrize(
    ("fecha", "habil"),
    [
        pytest.param(date(2026, 11, 24), True, id="martes"),
        pytest.param(date(2026, 11, 21), False, id="sabado"),
        pytest.param(date(2026, 11, 22), False, id="domingo"),
        pytest.param(date(2026, 11, 23), False, id="feriado"),
    ],
)
def test_es_dia_habil(app, fecha, habil):
    with app.app_context():
        assert es_dia_habil(fecha) is habil


def test_proximo_dia_habil_saltea_el_fin_de_semana_y_los_feriados(app):
    with app.app_context():
        # Viernes 20/11 → lunes 23/11 es feriado → martes 24/11.
        assert proximo_dia_habil(date(2026, 11, 20)) == date(2026, 11, 24)
        assert proximo_dia_habil(date(2026, 11, 24)) == date(2026, 11, 25)


def test_dias_habiles_incluye_el_primero_si_es_habil(app):
    with app.app_context():
        assert dias_habiles(date(2026, 12, 4), 4) == [
            date(2026, 12, 4),
            date(2026, 12, 7),
            date(2026, 12, 9),  # el 8/12 es feriado
            date(2026, 12, 10),
        ]


# --- Franjas del turnero: 15 minutos, de 9 a 18 ---


def test_un_dia_tiene_36_franjas_de_9_a_17_45():
    franjas = franjas_del_dia(date(2026, 11, 24))

    assert len(franjas) == 36
    assert franjas[0] == _hora("2026-11-24 09:00")
    assert franjas[-1] == _hora("2026-11-24 17:45")


@pytest.mark.parametrize(
    ("inicio", "valida"),
    [
        pytest.param("2026-11-24 09:00", True, id="apertura"),
        pytest.param("2026-11-24 17:45", True, id="ultima"),
        pytest.param("2026-11-24 18:00", False, id="cierre"),
        pytest.param("2026-11-24 08:45", False, id="antes de abrir"),
        pytest.param("2026-11-24 09:10", False, id="no es multiplo de 15"),
        pytest.param("2026-11-21 10:00", False, id="sabado"),
        pytest.param("2026-11-23 10:00", False, id="feriado"),
    ],
)
def test_es_franja_valida(app, inicio, valida):
    with app.app_context():
        assert es_franja_valida(_hora(inicio)) is valida


def test_una_franja_en_utc_se_compara_en_hora_de_argentina(app):
    with app.app_context():
        # 12:00 UTC son las 9:00 en Argentina.
        assert es_franja_valida(datetime.fromisoformat("2026-11-24 12:00+00:00"))


# --- Reglas de la base: un paciente por franja y un turno vigente por estudio ---


def test_dos_reservas_de_la_misma_franja_chocan_en_la_base(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        centro = crear_centro()
        inicio = _hora("2026-11-24 10:00")
        crear_turno(crear_estudio(EstadoEstudio.HABILITADO_TURNO), centro, inicio)

        db.session.add(
            TurnoExtraccion(
                estudio_id=crear_estudio(EstadoEstudio.HABILITADO_TURNO).id,
                centro_id=centro.id,
                inicio=inicio,
            )
        )
        with pytest.raises(IntegrityError, match="turnos_extraccion_franja_ocupada"):
            db.session.flush()
        db.session.rollback()


def test_un_turno_cancelado_libera_la_franja(app, crear_estudio, crear_centro, crear_turno):
    with app.app_context():
        centro = crear_centro()
        inicio = _hora("2026-11-24 10:00")
        crear_turno(
            crear_estudio(EstadoEstudio.HABILITADO_TURNO),
            centro,
            inicio,
            estado=EstadoTurno.CANCELADO,
        )

        otro = crear_turno(crear_estudio(EstadoEstudio.HABILITADO_TURNO), centro, inicio)

        assert otro.id is not None


def test_un_estudio_tiene_un_solo_turno_vigente(app, crear_estudio, crear_turno):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        crear_turno(estudio)

        with pytest.raises(IntegrityError, match="turnos_extraccion_vigente_por_estudio"):
            crear_turno(estudio, inicio=_hora("2026-11-25 10:00"))
        db.session.rollback()


def test_la_base_rechaza_una_franja_que_no_empieza_en_punto(app, crear_estudio, crear_turno):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(IntegrityError, match="turnos_extraccion_franja"):
            crear_turno(estudio, inicio=_hora("2026-11-24 10:10"))
        db.session.rollback()


# --- Centros de extracción ---


def test_los_seeds_cargan_10_centros_en_3_provincias_sin_duplicar(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0
    assert runner.invoke(args=["seeds"]).exit_code == 0

    with app.app_context():
        centros = listar_centros_activos()
        assert len(centros) == 10
        assert len({centro.provincia.nombre for centro in centros}) == 3
        assert buscar_por_chat("1000001").nombre == "Centro La Plata"


def test_los_centros_inactivos_no_se_listan(app, crear_centro):
    with app.app_context():
        activo = crear_centro()
        crear_centro(activo=False)

        assert listar_centros_activos() == [activo]


def test_buscar_por_chat_de_un_chat_desconocido_devuelve_none(app):
    with app.app_context():
        assert buscar_por_chat("999") is None


# --- flask demo turno_sacado ---


def test_demo_turno_sacado_reserva_un_turno_el_proximo_dia_habil(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    resultado = runner.invoke(args=["demo", "turno_sacado"])

    assert resultado.exit_code == 0, resultado.output
    assert "en Turno sacado." in resultado.output
    with app.app_context():
        usuario = buscar_por_email("demo.1@exoma.test")
        estudio = db.session.scalars(
            sa.select(Estudio).join(Estudio.paciente).where(Paciente.usuario_id == usuario.id)
        ).one()
        turno = db.session.scalars(
            sa.select(TurnoExtraccion).where(TurnoExtraccion.estudio_id == estudio.id)
        ).one()
        assert estudio.estado == EstadoEstudio.TURNO_SACADO
        assert turno.estado == EstadoTurno.RESERVADO
        assert es_franja_valida(turno.inicio)
        assert turno.inicio > datetime.now(ZONA_HORARIA)


def test_dos_demos_turno_sacado_no_chocan_en_la_misma_franja(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    assert runner.invoke(args=["demo", "turno_sacado"]).exit_code == 0
    assert runner.invoke(args=["demo", "turno_sacado"]).exit_code == 0

    with app.app_context():
        inicios = db.session.scalars(sa.select(TurnoExtraccion.inicio)).all()
        assert len(set(inicios)) == 2


def test_demo_turno_sacado_sin_centros_pide_los_seeds(app, monkeypatch):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0
    with app.app_context():
        db.session.execute(sa.update(CentroExtraccion).values(activo=False))
        db.session.commit()

    resultado = runner.invoke(args=["demo", "turno_sacado"])

    assert resultado.exit_code != 0
    assert "No hay centros de extracción" in resultado.output


# --- Tareas programadas ---


def test_las_tareas_no_arrancan_en_los_tests(app):
    assert not tareas.debe_arrancar(app)


def test_ejecutar_confirma_lo_que_hizo_la_tarea(app, monkeypatch, crear_centro):
    def crear_uno():
        crear_centro(provincia="Córdoba")
        return "listo"

    resultado = tareas.ejecutar(app, tareas.Tarea("prueba", crear_uno, {}))

    assert resultado == "listo"
    with app.app_context():
        assert len(listar_centros_activos()) == 1


def test_ejecutar_deshace_lo_que_hizo_una_tarea_que_falla(app, crear_centro):
    def falla():
        crear_centro()
        raise RuntimeError("se cayó")

    with pytest.raises(RuntimeError):
        tareas.ejecutar(app, tareas.Tarea("prueba", falla, {}))

    with app.app_context():
        assert listar_centros_activos() == []


def test_flask_tarea_corre_una_tarea_registrada(app, monkeypatch):
    monkeypatch.setattr(tareas, "TAREAS", [tareas.Tarea("saludar", lambda: "hola", {})])

    resultado = app.test_cli_runner().invoke(args=["tarea", "saludar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Tarea saludar: hola" in resultado.output


def test_flask_tarea_de_una_tarea_que_no_existe_lista_las_que_hay(app, monkeypatch):
    monkeypatch.setattr(tareas, "TAREAS", [tareas.Tarea("saludar", lambda: "hola", {})])

    resultado = app.test_cli_runner().invoke(args=["tarea", "volar"])

    assert resultado.exit_code != 0
    assert "Tareas: saludar" in resultado.output


# =============================================================================================
# Segunda parte: reservar (E19), cancelar (E20), recordar (E21) y las pantallas del paciente.
# =============================================================================================

# Martes 24/11/2026 a las 8:00: el lunes 23 es feriado; el próximo día hábil es el miércoles 25.
AHORA = _hora("2026-11-24 08:00")


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


def _estado_guardado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _avisos_de(usuario):
    return db.session.scalars(sa.select(Aviso).where(Aviso.usuario_id == usuario.id)).all()


# --- E19.3 Franjas libres ---


def test_franjas_libres_saca_las_ocupadas_y_las_que_ya_pasaron(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        centro = crear_centro()
        crear_turno(
            crear_estudio(EstadoEstudio.HABILITADO_TURNO), centro, _hora("2026-11-24 10:00")
        )
        ahora = _hora("2026-11-24 09:20")

        libres = franjas_libres(centro, date(2026, 11, 24), ahora)

        assert _hora("2026-11-24 09:15") not in libres  # ya pasó
        assert _hora("2026-11-24 10:00") not in libres  # ocupada
        assert libres[0] == _hora("2026-11-24 09:30")
        assert libres[-1] == _hora("2026-11-24 17:45")
        assert _hora("2026-11-24 18:00") not in libres


def test_un_turno_ocupado_en_otro_centro_no_saca_la_franja(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        centro, otro = crear_centro(), crear_centro()
        crear_turno(crear_estudio(EstadoEstudio.HABILITADO_TURNO), otro, _hora("2026-11-25 10:00"))

        assert _hora("2026-11-25 10:00") in franjas_libres(centro, date(2026, 11, 25), AHORA)


@pytest.mark.parametrize(
    "fecha",
    [pytest.param(date(2026, 11, 28), id="sabado"), pytest.param(date(2026, 11, 23), id="feriado")],
)
def test_sabados_y_feriados_no_tienen_franjas(app, crear_centro, fecha):
    with app.app_context():
        assert franjas_libres(crear_centro(), fecha, _hora("2026-11-20 08:00")) == []


def test_el_turnero_muestra_hoy_solo_si_quedan_franjas(app):
    with app.app_context():
        assert dias_con_turnos(_hora("2026-11-25 17:30"))[0] == date(2026, 11, 25)
        assert dias_con_turnos(_hora("2026-11-25 17:50"))[0] == date(2026, 11, 26)
        assert len(dias_con_turnos(AHORA)) == DIAS_DEL_TURNERO


# --- E19 Reservar turno ---


def test_reservar_pasa_el_estudio_a_turno_sacado_y_avisa_con_la_orden(
    app, crear_estudio, crear_centro
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        centro = crear_centro()
        inicio = _hora("2026-11-25 10:15")

        with mail.record_messages() as enviados:
            turno = reservar(estudio, paciente, centro, inicio, AHORA)
        db.session.commit()

        assert turno.estado == EstadoTurno.RESERVADO
        assert turno.inicio == inicio
        assert _estado_guardado(estudio.id) == EstadoEstudio.TURNO_SACADO
        ultimo = db.session.scalars(
            sa.select(HistorialEstado)
            .where(HistorialEstado.estudio_id == estudio.id)
            .order_by(HistorialEstado.id.desc())
        ).first()
        assert ultimo.estado_nuevo == EstadoEstudio.TURNO_SACADO
        assert ultimo.usuario_id == paciente.id
        # E19.6: el aviso y el mail llevan a "Mi turno", donde están la orden y el consentimiento.
        (aviso,) = _avisos_de(paciente)
        assert aviso.link == "/turnos/mio"
        assert "miércoles 25/11/2026 a las 10:15" in aviso.mensaje
        assert centro.nombre in aviso.mensaje
        assert "orden de extracción" in enviados[0].body


def test_desde_requiere_nueva_extraccion_se_reserva_sin_pagar_de_nuevo(
    app, crear_estudio, crear_centro
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.REQUIERE_NUEVA_EXTRACCION)
        pagos_antes = db.session.scalar(sa.select(sa.func.count()).select_from(Pago))

        reservar(
            estudio, estudio.paciente.usuario, crear_centro(), _hora("2026-11-25 10:00"), AHORA
        )
        db.session.commit()

        assert _estado_guardado(estudio.id) == EstadoEstudio.TURNO_SACADO
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Pago)) == pagos_antes


@pytest.mark.parametrize(
    "estado",
    [EstadoEstudio.CREADO, EstadoEstudio.PRESUPUESTADO, EstadoEstudio.PENDIENTE_AUTORIZACION],
)
def test_un_estudio_que_no_esta_habilitado_no_reserva(app, crear_estudio, crear_centro, estado):
    with app.app_context():
        estudio = crear_estudio(estado)

        with pytest.raises(ErrorDeTurno, match="Habilitado para turno"):
            reservar(
                estudio, estudio.paciente.usuario, crear_centro(), _hora("2026-11-25 10:00"), AHORA
            )


@pytest.mark.parametrize(
    ("inicio", "mensaje"),
    [
        pytest.param("2026-11-28 10:00", "lunes a viernes", id="sabado"),
        pytest.param("2026-11-23 10:00", "sin feriados", id="feriado"),
        pytest.param("2026-11-25 18:00", "de 9 a 18", id="a las 18"),
        pytest.param("2026-11-25 10:10", "15 minutos", id="no es una franja"),
        pytest.param("2026-11-24 07:45", "lunes a viernes", id="antes de abrir"),
    ],
)
def test_reservar_una_franja_invalida_falla(app, crear_estudio, crear_centro, inicio, mensaje):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(ErrorDeTurno, match=mensaje):
            reservar(estudio, estudio.paciente.usuario, crear_centro(), _hora(inicio), AHORA)


def test_reservar_una_franja_que_ya_paso_falla(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(ErrorDeTurno, match="ya pasó"):
            reservar(
                estudio,
                estudio.paciente.usuario,
                crear_centro(),
                _hora("2026-11-24 09:00"),
                _hora("2026-11-24 09:05"),
            )


def test_dos_pacientes_no_reservan_la_misma_franja(app, crear_estudio, crear_centro):
    with app.app_context():
        centro = crear_centro()
        inicio = _hora("2026-11-25 11:00")
        primero = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        reservar(primero, primero.paciente.usuario, centro, inicio, AHORA)
        db.session.commit()
        segundo = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(ErrorDeTurno, match="ya se reservó"):
            reservar(segundo, segundo.paciente.usuario, centro, inicio, AHORA)
        db.session.rollback()
        assert _estado_guardado(segundo.id) == EstadoEstudio.HABILITADO_TURNO


def test_si_dos_reservan_a_la_vez_el_indice_frena_al_segundo(
    app, crear_estudio, crear_centro, monkeypatch
):
    """Los dos pasan la consulta de franja ocupada; el índice único de la base frena al segundo."""
    with app.app_context():
        centro = crear_centro()
        inicio = _hora("2026-11-25 11:00")
        primero = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        reservar(primero, primero.paciente.usuario, centro, inicio, AHORA)
        segundo = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        monkeypatch.setattr(servicios_de_turnos, "_franja_ocupada", lambda centro, inicio: False)

        with pytest.raises(ErrorDeTurno, match="ya se reservó"):
            reservar(segundo, segundo.paciente.usuario, centro, inicio, AHORA)
        db.session.rollback()


def test_no_se_reserva_en_un_centro_inactivo(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(ErrorDeTurno, match="no está atendiendo"):
            reservar(
                estudio,
                estudio.paciente.usuario,
                crear_centro(activo=False),
                _hora("2026-11-25 10:00"),
                AHORA,
            )


def test_un_paciente_no_reserva_el_turno_de_otro_estudio(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        otro = crear_estudio(EstadoEstudio.HABILITADO_TURNO)

        with pytest.raises(ErrorDeTurno, match="Solo el paciente"):
            reservar(
                estudio, otro.paciente.usuario, crear_centro(), _hora("2026-11-25 10:00"), AHORA
            )


def test_un_estudio_con_turno_no_reserva_otro(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        reservar(estudio, paciente, crear_centro(), _hora("2026-11-25 10:00"), AHORA)

        with pytest.raises(ErrorDeTurno):
            reservar(estudio, paciente, crear_centro(), _hora("2026-11-26 10:00"), AHORA)


# --- E20 Cancelar turno ---


def test_cancelar_libera_la_franja_y_vuelve_a_habilitado_para_turno(
    app, crear_estudio, crear_centro
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        centro = crear_centro()
        inicio = _hora("2026-11-25 10:00")
        turno = reservar(estudio, paciente, centro, inicio, AHORA)
        db.session.commit()

        cancelar(turno, paciente, AHORA)
        db.session.commit()

        assert turno.estado == EstadoTurno.CANCELADO
        assert turno.cancelado_en == AHORA
        assert _estado_guardado(estudio.id) == EstadoEstudio.HABILITADO_TURNO
        assert inicio in franjas_libres(centro, date(2026, 11, 25), AHORA)
        assert turno_vigente(estudio) is None


def test_despues_de_cancelar_se_reserva_otro_turno(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        centro = crear_centro()
        cancelar(
            reservar(estudio, paciente, centro, _hora("2026-11-25 10:00"), AHORA), paciente, AHORA
        )

        otro = reservar(estudio, paciente, centro, _hora("2026-11-26 10:00"), AHORA)

        assert turno_vigente(estudio) == otro


def test_no_se_cancela_un_turno_que_ya_empezo(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        turno = reservar(estudio, paciente, crear_centro(), _hora("2026-11-25 10:00"), AHORA)

        with pytest.raises(ErrorDeTurno, match="ya empezó"):
            cancelar(turno, paciente, _hora("2026-11-25 10:00"))


def test_no_se_cancela_un_turno_ya_cancelado(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        paciente = estudio.paciente.usuario
        turno = reservar(estudio, paciente, crear_centro(), _hora("2026-11-25 10:00"), AHORA)
        cancelar(turno, paciente, AHORA)

        with pytest.raises(ErrorDeTurno, match="no está reservado"):
            cancelar(turno, paciente, AHORA)


def test_un_paciente_no_cancela_el_turno_de_otro(app, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        turno = reservar(
            estudio, estudio.paciente.usuario, crear_centro(), _hora("2026-11-25 10:00"), AHORA
        )
        otro = crear_estudio(EstadoEstudio.HABILITADO_TURNO).paciente.usuario

        with pytest.raises(ErrorDeTurno, match="Solo el paciente"):
            cancelar(turno, otro, AHORA)


# --- E21 Recordar turno ---


def test_el_recordatorio_sale_para_los_turnos_del_proximo_dia_habil_y_una_sola_vez(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        centro = crear_centro()
        manana = crear_estudio(EstadoEstudio.TURNO_SACADO)
        crear_turno(manana, centro, _hora("2026-11-25 09:30"))
        pasado = crear_estudio(EstadoEstudio.TURNO_SACADO)
        crear_turno(pasado, centro, _hora("2026-11-26 09:30"))
        cancelado = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        crear_turno(cancelado, centro, _hora("2026-11-25 10:00"), estado=EstadoTurno.CANCELADO)

        with mail.record_messages() as enviados:
            assert enviar_recordatorios(AHORA) == 1
            assert enviar_recordatorios(AHORA) == 0  # una sola vez
        db.session.commit()

        (aviso,) = _avisos_de(manana.paciente.usuario)
        assert aviso.link == "/turnos/mio"
        # E21.2: el mail lleva la fecha, la hora y el centro.
        assert "miércoles 25/11/2026 a las 09:30" in enviados[0].body
        assert centro.nombre in enviados[0].body
        assert _avisos_de(pasado.paciente.usuario) == []
        assert _avisos_de(cancelado.paciente.usuario) == []


def test_el_viernes_se_recuerdan_los_turnos_del_proximo_dia_habil(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.TURNO_SACADO)
        # Viernes 20/11: el lunes 23 es feriado, así que avisa los del martes 24.
        crear_turno(estudio, crear_centro(), _hora("2026-11-24 09:00"))

        assert enviar_recordatorios(_hora("2026-11-20 10:00")) == 1


def test_los_fines_de_semana_no_se_mandan_recordatorios(
    app, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        crear_turno(
            crear_estudio(EstadoEstudio.TURNO_SACADO), crear_centro(), _hora("2026-11-30 09:00")
        )

        assert enviar_recordatorios(_hora("2026-11-28 10:00")) == 0


def test_la_tarea_de_recordatorios_esta_programada_los_dias_habiles():
    tarea = tareas.buscar_tarea("recordatorios_de_turno")

    assert tarea.funcion is enviar_recordatorios
    assert tarea.cuando["day_of_week"] == "mon-fri"


# --- Pantallas del paciente ---


def _franja_libre(centro):
    dia = dias_con_turnos()[0]
    return franjas_libres(centro, dia)[0]


def test_el_paciente_reserva_desde_el_mapa_y_ve_su_turno(app, client, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        db.session.commit()
        estudio_id, centro_id, nombre = estudio.id, centro.id, centro.nombre
        inicio = _franja_libre(centro)
        _entrar_como(client, estudio.paciente.usuario)

    assert "Sacar turno" in client.get("/turnos/mio").text
    mapa = client.get("/turnos/centros")
    assert mapa.status_code == 200
    assert nombre in mapa.text
    assert "vendor/leaflet/leaflet.js" in mapa.text
    franjas = client.get(f"/turnos/centros/{centro_id}/franjas")
    assert inicio.isoformat() in franjas.text

    respuesta = client.post("/turnos", data={"centro_id": centro_id, "inicio": inicio.isoformat()})

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/turnos/mio")
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.TURNO_SACADO
    mio = client.get("/turnos/mio")
    assert nombre in mio.text
    assert "Orden de extracción (PDF)" in mio.text
    assert "Cancelar el turno" in mio.text


def test_reservar_una_franja_ocupada_desde_la_pantalla_avisa_el_error(
    app, client, crear_estudio, crear_centro, crear_turno
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        inicio = _franja_libre(centro)
        crear_turno(crear_estudio(EstadoEstudio.TURNO_SACADO), centro, inicio)
        db.session.commit()
        estudio_id, centro_id = estudio.id, centro.id
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.post(
        "/turnos",
        data={"centro_id": centro_id, "inicio": inicio.isoformat()},
        follow_redirects=True,
    )

    assert "Ese turno ya se reservó" in respuesta.text
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.HABILITADO_TURNO


def test_un_paciente_presupuestado_no_entra_al_mapa(app, client, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.PRESUPUESTADO)
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.get("/turnos/centros", follow_redirects=True)

    assert "Presupuestado" in respuesta.text
    assert "vendor/leaflet/leaflet.js" not in respuesta.text


def test_el_paciente_cancela_su_turno_desde_la_pantalla(app, client, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        turno = reservar(estudio, estudio.paciente.usuario, centro, _franja_libre(centro))
        db.session.commit()
        estudio_id, turno_id = estudio.id, turno.id
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.post(f"/turnos/{turno_id}/cancelar")

    assert respuesta.status_code == 302
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.HABILITADO_TURNO


def test_la_orden_y_el_consentimiento_son_pdf_con_el_codigo_del_estudio(
    app, client, crear_estudio, crear_centro
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        turno = reservar(estudio, estudio.paciente.usuario, centro, _franja_libre(centro))
        db.session.commit()
        turno_id, codigo = turno.id, estudio.codigo
        _entrar_como(client, estudio.paciente.usuario)

    orden = client.get(f"/turnos/{turno_id}/orden.pdf")
    consentimiento = client.get("/turnos/consentimiento.pdf")

    assert orden.status_code == 200
    assert orden.mimetype == "application/pdf"
    assert orden.data.startswith(b"%PDF")
    assert codigo in orden.headers["Content-Disposition"]
    assert consentimiento.status_code == 200
    assert consentimiento.data.startswith(b"%PDF")


def test_el_turno_de_otro_paciente_responde_404(app, client, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        turno = reservar(estudio, estudio.paciente.usuario, centro, _franja_libre(centro))
        otro = crear_estudio(EstadoEstudio.HABILITADO_TURNO)
        db.session.commit()
        turno_id = turno.id
        _entrar_como(client, otro.paciente.usuario)

    assert client.get(f"/turnos/{turno_id}/orden.pdf").status_code == 404
    assert client.post(f"/turnos/{turno_id}/cancelar").status_code == 404


@pytest.mark.parametrize("rol", [roles.MEDICO_TRATANTE, roles.ADMINISTRATIVO, roles.TRANSPORTISTA])
def test_solo_el_paciente_entra_a_los_turnos(login_como, rol):
    cliente = login_como(rol)

    assert cliente.get("/turnos/centros").status_code == 403
    assert cliente.get("/turnos/mio").status_code == 403


def test_sin_sesion_los_turnos_piden_iniciar_sesion(client):
    respuesta = client.get("/turnos/mio")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


def test_el_menu_del_paciente_tiene_mi_turno(login_como):
    cliente = login_como(roles.PACIENTE)

    assert "Mi turno" in cliente.get("/").text
