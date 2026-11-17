"""E16 Solicitar cobertura, E17 Autorizar cobertura y E18 Solicitar reautorización.

Incluye el pago de la diferencia de una cobertura parcial (supuestos O3 y O18) y los asientos del
registro financiero (E41.3). La API de obras sociales responde con los mocks de
tests/fixtures/apis/obras_sociales/: al 100 %, al 70 % y al 40 %.
"""

from decimal import Decimal
from io import BytesIO

import pytest
import sqlalchemy as sa

from src.core.coberturas import (
    Cobertura,
    DemandaReautorizacion,
    ErrorDeCobertura,
    EstadoCobertura,
    autorizar,
    cargar_demanda,
    cobertura_de,
    diferencia_a_pagar,
    opciones,
    rechazar,
    solicitar,
)
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.finanzas import AsientoFinanciero, Pago, TipoAsiento, TipoPago
from src.core.notificaciones import Aviso
from src.core.obras_sociales import ObraSocial
from src.core.pagos import ErrorDePago, importe_final, pagar_particular, presupuesto_de
from src.core.usuarios import roles
from src.integraciones import obras_sociales as api_de_obras_sociales
from src.integraciones.base import ErrorDeIntegracion

PDF = b"%PDF-1.4 resolucion judicial de prueba"


@pytest.fixture(autouse=True)
def storage_en_tmp(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)


def _presupuestado(crear_estudio, crear_presupuesto, genes=("GAA",)):
    """Estudio Presupuestado. Con un gen, el presupuesto es de 500 USD."""
    estudio = crear_estudio(genes=genes)
    crear_presupuesto(estudio)
    db.session.commit()
    return estudio


def _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070", genes=("GAA",)):
    estudio = _presupuestado(crear_estudio, crear_presupuesto, genes)
    solicitar(estudio, estudio.paciente.usuario, codigo)
    db.session.commit()
    return estudio


def _estado_guardado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _avisos_de(usuario):
    return db.session.scalars(sa.select(Aviso).where(Aviso.usuario_id == usuario.id)).all()


def _ultimo_aviso(usuario):
    consulta = sa.select(Aviso).where(Aviso.usuario_id == usuario.id).order_by(Aviso.id.desc())
    return db.session.scalars(consulta).first()


def _asientos(estudio, tipo):
    consulta = sa.select(AsientoFinanciero).where(
        AsientoFinanciero.estudio_id == estudio.id, AsientoFinanciero.tipo == tipo
    )
    return db.session.scalars(consulta).all()


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


# --- E16.2 Opciones de la API ---


def test_las_opciones_vienen_de_la_api_con_su_porcentaje(app):
    with app.app_context():
        obras = opciones()

    assert [(obra.codigo, obra.porcentaje) for obra in obras] == [
        ("OS-040", Decimal(40)),
        ("OS-070", Decimal(70)),
        ("OS-100", Decimal(100)),
    ]


def test_una_obra_social_que_no_cubre_nada_no_se_ofrece(app, monkeypatch):
    lista = [
        api_de_obras_sociales.ObraSocialEnApi("OS-000", "Sin cobertura", Decimal(0), "id-0"),
        api_de_obras_sociales.ObraSocialEnApi("OS-050", "A medias", Decimal(50), "id-50"),
    ]
    monkeypatch.setattr(api_de_obras_sociales, "listar", lambda cliente=None: lista)

    with app.app_context():
        assert [obra.codigo for obra in opciones()] == ["OS-050"]


# --- E16 Solicitar cobertura ---


