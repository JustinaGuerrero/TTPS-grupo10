"""E22 Registrar toma de muestra y supuesto O7 (inasistencia al turno).

El centro de extracción avisa por el bot de mensajería (webhook de Telegram) que tomó la muestra:
el estudio pasa solo a Listo para retirar. Si al cierre del día no llegó el mensaje, el turno
queda ausente y el estudio vuelve a Habilitado para turno.
"""

import itertools
from datetime import datetime

import pytest
import sqlalchemy as sa

from src.core.calendario import ZONA_HORARIA
from src.core.database import db
from src.core.estudios import EstadoEstudio, HistorialEstado
from src.core.muestras import (
    MensajeBot,
    Muestra,
    centros_con_muestras_listas,
    codigo_del_estudio,
    procesar_inasistencias,
)
from src.core.notificaciones import Aviso
from src.core.provincias import Provincia
from src.core.sample_sets import EstadoSampleSet, SampleSet
from src.core.turnos import EstadoTurno
from src.core.usuarios import roles
from src.web import tareas
from src.web.controllers.bot import HEADER_DEL_SECRETO

SECRETO = "secreto-del-bot-de-tests"
_ids = itertools.count(1)


def _hora(texto: str) -> datetime:
    """'2026-11-24 09:15' en hora de Argentina."""
    return datetime.fromisoformat(texto).replace(tzinfo=ZONA_HORARIA)


def _update(chat_id: str, texto: str, update_id: int | None = None) -> dict:
    update_id = update_id or next(_ids)
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 1795000000,
            "chat": {"id": chat_id, "type": "private"},
            "text": texto,
        },
    }


def _enviar(client, update: dict, secreto: str | None = SECRETO):
    headers = {HEADER_DEL_SECRETO: secreto} if secreto is not None else {}
    return client.post("/bot/telegram", json=update, headers=headers)


@pytest.fixture
def turno_sacado(app, crear_estudio, crear_turno):
    """Un estudio en Turno sacado con su turno reservado en un centro de Buenos Aires."""
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.TURNO_SACADO)
        turno = crear_turno(estudio)
        db.session.commit()
        return {
            "estudio_id": estudio.id,
            "codigo": estudio.codigo,
            "turno_id": turno.id,
            "centro_id": turno.centro_id,
            "chat_id": turno.centro.telegram_chat_id,
        }


def _sin_cambios(datos: dict) -> None:
    """El estudio sigue en Turno sacado, el turno reservado y no hay muestra."""
    from src.core.estudios import Estudio
    from src.core.turnos import TurnoExtraccion

    db.session.expire_all()
    assert db.session.get(Estudio, datos["estudio_id"]).estado == EstadoEstudio.TURNO_SACADO
    assert db.session.get(TurnoExtraccion, datos["turno_id"]).estado == EstadoTurno.RESERVADO
    assert db.session.scalar(sa.select(sa.func.count()).select_from(Muestra)) == 0


def _unico_mensaje() -> MensajeBot:
    return db.session.scalars(sa.select(MensajeBot)).one()


# --- Migración ---


def test_muestras_no_tiene_columnas_de_volumen(app):
    with app.app_context():
        columnas = {columna["name"] for columna in sa.inspect(db.engine).get_columns("muestras")}
        assert "turno_id" in columnas
        assert not columnas & {"volumen_ml", "volumen_registrado_por", "volumen_registrado_en"}


def test_hay_un_solo_sample_set_en_armado(app):
    with app.app_context():
        db.session.add(SampleSet())
        db.session.flush()
        with pytest.raises(sa.exc.IntegrityError), db.session.begin_nested():
            db.session.add(SampleSet(estado=EstadoSampleSet.EN_ARMADO))


def test_codigo_del_estudio_se_normaliza():
    assert codigo_del_estudio("Muestra tomada ex-2026-00042 ok") == "EX-2026-00042"
    assert codigo_del_estudio("Muestra tomada") is None


# --- E22.4 y E22.5: mensaje válido ---


