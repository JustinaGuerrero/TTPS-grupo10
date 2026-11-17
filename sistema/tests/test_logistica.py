"""E23 Generar orden del día y E24 Retirar muestras, con el módulo de optimización de recorridos.

Con USE_MOCKS=1 el módulo ordena por cercanía (src/integraciones/optimizacion.py). Para probar
el orden que da el módulo y sus fallas, los tests le pasan un ClienteApi con httpx.MockTransport.
"""

import json
from datetime import date
from decimal import Decimal

import httpx
import pytest
import sqlalchemy as sa

from src.core.calendario import es_dia_habil, hoy, proximo_dia_habil
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio
from src.core.logistica import OrdenDelDia
from src.core.logistica.servicios import (
    ErrorDeRetiro,
    buscar_parada,
    generar_ordenes,
    orden_de,
    registrar_retiro,
)
from src.core.muestras import Muestra
from src.core.notificaciones import Aviso
from src.core.turnos import EstadoTurno
from src.core.turnos.franjas import franjas_del_dia
from src.core.usuarios import roles
from src.integraciones import optimizacion
from src.integraciones.base import ClienteApi, ErrorDeIntegracion
from src.integraciones.mail import mail
from src.web.tareas import buscar_tarea

MIERCOLES = date(2026, 11, 18)
SABADO = date(2026, 11, 21)
FERIADO = date(2026, 12, 8)  # Inmaculada Concepción, martes


@pytest.fixture
def muestra_lista(crear_estudio, crear_turno, crear_muestra):
    """`muestra_lista(centro)`: un estudio Listo para retirar con su muestra tomada en el centro."""
    usadas = []

    def _crear(centro) -> Estudio:
        # Cada muestra en otra franja: dos turnos asistidos no comparten centro y hora.
        inicio = franjas_del_dia(proximo_dia_habil(hoy()))[len(usadas)]
        usadas.append(inicio)
        estudio = crear_estudio(EstadoEstudio.LISTO_PARA_RETIRAR)
        turno = crear_turno(estudio, centro=centro, inicio=inicio, estado=EstadoTurno.ASISTIDO)
        crear_muestra(estudio, turno=turno)
        return estudio

    return _crear


def _modulo(responder) -> ClienteApi:
    """Un módulo de recorridos de prueba: `responder(ids_enviados)` devuelve la respuesta."""

    def handler(pedido: httpx.Request) -> httpx.Response:
        ids = [punto["id"] for punto in json.loads(pedido.content)["puntos"]]
        return responder(ids)

    return ClienteApi(
        optimizacion.NOMBRE, "https://recorridos.test", transport=httpx.MockTransport(handler)
    )


def _avisos_de(usuario):
    return db.session.scalars(sa.select(Aviso).where(Aviso.usuario_id == usuario.id)).all()


def _estado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


def _punto(id_, latitud, longitud):
    return optimizacion.Punto(id_, f"Dirección {id_}", Decimal(latitud), Decimal(longitud))


def test_las_fechas_de_los_tests_son_las_que_dicen(app):
    with app.app_context():
        assert es_dia_habil(MIERCOLES)
        assert not es_dia_habil(SABADO)
        assert not es_dia_habil(FERIADO)


# --- módulo de optimización de recorridos ---


def test_el_mock_ordena_por_cercania_desde_el_primero():
    puntos = [_punto(1, 0, 0), _punto(2, 0, 10), _punto(3, 0, 1), _punto(4, 0, 4)]

    assert optimizacion.por_cercania(puntos) == [1, 3, 4, 2]


def test_ordenar_manda_las_direcciones_y_devuelve_el_orden_del_modulo(app):
    enviados = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        enviados.append(json.loads(pedido.content))
        return httpx.Response(200, json={"orden": [3, 1, 2]})

    cliente = ClienteApi(
        "Recorridos", "https://recorridos.test", transport=httpx.MockTransport(handler)
    )
    puntos = [_punto(1, -34.9, -57.9), _punto(2, -34.7, -58.2), _punto(3, -38.0, -57.5)]

    assert optimizacion.ordenar(puntos, cliente=cliente) == [3, 1, 2]
    (cuerpo,) = enviados
    assert cuerpo["puntos"][0] == {
        "id": 1,
        "direccion": "Dirección 1",
        "latitud": -34.9,
        "longitud": -57.9,
    }


@pytest.mark.parametrize(
    "respuesta",
    [
        pytest.param(httpx.Response(200, json={"orden": [1]}), id="falta un centro"),
        pytest.param(httpx.Response(200, json={"orden": [1, 2, 2]}), id="centro repetido"),
        pytest.param(httpx.Response(200, json=[1, 2]), id="sin orden"),
        pytest.param(httpx.Response(500, json={"message": "caído"}), id="error interno"),
    ],
)
def test_una_respuesta_invalida_del_modulo_es_un_error(app, respuesta):
    cliente = ClienteApi(
        "Recorridos", "https://recorridos.test", transport=httpx.MockTransport(lambda _: respuesta)
    )

    with pytest.raises(ErrorDeIntegracion):
        optimizacion.ordenar([_punto(1, 0, 0), _punto(2, 0, 1)], cliente=cliente)


