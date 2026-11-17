"""Autorización de la obra social desde su módulo (módulo 6, grupo 9, G22): alta de la solicitud,
demanda sobre la misma solicitud, consulta de la respuesta con la tarea programada y respaldo a
mano.

La API responde con los mocks de tests/fixtures/apis/obras_sociales/ (alta: solicitud pendiente;
estado: autorizada con el porcentaje de la lista; demanda: demanda_en_curso). Para otras
respuestas, los tests reemplazan estado_estudio o usan un ClienteApi con httpx.MockTransport.
"""

import json
from decimal import Decimal
from io import BytesIO

import httpx
import pytest
import sqlalchemy as sa

from src.core.calendario import ZONA_HORARIA
from src.core.coberturas import (
    DemandaReautorizacion,
    EstadoCobertura,
    autorizar,
    cargar_demanda,
    cobertura_de,
    consultar_respuestas,
    dar_de_alta_en_modulo,
    presentar_demanda_en_modulo,
    rechazar,
    solicitar,
)
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.finanzas import AsientoFinanciero, Pago, TipoAsiento, TipoPago
from src.core.notificaciones import Aviso
from src.core.obras_sociales import ObraSocial
from src.core.usuarios import roles
from src.integraciones import obras_sociales as api
from src.integraciones.base import ClienteApi, ErrorDeIntegracion
from src.web.tareas import buscar_tarea

PDF = b"%PDF-1.4 resolucion judicial de prueba"
ID_DE_LA_PARCIAL = "0b9e4f8a-0000-4000-8000-000000000070"  # OS-070 en listar.json
ID_DEL_MOCK = "5b1f0c0a-0000-4000-8000-000000000001"  # alta_estudio.json


@pytest.fixture(autouse=True)
def storage_en_tmp(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)


@pytest.fixture
def respuestas(monkeypatch):
    """`respuestas["MOD-1"] = RespuestaDelModulo(...)`: lo que contesta el módulo por cada id.
    Un id que no está responde pendiente; uno con un ErrorDeIntegracion lo lanza."""
    por_id = {}

    def estado_estudio(id_solicitud, *, cliente=None):
        respuesta = por_id.get(id_solicitud, api.RespuestaDelModulo(api.EstadoEnModulo.PENDIENTE))
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(api, "estado_estudio", estado_estudio)
    return por_id


def _modulo(handler) -> ClienteApi:
    return ClienteApi(api.NOMBRE, "https://os.test", transport=httpx.MockTransport(handler))


def _solicitud(estado="pendiente", **campos):
    """Una Solicitud del contrato, como la devuelve el módulo."""
    return {
        "id": campos.pop("id", "MOD-1"),
        "estado": estado,
        "porcentaje_cobertura": campos.pop("porcentaje_cobertura", None),
        "motivo_rechazo": campos.pop("motivo_rechazo", None),
        "urls_simulacion": {
            "autorizar": "https://os.test/simulacion/token-1/autorizar",
            "rechazar": "https://os.test/simulacion/token-1/rechazar",
        },
        **campos,
    }


def _caido(*args, **kwargs):
    raise ErrorDeIntegracion(api.NOMBRE, "La API de obras sociales no respondió.")


def _pedido(crear_estudio, crear_presupuesto, codigo="OS-070", id_modulo="MOD-1"):
    """Estudio en Pendiente de autorización con su solicitud dada de alta en el módulo."""
    estudio = crear_estudio(genes=("GAA",))  # 500 USD
    crear_presupuesto(estudio)
    db.session.commit()
    cobertura = solicitar(estudio, estudio.paciente.usuario, codigo)
    cobertura.id_estudio_modulo = id_modulo
    db.session.commit()
    return estudio


def _autorizada(porcentaje=None):
    return api.RespuestaDelModulo(api.EstadoEnModulo.AUTORIZADA, porcentaje=porcentaje)


def _rechazada(motivo=None):
    return api.RespuestaDelModulo(api.EstadoEnModulo.RECHAZADA, motivo=motivo)


def _estado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _entrar_como(client, usuario_id):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario_id


# --- cliente del módulo (contrato del grupo 9) ---