def test_mensaje_valido_registra_la_muestra_y_pasa_a_listo_para_retirar(app, client, turno_sacado):
    texto = f"Muestra tomada {turno_sacado['codigo']}"

    respuesta = _enviar(client, _update(turno_sacado["chat_id"], texto))

    assert respuesta.status_code == 200
    assert respuesta.json["method"] == "sendMessage"
    assert respuesta.json["chat_id"] == turno_sacado["chat_id"]
    assert "Listo para retirar" in respuesta.json["text"]
    with app.app_context():
        mensaje = _unico_mensaje()
        assert mensaje.error is None
        assert mensaje.procesado_en is not None
        assert mensaje.centro_id == turno_sacado["centro_id"]
        assert mensaje.estudio_id == turno_sacado["estudio_id"]

        muestra = db.session.scalars(sa.select(Muestra)).one()
        assert muestra.turno_id == turno_sacado["turno_id"]
        assert muestra.estudio_id == turno_sacado["estudio_id"]
        assert muestra.tomada_en is not None
        assert muestra.turno.estado == EstadoTurno.ASISTIDO
        assert muestra.estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR

        ultimo = db.session.scalars(
            sa.select(HistorialEstado)
            .where(HistorialEstado.estudio_id == turno_sacado["estudio_id"])
            .order_by(HistorialEstado.id.desc())
        ).first()
        assert ultimo.estado_nuevo == EstadoEstudio.LISTO_PARA_RETIRAR
        assert ultimo.usuario_id is None


def test_mensaje_repetido_no_hace_nada(app, client, turno_sacado):
    update = _update(turno_sacado["chat_id"], f"Muestra tomada {turno_sacado['codigo']}")
    assert _enviar(client, update).status_code == 200

    respuesta = _enviar(client, update)

    assert respuesta.status_code == 200
    assert respuesta.data == b""
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(MensajeBot)) == 1
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Muestra)) == 1


# --- Mensajes que no se pueden procesar: error guardado y sin cambios ---


def test_chat_desconocido_guarda_el_error_y_no_responde(app, client, turno_sacado):
    respuesta = _enviar(client, _update("999999", f"Muestra tomada {turno_sacado['codigo']}"))

    assert respuesta.status_code == 200
    assert respuesta.data == b""
    with app.app_context():
        mensaje = _unico_mensaje()
        assert "no es de un centro" in mensaje.error
        assert mensaje.centro_id is None
        _sin_cambios(turno_sacado)


@pytest.mark.parametrize(
    ("texto", "error"),
    [
        pytest.param("Muestra tomada EX-2026-99999", "No existe el estudio", id="inexistente"),
        pytest.param("Muestra tomada", "no trae el código", id="sin codigo"),
    ],
)
def test_codigo_desconocido_guarda_el_error(app, client, turno_sacado, texto, error):
    respuesta = _enviar(client, _update(turno_sacado["chat_id"], texto))

    assert respuesta.status_code == 200
    assert "No se registró la muestra" in respuesta.json["text"]
    with app.app_context():
        assert error in _unico_mensaje().error
        _sin_cambios(turno_sacado)


def test_update_sin_texto_se_guarda_con_error(app, client, turno_sacado):
    update = {"update_id": 4242, "message": {"chat": {"id": turno_sacado["chat_id"]}}}

    assert _enviar(client, update).status_code == 200

    with app.app_context():
        mensaje = _unico_mensaje()
        assert mensaje.texto is None
        assert "no trae texto" in mensaje.error


def test_estudio_en_otro_estado_guarda_el_error(app, client, crear_estudio, crear_centro):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.HABILITADO_TURNO)
        centro = crear_centro()
        db.session.commit()
        codigo, chat_id, estudio_id = estudio.codigo, centro.telegram_chat_id, estudio.id

    respuesta = _enviar(client, _update(chat_id, f"Muestra tomada {codigo}"))

    assert respuesta.status_code == 200
    with app.app_context():
        mensaje = _unico_mensaje()
        assert "Habilitado para turno" in mensaje.error
        assert mensaje.estudio_id == estudio_id
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Muestra)) == 0


def test_turno_de_otro_centro_guarda_el_error(app, client, turno_sacado, crear_centro):
    with app.app_context():
        otro = crear_centro()
        db.session.commit()
        chat_de_otro = otro.telegram_chat_id

    respuesta = _enviar(client, _update(chat_de_otro, f"Muestra tomada {turno_sacado['codigo']}"))

    assert respuesta.status_code == 200
    with app.app_context():
        assert "otro centro" in _unico_mensaje().error
        _sin_cambios(turno_sacado)


# --- Webhook sin sesión: secreto ---