def test_solicitar_pasa_a_pendiente_de_autorizacion_y_avisa_a_los_administrativos(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        administrativos = [usuario_rapido(roles.ADMINISTRATIVO) for _ in range(2)]
        estudio = _presupuestado(crear_estudio, crear_presupuesto)
        paciente = estudio.paciente.usuario

        cobertura = solicitar(estudio, paciente, "OS-070")
        db.session.commit()

        assert _estado_guardado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert cobertura.estado == EstadoCobertura.PENDIENTE
        assert cobertura.porcentaje == Decimal(70)  # copiado de la API
        assert db.session.get(ObraSocial, "OS-070").nombre == "Obra Social de Prueba Parcial"
        ultimo = db.session.scalars(
            sa.select(HistorialEstado)
            .where(HistorialEstado.estudio_id == estudio.id)
            .order_by(HistorialEstado.id.desc())
        ).first()
        assert ultimo.usuario_id == paciente.id
        for administrativo in administrativos:
            (aviso,) = _avisos_de(administrativo)
            assert aviso.link == "/coberturas"
            assert "Obra Social de Prueba Parcial" in aviso.mensaje


def test_una_obra_social_que_ya_estaba_se_actualiza_y_no_se_duplica(
    app, crear_estudio, crear_presupuesto
):
    with app.app_context():
        db.session.add(ObraSocial(codigo="OS-070", nombre="Nombre viejo"))
        db.session.commit()

        _pendiente(crear_estudio, crear_presupuesto)

        assert db.session.get(ObraSocial, "OS-070").nombre == "Obra Social de Prueba Parcial"


@pytest.mark.parametrize("estado", [EstadoEstudio.CREADO, EstadoEstudio.HABILITADO_TURNO])
def test_solo_se_solicita_con_el_estudio_presupuestado(app, crear_estudio, estado):
    with app.app_context():
        estudio = crear_estudio(estado)

        with pytest.raises(ErrorDeCobertura, match="Presupuestado"):
            solicitar(estudio, estudio.paciente.usuario, "OS-070")


def test_una_obra_social_que_no_esta_en_la_api_se_rechaza(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDeCobertura, match="de la lista"):
            solicitar(estudio, estudio.paciente.usuario, "OS-999")


def test_un_paciente_no_pide_la_cobertura_de_otro_estudio(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)
        otro = crear_estudio().paciente.usuario

        with pytest.raises(ErrorDeCobertura, match="Solo el paciente"):
            solicitar(estudio, otro, "OS-070")


def test_si_la_api_no_responde_no_cambia_nada(app, crear_estudio, crear_presupuesto, monkeypatch):
    def caida(cliente=None):
        raise ErrorDeIntegracion("La API de obras sociales", "No respondió a tiempo.")

    monkeypatch.setattr(api_de_obras_sociales, "listar", caida)
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDeIntegracion):
            solicitar(estudio, estudio.paciente.usuario, "OS-070")
        db.session.rollback()

        assert _estado_guardado(estudio.id) == EstadoEstudio.PRESUPUESTADO
        assert cobertura_de(estudio) is None


# --- E17 Autorizar cobertura ---