def test_listar_lee_la_pagina_con_el_codigo_rnos_y_el_id(app):
    with app.app_context():
        obras = api.listar()

    parcial = next(obra for obra in obras if obra.codigo == "OS-070")
    assert parcial == api.ObraSocialEnApi(
        "OS-070", "Obra Social de Prueba Parcial", Decimal(70), ID_DE_LA_PARCIAL
    )


def test_listar_recorre_todas_las_paginas_con_la_clave_en_el_header(app):
    pedidos = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        pedidos.append((pedido.url.params["pagina"], pedido.headers.get("x-api-key")))
        pagina = int(pedido.url.params["pagina"])
        item = {
            "id": f"id-{pagina}",
            "rnos_codigo": f"RNOS-{pagina}",
            "nombre": f"Obra {pagina}",
            "sigla": None,
            "porcentaje_cobertura": 80,
        }
        return httpx.Response(200, json={"datos": [item], "pagina": pagina, "total_paginas": 2})

    cliente = ClienteApi(
        api.NOMBRE,
        "https://os.test",
        headers={"x-api-key": "clave-de-prueba"},
        transport=httpx.MockTransport(handler),
    )

    obras = api.listar(cliente=cliente)

    assert [obra.codigo for obra in obras] == ["RNOS-1", "RNOS-2"]
    assert pedidos == [("1", "clave-de-prueba"), ("2", "clave-de-prueba")]


def test_el_alta_manda_el_id_de_la_obra_social_nombre_fecha_y_codigo(
    app, crear_estudio, crear_presupuesto
):
    enviados = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        enviados.append((pedido.method, pedido.url.path, json.loads(pedido.content)))
        return httpx.Response(201, json=_solicitud(id="MOD-77"))

    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo=None)
        cobertura = cobertura_de(estudio)

        assert dar_de_alta_en_modulo(cobertura, cliente=_modulo(handler)) == "MOD-77"

        assert cobertura.id_estudio_modulo == "MOD-77"
        ((metodo, ruta, cuerpo),) = enviados
        assert (metodo, ruta) == ("POST", "/solicitudes")
        assert cuerpo == {
            "obra_social_id": ID_DE_LA_PARCIAL,
            "paciente_nombre": estudio.paciente.usuario.nombre_completo,
            "fecha": cobertura.solicitada_en.astimezone(ZONA_HORARIA).date().isoformat(),
            "referencia_externa": estudio.codigo,
        }


@pytest.mark.parametrize(
    ("solicitud", "esperado"),
    [
        (_solicitud("pendiente"), api.RespuestaDelModulo(api.EstadoEnModulo.PENDIENTE)),
        (_solicitud("autorizada", porcentaje_cobertura=80), _autorizada(Decimal(80))),
        (_solicitud("rechazada", motivo_rechazo="Sin cobertura"), _rechazada("Sin cobertura")),
        (
            _solicitud("demanda_en_curso", motivo_rechazo="Sin cobertura"),
            api.RespuestaDelModulo(api.EstadoEnModulo.DEMANDA_EN_CURSO, motivo="Sin cobertura"),
        ),
    ],
)
def test_el_estado_se_lee_del_modulo(app, solicitud, esperado):
    cliente = _modulo(lambda _: httpx.Response(200, json=solicitud))

    assert api.estado_estudio("MOD-1", cliente=cliente) == esperado


def test_un_estado_desconocido_es_un_error(app):
    cliente = _modulo(lambda _: httpx.Response(200, json=_solicitud("quizas")))

    with pytest.raises(ErrorDeIntegracion):
        api.estado_estudio("MOD-1", cliente=cliente)


def test_la_demanda_sube_el_pdf_en_el_campo_archivo(app):
    pedidos = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        pedidos.append((pedido.url.path, pedido.headers["content-type"], pedido.read()))
        return httpx.Response(201, json=_solicitud("demanda_en_curso"))

    respuesta = api.presentar_demanda("MOD-1", PDF, cliente=_modulo(handler))

    assert respuesta.estado == api.EstadoEnModulo.DEMANDA_EN_CURSO
    ((ruta, tipo, cuerpo),) = pedidos
    assert ruta == "/solicitudes/MOD-1/demanda"
    assert tipo.startswith("multipart/form-data")
    assert b'name="archivo"' in cuerpo
    assert PDF in cuerpo


# --- alta al elegir la obra social ---