@pytest.mark.parametrize("secreto", [None, "otro-secreto"], ids=["sin header", "incorrecto"])
def test_sin_el_secreto_responde_403_y_no_guarda(app, client, turno_sacado, secreto):
    update = _update(turno_sacado["chat_id"], f"Muestra tomada {turno_sacado['codigo']}")

    respuesta = _enviar(client, update, secreto=secreto)

    assert respuesta.status_code == 403
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(MensajeBot)) == 0
        _sin_cambios(turno_sacado)


def test_sin_secreto_configurado_nadie_pasa(app, client, turno_sacado):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = None

    respuesta = _enviar(client, _update(turno_sacado["chat_id"], "x"), secreto="")

    assert respuesta.status_code == 403


def test_el_webhook_no_pide_token_csrf(app, client, turno_sacado):
    app.config["WTF_CSRF_ENABLED"] = True

    respuesta = _enviar(client, _update(turno_sacado["chat_id"], turno_sacado["codigo"]))

    assert respuesta.status_code == 200


def test_cuerpo_que_no_es_un_update_responde_200(app, client):
    respuesta = client.post(
        "/bot/telegram", json={"hola": 1}, headers={HEADER_DEL_SECRETO: SECRETO}
    )

    assert respuesta.status_code == 200
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(MensajeBot)) == 0


def test_un_error_inesperado_responde_200_y_guarda_el_mensaje(
    app, client, turno_sacado, monkeypatch
):
    from src.web.controllers import bot

    def falla(update):
        raise RuntimeError("se cayó")

    monkeypatch.setattr(bot, "registrar_toma", falla)

    respuesta = _enviar(client, _update(turno_sacado["chat_id"], turno_sacado["codigo"]))

    assert respuesta.status_code == 200
    with app.app_context():
        assert "Error interno" in _unico_mensaje().error


# --- E22.6: el centro entra en la próxima orden del día de su provincia ---


def test_centros_con_muestras_listas_devuelve_el_centro_de_la_muestra(
    app, client, turno_sacado, crear_centro
):
    _enviar(client, _update(turno_sacado["chat_id"], f"Muestra tomada {turno_sacado['codigo']}"))

    with app.app_context():
        crear_centro()  # otro centro de Buenos Aires, sin muestras
        buenos_aires = db.session.scalars(
            sa.select(Provincia).where(Provincia.nombre == "Buenos Aires")
        ).one()
        cordoba = db.session.scalars(
            sa.select(Provincia).where(Provincia.nombre == "Córdoba")
        ).one()

        centros = centros_con_muestras_listas(buenos_aires)

        assert [centro.id for centro in centros] == [turno_sacado["centro_id"]]
        assert centros_con_muestras_listas(buenos_aires.id) == centros
        assert centros_con_muestras_listas(cordoba) == []


def test_centros_con_muestras_listas_no_cuenta_las_retiradas(app, crear_estudio, crear_muestra):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.EN_CAMINO_LABORATORIO)
        muestra = crear_muestra(estudio)
        provincia_id = muestra.turno.centro.provincia_id

        assert centros_con_muestras_listas(provincia_id) == []


# --- O7: inasistencia al turno ---


def test_inasistencia_libera_el_turno_y_avisa_al_paciente(app, crear_estudio, crear_turno):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.TURNO_SACADO)
        turno = crear_turno(estudio, inicio=_hora("2026-11-24 10:00"))
        manana = crear_estudio(estado=EstadoEstudio.TURNO_SACADO)
        turno_de_manana = crear_turno(manana, inicio=_hora("2026-11-25 10:00"))

        liberados = procesar_inasistencias(ahora=_hora("2026-11-24 18:30"))

        assert liberados == 1
        assert turno.estado == EstadoTurno.AUSENTE
        assert estudio.estado == EstadoEstudio.HABILITADO_TURNO
        aviso = db.session.scalars(
            sa.select(Aviso).where(Aviso.usuario_id == estudio.paciente.usuario_id)
        ).one()
        assert aviso.link == "/turnos/mio"
        assert aviso.estudio_id == estudio.id
        # El turno de mañana no se toca.
        assert turno_de_manana.estado == EstadoTurno.RESERVADO
        assert manana.estado == EstadoEstudio.TURNO_SACADO