# --- E23 Generar orden del día ---


def test_genera_una_orden_por_provincia_con_muestras(
    app, crear_centro, crear_transportista, muestra_lista
):
    with app.app_context():
        bsas = crear_transportista("Buenos Aires")
        cordoba = crear_transportista("Córdoba")
        mendoza = crear_transportista("Mendoza")  # sin muestras
        la_plata, quilmes = crear_centro("Buenos Aires"), crear_centro("Buenos Aires")
        sin_muestras = crear_centro("Buenos Aires")
        centro_cordoba = crear_centro("Córdoba")
        for centro in (la_plata, quilmes, centro_cordoba):
            muestra_lista(centro)
        db.session.commit()

        with mail.record_messages() as enviados:
            generacion = generar_ordenes(MIERCOLES)
        db.session.commit()

        assert len(generacion.nuevas) == 2
        orden = orden_de(bsas.usuario, MIERCOLES)
        assert sorted(p.centro_id for p in orden.paradas) == [la_plata.id, quilmes.id]
        assert sin_muestras.id not in [p.centro_id for p in orden.paradas]
        assert [p.centro_id for p in orden_de(cordoba.usuario, MIERCOLES).paradas] == [
            centro_cordoba.id
        ]
        assert orden_de(mendoza.usuario, MIERCOLES) is None
        (aviso,) = _avisos_de(bsas.usuario)
        assert aviso.link == "/orden-del-dia"
        assert "2 centros" in aviso.mensaje
        assert bsas.usuario.email in [m.recipients[0] for m in enviados]


def test_sin_muestras_no_hay_ordenes(app, crear_transportista, crear_centro):
    with app.app_context():
        crear_transportista("Buenos Aires")
        crear_centro("Buenos Aires")
        db.session.commit()

        generacion = generar_ordenes(MIERCOLES)

        assert generacion.nuevas == []
        assert db.session.scalar(sa.select(sa.func.count()).select_from(OrdenDelDia)) == 0


@pytest.mark.parametrize("fecha", [SABADO, FERIADO], ids=["sábado", "feriado"])
def test_en_sabado_o_feriado_no_se_genera(
    app, crear_centro, crear_transportista, muestra_lista, fecha
):
    with app.app_context():
        crear_transportista("Buenos Aires")
        muestra_lista(crear_centro("Buenos Aires"))
        db.session.commit()

        generacion = generar_ordenes(fecha)

        assert not generacion.es_habil
        assert "no es día hábil" in str(generacion)
        assert db.session.scalar(sa.select(sa.func.count()).select_from(OrdenDelDia)) == 0


def test_una_segunda_corrida_no_duplica(app, crear_centro, crear_transportista, muestra_lista):
    with app.app_context():
        transportista = crear_transportista("Buenos Aires")
        muestra_lista(crear_centro("Buenos Aires"))
        db.session.commit()
        generar_ordenes(MIERCOLES)
        db.session.commit()

        segunda = generar_ordenes(MIERCOLES)
        db.session.commit()

        assert segunda.nuevas == []
        assert len(segunda.ya_generadas) == 1
        assert db.session.scalar(sa.select(sa.func.count()).select_from(OrdenDelDia)) == 1
        assert len(_avisos_de(transportista.usuario)) == 1


def test_las_paradas_respetan_el_orden_del_modulo(
    app, crear_centro, crear_transportista, muestra_lista
):
    with app.app_context():
        transportista = crear_transportista("Buenos Aires")
        centros = [crear_centro("Buenos Aires") for _ in range(3)]
        for centro in centros:
            muestra_lista(centro)
        db.session.commit()
        invierte = _modulo(lambda ids: httpx.Response(200, json={"orden": ids[::-1]}))

        generar_ordenes(MIERCOLES, cliente=invierte)

        orden = orden_de(transportista.usuario, MIERCOLES)
        assert [p.centro_id for p in orden.paradas] == [c.id for c in reversed(centros)]
        assert [p.posicion for p in orden.paradas] == [1, 2, 3]


def test_con_el_modulo_caido_no_hay_orden_y_se_avisa(
    app, crear_centro, crear_transportista, muestra_lista, usuario_rapido
):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        transportista = crear_transportista("Buenos Aires")
        muestra_lista(crear_centro("Buenos Aires"))
        db.session.commit()
        caido = _modulo(lambda _: httpx.Response(503, json={"message": "mantenimiento"}))

        generacion = generar_ordenes(MIERCOLES, cliente=caido)

        assert orden_de(transportista.usuario, MIERCOLES) is None
        assert [provincia.nombre for provincia, _ in generacion.con_error] == ["Buenos Aires"]
        (aviso,) = _avisos_de(administrativo)
        assert aviso.asunto == "No se generó la orden del día"
        assert aviso.link == "/ordenes-del-dia"
        assert _avisos_de(transportista.usuario) == []