def test_al_elegir_la_obra_social_se_da_de_alta_la_solicitud(
    app, client, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        estudio = crear_estudio(genes=("GAA",))
        crear_presupuesto(estudio)
        db.session.commit()
        estudio_id, paciente_id = estudio.id, estudio.paciente.usuario_id
        administrativo_id = administrativo.id
        _entrar_como(client, paciente_id)

    client.post(f"/estudios/{estudio_id}/cobertura", data={"codigo": "OS-070"})

    with app.app_context():
        estudio = db.session.get(Estudio, estudio_id)
        assert cobertura_de(estudio).id_estudio_modulo == ID_DEL_MOCK
        assert db.session.get(ObraSocial, "OS-070").id_modulo == ID_DE_LA_PARCIAL
        aviso = db.session.scalars(
            sa.select(Aviso).where(Aviso.usuario_id == administrativo_id)
        ).one()
        assert "módulo de obras sociales" in aviso.mensaje


def test_con_el_modulo_caido_el_pedido_queda_y_la_tarea_lo_da_de_alta(
    app, client, crear_estudio, crear_presupuesto, monkeypatch
):
    with app.app_context():
        estudio = crear_estudio(genes=("GAA",))
        crear_presupuesto(estudio)
        db.session.commit()
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario_id)
    monkeypatch.setattr(api, "alta_estudio", _caido)

    respuesta = client.post(f"/estudios/{estudio_id}/cobertura", data={"codigo": "OS-070"})

    assert respuesta.status_code == 302
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        cobertura = cobertura_de(db.session.get(Estudio, estudio_id))
        assert cobertura.estado == EstadoCobertura.PENDIENTE
        assert cobertura.id_estudio_modulo is None
        monkeypatch.undo()

        consulta = consultar_respuestas()
        db.session.commit()

        assert consulta.dadas_de_alta == 1
        assert cobertura_de(db.session.get(Estudio, estudio_id)).id_estudio_modulo == ID_DEL_MOCK


def test_una_obra_social_guardada_sin_id_lo_busca_en_el_modulo(
    app, crear_estudio, crear_presupuesto
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo=None)
        db.session.get(ObraSocial, "OS-070").id_modulo = None  # de antes del contrato
        db.session.commit()

        dar_de_alta_en_modulo(cobertura_de(estudio))

        assert db.session.get(ObraSocial, "OS-070").id_modulo == ID_DE_LA_PARCIAL


# --- respuesta desde el módulo ---