def test_al_100_por_ciento_la_autorizacion_habilita_el_turno(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-100")
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        pago = autorizar(cobertura_de(estudio), administrativo)
        db.session.commit()

        cobertura = cobertura_de(estudio)
        assert cobertura.estado == EstadoCobertura.AUTORIZADA
        assert cobertura.importe_cubierto_usd == Decimal("500.00")
        assert cobertura.respondida_por == administrativo.id
        assert pago.tipo == TipoPago.OBRA_SOCIAL
        assert pago.importe_usd == Decimal("500.00")
        (asiento,) = _asientos(estudio, TipoAsiento.COBERTURA_OBRA_SOCIAL)
        assert asiento.importe_usd == Decimal("500.00")
        assert asiento.obra_social_codigo == "OS-100"
        assert asiento.pago_id == pago.id
        assert _estado_guardado(estudio.id) == EstadoEstudio.HABILITADO_TURNO
        aviso = _ultimo_aviso(estudio.paciente.usuario)
        assert aviso.link == "/turnos/mio"


def test_al_70_por_ciento_falta_pagar_la_diferencia(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070")
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        autorizar(cobertura_de(estudio), administrativo)
        db.session.commit()

        assert cobertura_de(estudio).importe_cubierto_usd == Decimal("350.00")
        # Sigue en Pendiente de autorización hasta que paga la diferencia (O3, O18).
        assert _estado_guardado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        assert diferencia_a_pagar(estudio) == Decimal("150.00")
        assert importe_final(presupuesto_de(estudio)) == Decimal("150.00")
        aviso = _ultimo_aviso(estudio.paciente.usuario)
        assert "150.00 USD" in aviso.mensaje
        assert aviso.link == f"/estudios/{estudio.id}/presupuesto"


def test_pagar_la_diferencia_habilita_el_turno(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070")
        autorizar(cobertura_de(estudio), usuario_rapido(roles.ADMINISTRATIVO))
        db.session.commit()

        pago = pagar_particular(estudio, estudio.paciente.usuario, "150.00")
        db.session.commit()

        assert pago.tipo == TipoPago.PARTICULAR
        assert pago.importe_usd == Decimal("150.00")
        assert _estado_guardado(estudio.id) == EstadoEstudio.HABILITADO_TURNO
        (asiento,) = _asientos(estudio, TipoAsiento.PAGO_PARTICULAR)
        assert asiento.importe_usd == Decimal("150.00")
        assert diferencia_a_pagar(estudio) is None


def test_la_diferencia_no_se_paga_por_el_total_ni_con_cupon(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070")
        autorizar(cobertura_de(estudio), usuario_rapido(roles.ADMINISTRATIVO))
        db.session.commit()
        paciente = estudio.paciente.usuario

        with pytest.raises(ErrorDePago, match="150.00 USD"):
            pagar_particular(estudio, paciente, "500.00")
        with pytest.raises(ErrorDePago, match="no en la diferencia"):
            pagar_particular(estudio, paciente, "150.00", cupon_codigo="TEST0001")


def test_con_la_cobertura_pendiente_no_se_puede_pagar(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDePago, match="Presupuestado"):
            pagar_particular(estudio, estudio.paciente.usuario, "500.00")


def test_el_importe_cubierto_se_redondea_a_centavos(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    genes = ("GAA", "GLA", "GBA", "IDUA", "SMPD1", "HEXA")  # 6 genes: 530 USD
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070", genes=genes)

        pago = autorizar(cobertura_de(estudio), usuario_rapido(roles.ADMINISTRATIVO))

        assert pago.importe_usd == Decimal("371.00")
        assert diferencia_a_pagar(estudio) == Decimal("159.00")


def test_rechazar_pasa_a_rechazado_por_obra_social_y_avisa(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        rechazar(cobertura_de(estudio), administrativo, "No cubre estudios genéticos")
        db.session.commit()

        assert cobertura_de(estudio).estado == EstadoCobertura.RECHAZADA
        assert _estado_guardado(estudio.id) == EstadoEstudio.RECHAZADO_OBRA_SOCIAL
        ultimo = db.session.scalars(
            sa.select(HistorialEstado)
            .where(HistorialEstado.estudio_id == estudio.id)
            .order_by(HistorialEstado.id.desc())
        ).first()
        assert ultimo.motivo == "No cubre estudios genéticos"
        aviso = _ultimo_aviso(estudio.paciente.usuario)
        assert "No cubre estudios genéticos" in aviso.mensaje
        assert aviso.link == f"/estudios/{estudio.id}/reautorizacion"
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Pago)) == 0


def test_solo_un_administrativo_registra_la_respuesta(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDeCobertura, match="administrativo"):
            autorizar(cobertura_de(estudio), estudio.paciente.usuario)


def test_una_cobertura_ya_respondida_no_se_vuelve_a_responder(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        autorizar(cobertura_de(estudio), administrativo)

        with pytest.raises(ErrorDeCobertura, match="no está esperando"):
            rechazar(cobertura_de(estudio), administrativo)


# --- E18 Solicitar reautorización ---


def _rechazado(crear_estudio, crear_presupuesto, usuario_rapido):
    estudio = _pendiente(crear_estudio, crear_presupuesto)
    administrativo = usuario_rapido(roles.ADMINISTRATIVO)
    db.session.flush()
    rechazar(cobertura_de(estudio), administrativo)
    db.session.commit()
    return estudio


def test_la_demanda_vuelve_a_pendiente_de_autorizacion_y_avisa(
    app, crear_estudio, crear_presupuesto, usuario_rapido, tmp_path
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto, usuario_rapido)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        demanda = cargar_demanda(estudio, estudio.paciente.usuario, PDF)
        db.session.commit()

        assert (tmp_path / demanda.resolucion_path).read_bytes() == PDF
        assert cobertura_de(estudio).estado == EstadoCobertura.PENDIENTE
        assert _estado_guardado(estudio.id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        (aviso,) = _avisos_de(administrativo)
        assert aviso.asunto == "Reautorización pendiente"


def test_despues_de_la_demanda_el_administrativo_autoriza(
    app, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto, usuario_rapido)
        cargar_demanda(estudio, estudio.paciente.usuario, PDF)

        autorizar(cobertura_de(estudio), usuario_rapido(roles.ADMINISTRATIVO))

        assert cobertura_de(estudio).estado == EstadoCobertura.AUTORIZADA


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        pytest.param(b"", "en PDF", id="sin archivo"),
        pytest.param(b"no es un pdf", "en PDF", id="otro tipo"),
        pytest.param(b"%PDF" + b"x" * (5 * 1024 * 1024), "5 MB", id="muy grande"),
    ],
)
def test_la_demanda_exige_un_pdf_de_hasta_5_mb(
    app, crear_estudio, crear_presupuesto, usuario_rapido, contenido, mensaje
):
    with app.app_context():
        estudio = _rechazado(crear_estudio, crear_presupuesto, usuario_rapido)

        with pytest.raises(ErrorDeCobertura, match=mensaje):
            cargar_demanda(estudio, estudio.paciente.usuario, contenido)


def test_la_demanda_solo_se_carga_con_el_estudio_rechazado(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDeCobertura, match="rechazó"):
            cargar_demanda(estudio, estudio.paciente.usuario, PDF)
        assert db.session.scalar(sa.select(sa.func.count()).select_from(DemandaReautorizacion)) == 0


# --- Pantallas ---


def test_el_paciente_elige_su_obra_social_desde_el_presupuesto(
    app, client, crear_estudio, crear_presupuesto
):
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario)

    assert "Usar mi obra social" in client.get(f"/estudios/{estudio_id}/presupuesto").text
    eleccion = client.get(f"/estudios/{estudio_id}/cobertura")
    assert eleccion.status_code == 200
    assert "Obra Social de Prueba Parcial" in eleccion.text
    assert "350.00 USD" in eleccion.text  # lo que cubriría el 70 % de 500

    respuesta = client.post(f"/estudios/{estudio_id}/cobertura", data={"codigo": "OS-070"})

    assert respuesta.status_code == 302
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.PENDIENTE_AUTORIZACION
    assert (
        "le está pidiendo la autorización" in client.get(f"/estudios/{estudio_id}/presupuesto").text
    )


def test_si_la_api_esta_caida_la_pantalla_lo_avisa(
    app, client, crear_estudio, crear_presupuesto, monkeypatch
):
    def caida(cliente=None):
        raise ErrorDeIntegracion(
            "La API de obras sociales", "La API de obras sociales no respondió."
        )

    monkeypatch.setattr(api_de_obras_sociales, "listar", caida)
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.get(f"/estudios/{estudio_id}/cobertura")

    assert respuesta.status_code == 503
    assert "no respondió" in respuesta.text


def test_el_administrativo_autoriza_y_el_paciente_paga_la_diferencia(
    app, client, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto, codigo="OS-070")
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.commit()
        estudio_id, cobertura_id = estudio.id, cobertura_de(estudio).id
        paciente = estudio.paciente.usuario
        _entrar_como(client, administrativo)

    lista = client.get("/coberturas")
    assert lista.status_code == 200
    assert "Obra Social de Prueba Parcial" in lista.text
    assert client.post(f"/coberturas/{cobertura_id}/autorizar").status_code == 302

    with app.app_context():
        _entrar_como(client, paciente)
    presupuesto = client.get(f"/estudios/{estudio_id}/presupuesto")
    assert "Falta que pagues la diferencia" in presupuesto.text
    pago = client.get(f"/estudios/{estudio_id}/pago")
    assert "Cubre tu obra social" in pago.text
    assert "¿Tenés un cupón de descuento?" not in pago.text
    assert (
        client.post(f"/estudios/{estudio_id}/pago", data={"importe": "150.00"}).status_code == 302
    )
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.HABILITADO_TURNO


def test_el_administrativo_rechaza_y_el_paciente_sube_la_resolucion(
    app, client, crear_estudio, crear_presupuesto, usuario_rapido
):
    with app.app_context():
        estudio = _pendiente(crear_estudio, crear_presupuesto)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.commit()
        estudio_id, cobertura_id = estudio.id, cobertura_de(estudio).id
        paciente = estudio.paciente.usuario
        _entrar_como(client, administrativo)

    client.post(f"/coberturas/{cobertura_id}/rechazar", data={"motivo": "Plan sin cobertura"})

    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.RECHAZADO_OBRA_SOCIAL
        _entrar_como(client, paciente)
    assert "pedir la reautorización" in client.get(f"/estudios/{estudio_id}/presupuesto").text
    respuesta = client.post(
        f"/estudios/{estudio_id}/reautorizacion",
        data={"resolucion": (BytesIO(PDF), "resolucion.pdf")},
        content_type="multipart/form-data",
    )

    assert respuesta.status_code == 302
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.PENDIENTE_AUTORIZACION
        _entrar_como(client, administrativo)
    lista = client.get("/coberturas")
    assert "Reautorización" in lista.text
    descarga = client.get(f"/coberturas/{cobertura_id}/resolucion.pdf")
    assert descarga.status_code == 200
    assert descarga.data == PDF


def test_un_paciente_no_entra_a_la_cobertura_de_otro(app, client, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio = _presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, crear_estudio().paciente.usuario)

    assert client.get(f"/estudios/{estudio_id}/cobertura").status_code == 404
    assert (
        client.post(f"/estudios/{estudio_id}/cobertura", data={"codigo": "OS-070"}).status_code
        == 404
    )
    assert client.get(f"/estudios/{estudio_id}/reautorizacion").status_code == 404


def test_el_paciente_no_entra_a_la_lista_de_coberturas(login_como):
    assert login_como(roles.PACIENTE).get("/coberturas").status_code == 403


def test_el_administrativo_no_pide_coberturas(
    app, client, crear_estudio, crear_presupuesto, login_como
):
    with app.app_context():
        estudio_id = _presupuestado(crear_estudio, crear_presupuesto).id
    cliente = login_como(roles.ADMINISTRATIVO)

    assert cliente.get(f"/estudios/{estudio_id}/cobertura").status_code == 403


def test_el_menu_del_administrativo_tiene_coberturas(login_como):
    assert "Coberturas" in login_como(roles.ADMINISTRATIVO).get("/").text


# --- flask demo ---


def test_demo_pendiente_de_autorizacion_y_rechazado_por_obra_social(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seeds"]).exit_code == 0

    pendiente = runner.invoke(args=["demo", "pendiente_autorizacion"])
    rechazado = runner.invoke(args=["demo", "rechazado_obra_social"])

    assert pendiente.exit_code == 0, pendiente.output
    assert rechazado.exit_code == 0, rechazado.output
    with app.app_context():
        estados = db.session.scalars(sa.select(Cobertura.estado).order_by(Cobertura.id)).all()
        assert estados == [EstadoCobertura.PENDIENTE, EstadoCobertura.RECHAZADA]