def test_una_provincia_sin_transportista_avisa_a_los_administrativos(
    app, crear_centro, crear_transportista, muestra_lista, usuario_rapido
):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        crear_transportista("Córdoba", activo=False)  # desactivado: no cuenta
        muestra_lista(crear_centro("Córdoba"))
        db.session.commit()

        generacion = generar_ordenes(MIERCOLES)

        assert [provincia.nombre for provincia in generacion.sin_transportista] == ["Córdoba"]
        (aviso,) = _avisos_de(administrativo)
        assert aviso.asunto == "Provincia sin transportista"
        assert "Córdoba" in aviso.mensaje


def test_la_tarea_corre_los_dias_habiles_a_las_7():
    tarea = buscar_tarea("ordenes_del_dia")

    assert tarea.funcion is generar_ordenes
    assert tarea.cuando == {"day_of_week": "mon-fri", "hour": 7}


# --- E24 Retirar muestras ---


@pytest.fixture
def recorrido(app, crear_centro, crear_transportista, crear_orden_del_dia, muestra_lista):
    """Una orden de hoy con dos centros: el primero con dos muestras y el segundo con una."""
    with app.app_context():
        transportista = crear_transportista("Buenos Aires")
        primero, segundo = crear_centro("Buenos Aires"), crear_centro("Buenos Aires")
        estudios_del_primero = [muestra_lista(primero), muestra_lista(primero)]
        estudio_del_segundo = muestra_lista(segundo)
        orden = crear_orden_del_dia(transportista, [primero, segundo])
        db.session.commit()
        return {
            "transportista": transportista.usuario,
            "orden_id": orden.id,
            "primero": [estudio.id for estudio in estudios_del_primero],
            "segundo": estudio_del_segundo.id,
        }


def test_el_retiro_en_orden_pasa_las_muestras_a_en_camino(app, recorrido, crear_centro):
    with app.app_context():
        orden = db.session.get(OrdenDelDia, recorrido["orden_id"])
        transportista = db.session.merge(recorrido["transportista"])

        retirados = registrar_retiro(buscar_parada(orden, 1), transportista)
        db.session.commit()

        assert sorted(e.id for e in retirados) == sorted(recorrido["primero"])
        for estudio_id in recorrido["primero"]:
            assert _estado(estudio_id) == EstadoEstudio.EN_CAMINO_LABORATORIO
        assert _estado(recorrido["segundo"]) == EstadoEstudio.LISTO_PARA_RETIRAR
        parada = buscar_parada(db.session.get(OrdenDelDia, recorrido["orden_id"]), 1)
        assert parada.retirado_en is not None
        muestras = db.session.scalars(
            sa.select(Muestra).where(Muestra.estudio_id.in_(recorrido["primero"]))
        ).all()
        assert {m.orden_del_dia_id for m in muestras} == {recorrido["orden_id"]}


def test_el_retiro_se_lleva_las_muestras_que_llegaron_despues(app, recorrido, muestra_lista):
    with app.app_context():
        orden = db.session.get(OrdenDelDia, recorrido["orden_id"])
        tardia = muestra_lista(orden.paradas[0].centro)  # después de generar la orden (G10)
        db.session.commit()

        retirados = registrar_retiro(
            buscar_parada(orden, 1), db.session.merge(recorrido["transportista"])
        )

        assert tardia.id in [estudio.id for estudio in retirados]


def test_no_se_puede_saltear_una_parada_ni_retirar_dos_veces(app, recorrido):
    with app.app_context():
        orden = db.session.get(OrdenDelDia, recorrido["orden_id"])
        transportista = db.session.merge(recorrido["transportista"])

        with pytest.raises(ErrorDeRetiro, match="primero retirá"):
            registrar_retiro(buscar_parada(orden, 2), transportista)
        registrar_retiro(buscar_parada(orden, 1), transportista)
        with pytest.raises(ErrorDeRetiro, match="Ya registraste"):
            registrar_retiro(buscar_parada(orden, 1), transportista)


def test_solo_el_transportista_de_la_orden_registra_el_retiro(app, recorrido, crear_transportista):
    with app.app_context():
        orden = db.session.get(OrdenDelDia, recorrido["orden_id"])
        otro = crear_transportista("Córdoba")

        with pytest.raises(ErrorDeRetiro, match="Solo el transportista"):
            registrar_retiro(buscar_parada(orden, 1), otro.usuario)