def test_autorizada_al_100_habilita_el_turno_sin_usuario(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100")
        respuestas["MOD-1"] = _autorizada(Decimal(100))

        consulta = consultar_respuestas()
        db.session.commit()

        assert consulta.autorizadas == 1
        assert _estado(estudio.id) == EstadoEstudio.HABILITADO_TURNO
        cobertura = cobertura_de(estudio)
        assert cobertura.estado == EstadoCobertura.AUTORIZADA
        assert cobertura.respondida_por is None
        assert cobertura.respondida_en is not None
        pago = db.session.scalars(sa.select(Pago).where(Pago.estudio_id == estudio.id)).one()
        assert (pago.tipo, pago.importe_usd) == (TipoPago.OBRA_SOCIAL, Decimal("500.00"))
        asiento = db.session.scalars(
            sa.select(AsientoFinanciero).where(
                AsientoFinanciero.estudio_id == estudio.id,
                AsientoFinanciero.tipo == TipoAsiento.COBERTURA_OBRA_SOCIAL,
            )
        ).one()
        assert asiento.importe_usd == Decimal("500.00")
        ultimo = db.session.scalars(
            sa.select(HistorialEstado)
            .where(HistorialEstado.estudio_id == estudio.id)
            .order_by(HistorialEstado.id.desc())
        ).first()
        assert ultimo.usuario_id is None


def test_autorizada_al_70_pide_la_diferencia(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-070")
        respuestas["MOD-1"] = _autorizada(Decimal(70))

        consultar_respuestas()
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert cobertura_de(estudio).importe_cubierto_usd == Decimal("350.00")


def test_se_usa_el_porcentaje_que_autorizo_el_modulo(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-070")
        respuestas["MOD-1"] = _autorizada(Decimal(80))  # otro que el de la lista (70)

        consultar_respuestas()
        db.session.commit()

        cobertura = cobertura_de(estudio)
        assert cobertura.porcentaje == Decimal(80)
        assert cobertura.importe_cubierto_usd == Decimal("400.00")


def test_sin_porcentaje_se_usa_el_de_la_lista(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-070")
        respuestas["MOD-1"] = _autorizada()

        consultar_respuestas()

        assert cobertura_de(estudio).importe_cubierto_usd == Decimal("350.00")


def test_una_autorizacion_al_0_queda_con_error(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto)
        respuestas["MOD-1"] = _autorizada(Decimal(0))

        consulta = consultar_respuestas()

        assert consulta.con_error == [estudio.codigo]
        assert cobertura_de(estudio).estado == EstadoCobertura.PENDIENTE


def test_rechazada_pasa_a_rechazado_por_obra_social_con_el_motivo(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto)
        respuestas["MOD-1"] = _rechazada("El plan no cubre estudios genéticos")

        consulta = consultar_respuestas()
        db.session.commit()

        assert consulta.rechazadas == 1
        assert _estado(estudio.id) == EstadoEstudio.RECHAZADO_OBRA_SOCIAL
        aviso = db.session.scalars(
            sa.select(Aviso)
            .where(Aviso.usuario_id == estudio.paciente.usuario_id)
            .order_by(Aviso.id.desc())
        ).first()
        assert "El plan no cubre estudios genéticos" in aviso.mensaje


@pytest.mark.parametrize(
    "estado", [api.EstadoEnModulo.PENDIENTE, api.EstadoEnModulo.DEMANDA_EN_CURSO]
)
def test_sin_respuesta_no_cambia_nada(app, crear_estudio, crear_presupuesto, respuestas, estado):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto)
        respuestas["MOD-1"] = api.RespuestaDelModulo(estado)

        consulta = consultar_respuestas()

        assert consulta.sin_respuesta == 1
        assert _estado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Pago)) == 0


def test_si_el_modulo_falla_con_una_las_demas_se_procesan(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        falla = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100", id_modulo="MOD-1")
        anda = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100", id_modulo="MOD-2")
        respuestas["MOD-1"] = ErrorDeIntegracion(api.NOMBRE, "No respondió a tiempo.")
        respuestas["MOD-2"] = _autorizada(Decimal(100))

        consulta = consultar_respuestas()
        db.session.commit()

        assert consulta.con_error == [falla.codigo]
        assert _estado(falla.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert _estado(anda.id) == EstadoEstudio.HABILITADO_TURNO


def test_una_respondida_a_mano_no_se_vuelve_a_consultar(
    app, crear_estudio, crear_presupuesto, respuestas, usuario_rapido
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100")
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()
        autorizar(cobertura_de(estudio), administrativo)
        db.session.commit()
        respuestas["MOD-1"] = _rechazada()

        consulta = consultar_respuestas()

        assert (consulta.autorizadas, consulta.rechazadas, consulta.sin_respuesta) == (0, 0, 0)
        assert cobertura_de(estudio).respondida_por == administrativo.id
        assert _estado(estudio.id) == EstadoEstudio.HABILITADO_TURNO


# --- demanda de reautorización (E18) ---


def _rechazado(crear_estudio, crear_presupuesto, id_modulo="MOD-1"):
    estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo=id_modulo)
    rechazar(cobertura_de(estudio), None, "Plan sin cobertura")
    db.session.commit()
    return estudio


def test_la_demanda_se_presenta_sobre_la_misma_solicitud(
    app, client, crear_estudio, crear_presupuesto
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario_id)

    client.post(
        f"/estudios/{estudio_id}/reautorizacion",
        data={"resolucion": (BytesIO(PDF), "resolucion.pdf")},
        content_type="multipart/form-data",
    )

    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        cobertura = cobertura_de(db.session.get(Estudio, estudio_id))
        assert cobertura.id_estudio_modulo == "MOD-1"  # la misma solicitud, no una nueva
        (demanda,) = cobertura.demandas
        assert demanda.presentada_en_modulo_en is not None


def test_si_la_demanda_no_salio_la_tarea_la_sube_antes_de_leer_el_rechazo(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto)
        cargar_demanda(estudio, estudio.paciente.usuario, PDF)  # el módulo no se enteró todavía
        db.session.commit()
        respuestas["MOD-1"] = _rechazada("Plan sin cobertura")  # el rechazo de antes

        primera = consultar_respuestas()
        db.session.commit()

        assert primera.demandas_presentadas == 1
        assert primera.rechazadas == 0
        assert _estado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        demanda = db.session.scalars(sa.select(DemandaReautorizacion)).one()
        assert demanda.presentada_en_modulo_en is not None

        respuestas["MOD-1"] = _autorizada(Decimal(100))
        segunda = consultar_respuestas()
        db.session.commit()

        assert segunda.autorizadas == 1
        assert cobertura_de(estudio).estado == EstadoCobertura.AUTORIZADA


def test_si_la_solicitud_no_estaba_rechazada_la_demanda_se_da_por_presentada(
    app, crear_estudio, crear_presupuesto
):
    respuesta = {
        "error": {
            "codigo": "ESTADO_INVALIDO",
            "mensaje": "Solo se puede presentar una demanda sobre una solicitud rechazada",
            "detalle": {"estado_actual": "pendiente"},
        }
    }
    cliente = _modulo(lambda _: httpx.Response(409, json=respuesta))
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto)
        demanda = cargar_demanda(estudio, estudio.paciente.usuario, PDF)

        presentar_demanda_en_modulo(demanda, PDF, cliente=cliente)

        assert demanda.presentada_en_modulo_en is not None


def test_sin_solicitud_en_el_modulo_la_demanda_va_en_un_alta_nueva(
    app, crear_estudio, crear_presupuesto
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto, id_modulo=None)
        demanda = cargar_demanda(estudio, estudio.paciente.usuario, PDF)

        presentar_demanda_en_modulo(demanda, PDF)

        assert cobertura_de(estudio).id_estudio_modulo == ID_DEL_MOCK
        assert demanda.presentada_en_modulo_en is not None


# --- tarea, comando y pantalla ---


def test_la_tarea_corre_cada_30_minutos():
    tarea = buscar_tarea("respuestas_obras_sociales")

    assert tarea.funcion is consultar_respuestas
    assert tarea.cuando == {"minute": "*/30"}


def test_flask_tarea_aplica_la_respuesta_del_mock(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100", id_modulo=None)
        estudio_id = estudio.id

    resultado = app.test_cli_runner().invoke(args=["tarea", "respuestas_obras_sociales"])

    assert resultado.exit_code == 0, resultado.output
    assert "1 dadas de alta en el módulo" in resultado.output
    resultado = app.test_cli_runner().invoke(args=["tarea", "respuestas_obras_sociales"])
    assert "1 autorizadas" in resultado.output
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.HABILITADO_TURNO


def test_flask_obra_social_simular_hace_de_la_obra_social(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        codigo = _pedido(crear_estudio, crear_presupuesto, id_modulo=ID_DEL_MOCK).codigo
    runner = app.test_cli_runner()

    autoriza = runner.invoke(args=["obra-social", "simular", codigo, "autorizar"])
    rechaza = runner.invoke(
        args=["obra-social", "simular", codigo, "rechazar", "--motivo", "Sin cobertura"]
    )
    inexistente = runner.invoke(args=["obra-social", "simular", "EX-1900-00001", "autorizar"])

    assert autoriza.exit_code == 0, autoriza.output
    assert "quedó autorizada" in autoriza.output
    assert "quedó rechazada" in rechaza.output
    assert inexistente.exit_code != 0


def test_el_administrativo_ve_el_estado_en_el_modulo_y_consulta_a_mano(
    app, client, crear_estudio, crear_presupuesto, usuario_rapido, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100")
        sin_enviar = _pedido(crear_estudio, crear_presupuesto, id_modulo=None)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.commit()
        estudio_id, sin_enviar_id = estudio.id, sin_enviar.id
        _entrar_como(client, administrativo.id)
    respuestas["MOD-1"] = _autorizada(Decimal(100))

    lista = client.get("/coberturas")
    assert "En el módulo: MOD-1" in lista.text
    assert "Sin enviar al módulo" in lista.text

    assert client.post("/coberturas/consultar").status_code == 302
    pagina = client.get("/coberturas")
    assert "1 autorizadas" in pagina.text
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.HABILITADO_TURNO
        cobertura = cobertura_de(db.session.get(Estudio, sin_enviar_id))
        assert cobertura.id_estudio_modulo == ID_DEL_MOCK


def test_el_paciente_no_consulta_el_modulo(login_como):
    assert login_como(roles.PACIENTE).post("/coberturas/consultar").status_code == 403