def test_inasistencia_no_toca_el_turno_con_muestra(app, client, turno_sacado):
    _enviar(client, _update(turno_sacado["chat_id"], f"Muestra tomada {turno_sacado['codigo']}"))

    with app.app_context():
        muestra = db.session.scalars(sa.select(Muestra)).one()
        fin_del_dia = muestra.turno.inicio.astimezone(ZONA_HORARIA).replace(hour=18, minute=30)

        assert procesar_inasistencias(ahora=fin_del_dia) == 0
        assert muestra.turno.estado == EstadoTurno.ASISTIDO
        assert muestra.estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR


def test_la_tarea_de_inasistencias_corre_los_dias_habiles_a_las_18_30():
    tarea = tareas.buscar_tarea("inasistencias")

    assert tarea is not None
    assert tarea.funcion is procesar_inasistencias
    assert tarea.cuando == {"day_of_week": "mon-fri", "hour": 18, "minute": 30}


# --- GET /bot/mensajes: lista del administrativo ---


def test_el_administrativo_ve_los_mensajes_con_error(app, login_como, crear_mensaje_bot):
    with app.app_context():
        crear_mensaje_bot(texto="Hola", error="El chat no es de un centro de extracción.")
        crear_mensaje_bot(texto="Muestra tomada EX-2026-00001")
        db.session.commit()
    client = login_como(roles.ADMINISTRATIVO)

    todos = client.get("/bot/mensajes")
    con_error = client.get("/bot/mensajes?errores=1")

    assert todos.status_code == 200
    assert "Muestra tomada EX-2026-00001" in todos.text
    assert "El chat no es de un centro" in todos.text
    assert con_error.status_code == 200
    assert "El chat no es de un centro" in con_error.text
    assert "EX-2026-00001" not in con_error.text


def test_el_menu_del_administrativo_lleva_a_los_mensajes(login_como):
    client = login_como(roles.ADMINISTRATIVO)

    assert "/bot/mensajes" in client.get("/").text


@pytest.mark.parametrize(
    "rol", [rol for rol in roles.TODOS if rol != roles.ADMINISTRATIVO], ids=str
)
def test_los_demas_roles_no_entran_a_los_mensajes(login_como, rol):
    assert login_como(rol).get("/bot/mensajes").status_code == 403


def test_sin_sesion_los_mensajes_piden_login(client):
    respuesta = client.get("/bot/mensajes")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


# --- flask demo listo_para_retirar y flask bot simular ---


def test_demo_turno_sacado_y_bot_simular_pasan_a_listo_para_retirar(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0
    demo = runner.invoke(args=["demo", "turno_sacado"])
    assert demo.exit_code == 0, demo.output
    codigo = demo.output.split()[1]
    with app.app_context():
        from src.core.turnos import TurnoExtraccion

        chat_id = db.session.scalars(sa.select(TurnoExtraccion)).one().centro.telegram_chat_id

    resultado = runner.invoke(args=["bot", "simular", chat_id, f"Muestra tomada {codigo}"])

    assert resultado.exit_code == 0, resultado.output
    assert f"estudio {codigo} en Listo para retirar" in resultado.output
    with app.app_context():
        mensaje = _unico_mensaje()
        assert mensaje.telegram_update_id < 0
        assert mensaje.estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR


def test_bot_simular_muestra_el_error(app):
    resultado = app.test_cli_runner().invoke(args=["bot", "simular", "123", "hola"])

    assert resultado.exit_code == 0, resultado.output
    assert "guardado con error" in resultado.output
    assert "Respuesta al centro: (ninguna)" in resultado.output


def test_bot_simular_no_repite_update_id(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["bot", "simular", "123", "hola"])
    runner.invoke(args=["bot", "simular", "123", "hola"])

    with app.app_context():
        ids = db.session.scalars(sa.select(MensajeBot.telegram_update_id)).all()
        assert sorted(ids) == [-2, -1]


def test_demo_listo_para_retirar_crea_la_muestra(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    resultado = runner.invoke(args=["demo", "listo_para_retirar"])

    assert resultado.exit_code == 0, resultado.output
    with app.app_context():
        muestra = db.session.scalars(sa.select(Muestra)).one()
        assert muestra.turno.estado == EstadoTurno.ASISTIDO
        assert muestra.estudio.estado == EstadoEstudio.LISTO_PARA_RETIRAR