# --- Pantallas ---


def test_el_transportista_ve_su_orden_y_registra_el_retiro(app, client, recorrido):
    with app.app_context():
        _entrar_como(client, db.session.merge(recorrido["transportista"]))

    pagina = client.get("/orden-del-dia")
    assert pagina.status_code == 200
    assert pagina.text.count("Registrar el retiro") == 1  # solo en la siguiente parada
    assert "2 muestras para retirar" in pagina.text

    fuera_de_orden = client.post("/orden-del-dia/paradas/2/retiro")
    assert fuera_de_orden.status_code == 302
    with app.app_context():
        assert _estado(recorrido["segundo"]) == EstadoEstudio.LISTO_PARA_RETIRAR

    assert client.post("/orden-del-dia/paradas/1/retiro").status_code == 302
    assert client.post("/orden-del-dia/paradas/2/retiro").status_code == 302
    with app.app_context():
        assert _estado(recorrido["segundo"]) == EstadoEstudio.EN_CAMINO_LABORATORIO
    assert "Retiraste las muestras de todos los centros" in client.get("/orden-del-dia").text


def test_sin_orden_el_transportista_lo_ve(app, client, crear_transportista):
    with app.app_context():
        transportista = crear_transportista("Buenos Aires")
        db.session.commit()
        _entrar_como(client, transportista.usuario)

    assert 'id="sin-orden"' in client.get("/orden-del-dia").text


def test_otro_transportista_no_retira_en_una_orden_ajena(
    app, client, recorrido, crear_transportista
):
    with app.app_context():
        otro = crear_transportista("Córdoba")
        db.session.commit()
        _entrar_como(client, otro.usuario)

    assert client.post("/orden-del-dia/paradas/1/retiro").status_code == 404
    with app.app_context():
        for estudio_id in recorrido["primero"]:
            assert _estado(estudio_id) == EstadoEstudio.LISTO_PARA_RETIRAR


def test_el_paciente_no_entra_a_la_orden_del_dia(login_como):
    assert login_como(roles.PACIENTE).get("/orden-del-dia").status_code == 403


def test_el_transportista_no_entra_a_las_ordenes_del_administrativo(login_como):
    assert login_como(roles.TRANSPORTISTA).get("/ordenes-del-dia").status_code == 403


def test_el_administrativo_ve_las_ordenes_y_las_regenera(
    app, client, crear_centro, crear_transportista, muestra_lista, usuario_rapido, monkeypatch
):
    from src.core.logistica import servicios
    from src.web.controllers import logistica

    monkeypatch.setattr(servicios, "hoy", lambda: MIERCOLES)
    monkeypatch.setattr(logistica, "hoy", lambda: MIERCOLES)
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        crear_transportista("Buenos Aires")
        centro = crear_centro("Buenos Aires")
        muestra_lista(centro)
        db.session.commit()
        nombre_del_centro = centro.nombre
        _entrar_como(client, administrativo)

    assert 'id="sin-ordenes"' in client.get("/ordenes-del-dia").text
    assert client.post("/ordenes-del-dia/generar").status_code == 302

    pagina = client.get("/ordenes-del-dia")
    assert "Órdenes del día: 1 orden nueva." in pagina.text
    assert nombre_del_centro in pagina.text
    assert "0 de 1" in pagina.text
    assert 'id="sin-ordenes"' in client.get("/ordenes-del-dia?fecha=2026-11-19").text


def test_los_menus_tienen_la_orden_del_dia(login_como):
    assert "Orden del día" in login_como(roles.TRANSPORTISTA).get("/").text


def test_el_menu_del_administrativo_tiene_las_ordenes(login_como):
    assert "Órdenes del día" in login_como(roles.ADMINISTRATIVO).get("/").text


# --- flask demo ---


def test_demo_listo_para_retirar_entra_en_la_orden_del_transportista_de_prueba(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    resultado = runner.invoke(args=["demo", "listo_para_retirar"])

    assert resultado.exit_code == 0, resultado.output
    with app.app_context():
        generacion = generar_ordenes(MIERCOLES)
        (orden,) = generacion.nuevas
        assert orden.transportista.usuario.email == "transportista@exoma.test"
        assert [p.centro.nombre for p in orden.paradas] == ["Centro La Plata"]


def test_demo_en_camino_deja_la_muestra_en_una_orden_retirada(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    resultado = runner.invoke(args=["demo", "en_camino_laboratorio"])

    assert resultado.exit_code == 0, resultado.output
    with app.app_context():
        muestra = db.session.scalars(sa.select(Muestra)).one()
        assert muestra.estudio.estado == EstadoEstudio.EN_CAMINO_LABORATORIO
        orden = muestra.orden_del_dia
        assert orden.fecha < hoy()
        assert [p.retirado_en is not None for p in orden.paradas] == [True]
