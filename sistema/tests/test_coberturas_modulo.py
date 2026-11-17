"""Autorización de la obra social desde su módulo (G22): alta del estudio en el módulo de obras
sociales, consulta de la respuesta con la tarea programada y respaldo a mano.

La API responde con los mocks de tests/fixtures/apis/obras_sociales/ (alta: MOD-OS-0001; estado:
autorizado). Para otras respuestas, los tests reemplazan alta_estudio o estado_estudio.
"""

import json
from decimal import Decimal
from io import BytesIO

import httpx
import pytest
import sqlalchemy as sa

from src.core.coberturas import (
    EstadoCobertura,
    autorizar,
    cargar_demanda,
    cobertura_de,
    consultar_respuestas,
    dar_de_alta_en_modulo,
    rechazar,
    solicitar,
)
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.finanzas import AsientoFinanciero, Pago, TipoAsiento, TipoPago
from src.core.notificaciones import Aviso
from src.core.usuarios import roles
from src.integraciones import obras_sociales as api
from src.integraciones.base import ClienteApi, ErrorDeIntegracion
from src.web.tareas import buscar_tarea

PDF = b"%PDF-1.4 resolucion judicial de prueba"


@pytest.fixture(autouse=True)
def storage_en_tmp(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)


@pytest.fixture
def respuestas(monkeypatch):
    """`respuestas["MOD-1"] = RespuestaDelModulo(...)`: lo que contesta el módulo por cada id.
    Un id que no está responde pendiente; uno con un ErrorDeIntegracion lo lanza."""
    por_id = {}

    def estado_estudio(id_estudio, *, cliente=None):
        respuesta = por_id.get(id_estudio, api.RespuestaDelModulo(api.EstadoEnModulo.PENDIENTE))
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(api, "estado_estudio", estado_estudio)
    return por_id


def _caido(*args, **kwargs):
    raise ErrorDeIntegracion(api.NOMBRE, "La API de obras sociales no respondió.")


def _pedido(crear_estudio, crear_presupuesto, codigo="OS-070", id_modulo="MOD-1"):
    """Estudio en Pendiente de autorización con su cobertura dada de alta en el módulo."""
    estudio = crear_estudio(genes=("GAA",))  # 500 USD
    crear_presupuesto(estudio)
    db.session.commit()
    cobertura = solicitar(estudio, estudio.paciente.usuario, codigo)
    cobertura.id_estudio_modulo = id_modulo
    db.session.commit()
    return estudio


def _autorizado(**kwargs):
    return api.RespuestaDelModulo(api.EstadoEnModulo.AUTORIZADO, **kwargs)


def _rechazado(motivo=None):
    return api.RespuestaDelModulo(api.EstadoEnModulo.RECHAZADO, motivo)


def _estado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _entrar_como(client, usuario_id):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario_id


# --- cliente del módulo ---


def test_el_alta_manda_solo_obra_social_nombre_y_fecha(app, crear_estudio, crear_presupuesto):
    enviados = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        enviados.append((pedido.method, pedido.url.path, json.loads(pedido.content)))
        return httpx.Response(201, json={"id": "MOD-77"})

    cliente = ClienteApi(api.NOMBRE, "https://os.test", transport=httpx.MockTransport(handler))
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo=None)
        cobertura = cobertura_de(estudio)

        assert dar_de_alta_en_modulo(cobertura, cliente=cliente) == "MOD-77"

        assert cobertura.id_estudio_modulo == "MOD-77"
        ((metodo, ruta, cuerpo),) = enviados
        assert (metodo, ruta) == ("POST", "/estudios")
        assert cuerpo == {
            "obra_social": "OS-070",
            "paciente": estudio.paciente.usuario.nombre_completo,
            "fecha": cobertura.solicitada_en.date().isoformat(),
        }


@pytest.mark.parametrize(
    ("respuesta", "esperado"),
    [
        (
            {"id": "MOD-1", "estado": "pendiente"},
            api.RespuestaDelModulo(api.EstadoEnModulo.PENDIENTE),
        ),
        (
            {"id": "MOD-1", "estado": "rechazado", "motivo": "Sin cobertura"},
            _rechazado("Sin cobertura"),
        ),
    ],
)
def test_el_estado_se_lee_del_modulo(app, respuesta, esperado):
    cliente = ClienteApi(
        api.NOMBRE,
        "https://os.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=respuesta)),
    )

    assert api.estado_estudio("MOD-1", cliente=cliente) == esperado


def test_un_estado_desconocido_es_un_error(app):
    cliente = ClienteApi(
        api.NOMBRE,
        "https://os.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"estado": "quizas"})),
    )

    with pytest.raises(ErrorDeIntegracion):
        api.estado_estudio("MOD-1", cliente=cliente)


# --- alta al elegir la obra social ---


def test_al_elegir_la_obra_social_el_estudio_se_da_de_alta_en_el_modulo(
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
        assert cobertura_de(estudio).id_estudio_modulo == "MOD-OS-0001"
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
        assert cobertura_de(db.session.get(Estudio, estudio_id)).id_estudio_modulo == "MOD-OS-0001"


# --- respuesta desde el módulo ---


def test_autorizado_al_100_habilita_el_turno_sin_usuario(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-100")
        respuestas["MOD-1"] = _autorizado()

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


def test_autorizado_al_70_pide_la_diferencia(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, codigo="OS-070")
        respuestas["MOD-1"] = _autorizado()

        consultar_respuestas()
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert cobertura_de(estudio).importe_cubierto_usd == Decimal("350.00")


def test_rechazado_pasa_a_rechazado_por_obra_social_con_el_motivo(
    app, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto)
        respuestas["MOD-1"] = _rechazado("El plan no cubre estudios genéticos")

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


def test_pendiente_no_cambia_nada(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto)

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
        respuestas["MOD-2"] = _autorizado()

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
        respuestas["MOD-1"] = _rechazado()

        consulta = consultar_respuestas()

        assert (consulta.autorizadas, consulta.rechazadas, consulta.sin_respuesta) == (0, 0, 0)
        assert cobertura_de(estudio).respondida_por == administrativo.id
        assert _estado(estudio.id) == EstadoEstudio.HABILITADO_TURNO


def test_la_demanda_vuelve_a_dar_de_alta_el_estudio(
    app, client, crear_estudio, crear_presupuesto, respuestas
):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo="MOD-VIEJO")
        rechazar(cobertura_de(estudio), None, "Plan sin cobertura")
        db.session.commit()
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
        assert cobertura.id_estudio_modulo == "MOD-OS-0001"  # alta nueva, no la del rechazo


def test_la_demanda_sin_modulo_borra_el_id_viejo(app, crear_estudio, crear_presupuesto, respuestas):
    with app.app_context():
        estudio = _pedido(crear_estudio, crear_presupuesto, id_modulo="MOD-VIEJO")
        rechazar(cobertura_de(estudio), None)
        db.session.commit()

        cargar_demanda(estudio, estudio.paciente.usuario, PDF)

        # Sin id, la tarea la da de alta otra vez en lugar de leer el rechazo viejo.
        assert cobertura_de(estudio).id_estudio_modulo is None


# --- tarea y pantalla ---


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
    respuestas["MOD-1"] = _autorizado()

    lista = client.get("/coberturas")
    assert "En el módulo: MOD-1" in lista.text
    assert "Sin enviar al módulo" in lista.text

    assert client.post("/coberturas/consultar").status_code == 302
    pagina = client.get("/coberturas")
    assert "1 autorizadas" in pagina.text
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.HABILITADO_TURNO
        cobertura = cobertura_de(db.session.get(Estudio, sin_enviar_id))
        assert cobertura.id_estudio_modulo == "MOD-OS-0001"


def test_el_paciente_no_consulta_el_modulo(login_como):
    assert login_como(roles.PACIENTE).post("/coberturas/consultar").status_code == 403
