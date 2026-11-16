"""E37 Generar cupón, E38 Asignar cupón y E15 Aplicar cupón: reglas, transacción y permisos."""

import io
from decimal import Decimal

import pytest
import sqlalchemy as sa
from reportlab.pdfgen import canvas

from src.core.cupones import (
    Cupon,
    ErrorDeCupon,
    EstadoCupon,
    asignar_a_paciente,
    codigo_desde_pdf,
    cupones_del_paciente,
    cupones_disponibles,
    generar_cupones,
    resolver_cupon,
)
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio
from src.core.finanzas import AsientoFinanciero, Pago, TipoAsiento, deuda_por_paciente
from src.core.notificaciones import Aviso
from src.core.pagos import ErrorDePago, pagar_particular
from src.core.usuarios import crear_perfil_medico, roles
from src.integraciones import cupones as modulo_de_cupones
from src.integraciones.base import ErrorDeIntegracion


@pytest.fixture(autouse=True)
def storage_en_disco(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)
    return tmp_path


def _medico(usuario_rapido, numero=1):
    medico = usuario_rapido(roles.MEDICO_TRATANTE)
    crear_perfil_medico(medico, f"MP-CUPON-{medico.email}")
    db.session.flush()
    return medico


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


def _avisos(usuario):
    return db.session.scalars(sa.select(Aviso).where(Aviso.usuario_id == usuario.id)).all()


def _escenario(crear_estudio, crear_presupuesto, crear_cupon, codigo=None, porcentaje=20):
    """Estudio Presupuestado de 500 USD con un cupón de su médico asignado a su paciente."""
    estudio = crear_estudio()
    crear_presupuesto(estudio)
    medico = estudio.paciente.medico_tratante.usuario
    cupon = crear_cupon(medico, codigo=codigo, porcentaje=porcentaje, paciente=estudio.paciente)
    db.session.commit()
    return estudio, medico, cupon


def _pdf_con_texto(texto: str) -> bytes:
    salida = io.BytesIO()
    lienzo = canvas.Canvas(salida)
    if texto:
        lienzo.drawString(72, 760, texto)
    lienzo.save()
    return salida.getvalue()


# --- E37 generar ---


def test_generar_tres_cupones_los_asigna_al_medico_guarda_los_pdf_y_avisa(
    app, usuario_rapido, storage_en_disco
):
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.flush()

        cupones = generar_cupones(gerente, medico, "25", "3")
        db.session.commit()

        assert len(cupones) == 3
        for cupon in cupones:
            assert cupon.medico_tratante_id == medico.id
            assert cupon.generado_por == gerente.id
            assert cupon.descuento_porcentaje == Decimal(20)  # el que devuelve el módulo
            assert cupon.estado == EstadoCupon.VIGENTE
            assert cupon.paciente_id is None
            pdf = (storage_en_disco / cupon.pdf_path).read_bytes()
            assert pdf.startswith(b"%PDF")
            assert codigo_desde_pdf(pdf) == cupon.codigo
        avisos = _avisos(medico)
        assert len(avisos) == 1
        assert avisos[0].link == "/cupones/mios"


@pytest.mark.parametrize(
    ("porcentaje", "cantidad"),
    [
        ("0", "1"),
        ("101", "1"),
        ("-5", "1"),
        ("abc", "1"),
        ("10.555", "1"),
        ("20", "0"),
        ("20", "x"),
    ],
)
def test_generar_con_datos_invalidos_falla_y_no_guarda_nada(
    app, usuario_rapido, porcentaje, cantidad
):
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.flush()

        with pytest.raises(ErrorDeCupon):
            generar_cupones(gerente, medico, porcentaje, cantidad)

        assert db.session.scalars(sa.select(Cupon)).all() == []


@pytest.mark.parametrize("porcentaje", ["1", "100", "12.5"])
def test_generar_acepta_porcentajes_de_1_a_100(app, usuario_rapido, porcentaje):
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.flush()

        cupones = generar_cupones(gerente, medico, porcentaje, 1)

        assert len(cupones) == 1


def test_solo_el_gerente_medico_genera_y_solo_para_un_medico_tratante(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        db.session.flush()

        with pytest.raises(ErrorDeCupon, match="gerente médico"):
            generar_cupones(medico, medico, 10, 1)
        with pytest.raises(ErrorDeCupon, match="médico tratante"):
            generar_cupones(gerente, gerente, 10, 1)
        with pytest.raises(ErrorDeCupon, match="médico tratante"):
            generar_cupones(gerente, None, 10, 1)


def test_generar_con_el_modulo_caido_no_guarda_nada(app, client, usuario_rapido, monkeypatch):
    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("Cupones", "Cupones no respondió a tiempo.")

    monkeypatch.setattr(modulo_de_cupones, "generar", caido)
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.commit()
        _entrar_como(client, gerente)

        respuesta = client.post(
            "/cupones/generar", data={"porcentaje": "20", "cantidad": "2", "medico_id": medico.id}
        )

        assert respuesta.status_code == 503
        assert "Cupones no respondió a tiempo" in respuesta.get_data(as_text=True)
        assert db.session.scalars(sa.select(Cupon)).all() == []
        assert _avisos(medico) == []


def test_el_gerente_genera_desde_la_pantalla(app, client, usuario_rapido):
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.commit()
        _entrar_como(client, gerente)

        assert client.get("/cupones/generar").status_code == 200
        respuesta = client.post(
            "/cupones/generar", data={"porcentaje": "30", "cantidad": "2", "medico_id": medico.id}
        )

        assert respuesta.status_code == 302
        assert len(db.session.scalars(sa.select(Cupon)).all()) == 2
        assert "CUP73920001" in client.get("/cupones").get_data(as_text=True)


def test_pantalla_de_generar_con_datos_invalidos_responde_400(app, client, usuario_rapido):
    with app.app_context():
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        medico = _medico(usuario_rapido)
        db.session.commit()
        _entrar_como(client, gerente)

        respuesta = client.post(
            "/cupones/generar", data={"porcentaje": "150", "cantidad": "2", "medico_id": medico.id}
        )

        assert respuesta.status_code == 400
        assert "entre 1 y 100" in respuesta.get_data(as_text=True)
        assert db.session.scalars(sa.select(Cupon)).all() == []


# --- E38 asignar ---


def test_asignar_a_un_paciente_propio_avisa_y_lo_deja_en_su_vista(app, crear_paciente, crear_cupon):
    with app.app_context():
        paciente = crear_paciente()
        medico = paciente.medico_tratante.usuario
        cupon = crear_cupon(medico)
        db.session.commit()
        assert cupon in cupones_disponibles(medico)

        asignar_a_paciente(medico, cupon.id, paciente.id)
        db.session.commit()

        assert cupon.paciente_id == paciente.id
        assert cupon.asignado_a_paciente_en is not None
        assert cupon not in cupones_disponibles(medico)
        assert cupones_del_paciente(paciente.usuario) == [cupon]
        avisos = _avisos(paciente.usuario)
        assert len(avisos) == 1
        assert avisos[0].link == "/cupones/mios"


def test_asignar_a_un_paciente_de_otro_medico_falla(app, crear_paciente, crear_cupon):
    with app.app_context():
        mio, ajeno = crear_paciente(), crear_paciente()
        cupon = crear_cupon(mio.medico_tratante.usuario)
        db.session.commit()

        with pytest.raises(ErrorDeCupon, match="paciente no es tuyo"):
            asignar_a_paciente(mio.medico_tratante.usuario, cupon.id, ajeno.id)

        assert cupon.paciente_id is None
        assert _avisos(ajeno.usuario) == []


def test_asignar_un_cupon_de_otro_medico_ya_asignado_o_utilizado_falla(
    app, crear_paciente, crear_cupon
):
    with app.app_context():
        paciente, otro = crear_paciente(), crear_paciente()
        medico = paciente.medico_tratante.usuario
        ajeno = crear_cupon(otro.medico_tratante.usuario)
        asignado = crear_cupon(medico, paciente=paciente)
        usado = crear_cupon(medico, estado=EstadoCupon.UTILIZADO)
        db.session.commit()

        with pytest.raises(ErrorDeCupon, match="entre tus cupones"):
            asignar_a_paciente(medico, ajeno.id, paciente.id)
        with pytest.raises(ErrorDeCupon, match="ya está asignado"):
            asignar_a_paciente(medico, asignado.id, paciente.id)
        with pytest.raises(ErrorDeCupon, match="ya no está vigente"):
            asignar_a_paciente(medico, usado.id, paciente.id)
        with pytest.raises(ErrorDeCupon, match="entre tus cupones"):
            asignar_a_paciente(medico, 999999, paciente.id)

        assert ajeno.paciente_id is None


def test_el_modulo_rechaza_un_paciente_que_ya_tuvo_un_cupon(app, crear_paciente, crear_cupon):
    with app.app_context():
        paciente = crear_paciente()
        medico = paciente.medico_tratante.usuario
        cupon = crear_cupon(medico, codigo="YACANJE1")
        db.session.commit()

        with pytest.raises(ErrorDeCupon, match="uno por paciente"):
            asignar_a_paciente(medico, cupon.id, paciente.id)

        assert cupon.paciente_id is None
        assert _avisos(paciente.usuario) == []


def test_el_medico_asigna_desde_su_pantalla(app, client, crear_paciente, crear_cupon):
    with app.app_context():
        paciente = crear_paciente()
        medico = paciente.medico_tratante.usuario
        cupon = crear_cupon(medico)
        db.session.commit()
        _entrar_como(client, medico)

        assert paciente.dni in client.get("/cupones/mios").get_data(as_text=True)
        respuesta = client.post(f"/cupones/{cupon.id}/asignar", data={"paciente_id": paciente.id})

        assert respuesta.status_code == 302
        db.session.expire_all()
        assert db.session.get(Cupon, cupon.id).paciente_id == paciente.id

        _entrar_como(client, paciente.usuario)
        assert cupon.codigo in client.get("/cupones/mios").get_data(as_text=True)


def test_el_medico_no_asigna_a_un_paciente_ajeno_desde_la_pantalla(
    app, client, crear_paciente, crear_cupon
):
    with app.app_context():
        mio, ajeno = crear_paciente(), crear_paciente()
        medico = mio.medico_tratante.usuario
        cupon = crear_cupon(medico)
        db.session.commit()
        _entrar_como(client, medico)

        client.post(f"/cupones/{cupon.id}/asignar", data={"paciente_id": ajeno.id})

        db.session.expire_all()
        assert db.session.get(Cupon, cupon.id).paciente_id is None


# --- E15 aplicar y pagar ---


def test_aplicar_un_cupon_vigente_muestra_el_importe_con_descuento(
    app, client, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, cupon = _escenario(crear_estudio, crear_presupuesto, crear_cupon)
        _entrar_como(client, estudio.paciente.usuario)

        respuesta = client.post(f"/estudios/{estudio.id}/pago/cupon", data={"codigo": cupon.codigo})

        html = respuesta.get_data(as_text=True)
        assert respuesta.status_code == 200
        assert "400.00 USD" in html
        assert "−100.00 USD" in html
        assert db.session.scalars(sa.select(Pago)).all() == []


def test_un_cupon_vencido_segun_el_modulo_se_rechaza_con_mensaje(
    app, client, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, _ = _escenario(crear_estudio, crear_presupuesto, crear_cupon, "VENCIDO01")
        _entrar_como(client, estudio.paciente.usuario)

        respuesta = client.post(f"/estudios/{estudio.id}/pago/cupon", data={"codigo": "VENCIDO01"})

        assert respuesta.status_code == 400
        assert "ya fue utilizado" in respuesta.get_data(as_text=True)
        with pytest.raises(ErrorDePago, match="ya fue utilizado"):
            pagar_particular(estudio, estudio.paciente.usuario, "400.00", "VENCIDO01")


def test_un_cupon_que_vencio_o_no_esta_asignado_en_el_modulo_se_rechaza(
    app, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, medico, _ = _escenario(crear_estudio, crear_presupuesto, crear_cupon, "EXPIRADO1")
        sin_asignar = crear_cupon(medico, codigo="SINPACIE1", paciente=estudio.paciente)
        db.session.commit()
        paciente = estudio.paciente.usuario

        with pytest.raises(ErrorDeCupon, match="venció el 01/01/2020"):
            resolver_cupon(paciente, "EXPIRADO1")
        with pytest.raises(ErrorDeCupon, match="no está asignado"):
            resolver_cupon(paciente, sin_asignar.codigo)


def test_un_cupon_de_otro_paciente_o_inexistente_se_rechaza(
    app, crear_estudio, crear_presupuesto, crear_cupon, crear_paciente
):
    with app.app_context():
        estudio, medico, _ = _escenario(crear_estudio, crear_presupuesto, crear_cupon)
        otro = crear_paciente()
        ajeno = crear_cupon(otro.medico_tratante.usuario, paciente=otro)
        sin_paciente = crear_cupon(medico)
        db.session.commit()
        paciente = estudio.paciente.usuario

        for codigo in (ajeno.codigo, sin_paciente.codigo, "NOEXISTE", ""):
            with pytest.raises(ErrorDeCupon):
                resolver_cupon(paciente, codigo)
        with pytest.raises(ErrorDePago, match="no está asignado a tu cuenta"):
            pagar_particular(estudio, paciente, "400.00", ajeno.codigo)
        assert ajeno.estado == EstadoCupon.VIGENTE


def test_pagar_con_cupon_registra_descuento_asientos_vence_y_habilita(
    app, crear_estudio, crear_presupuesto, crear_cupon, monkeypatch
):
    llamadas = []
    original = modulo_de_cupones.canjear

    def espia(paciente_id, codigo):
        llamadas.append((paciente_id, codigo))
        return original(paciente_id, codigo)

    monkeypatch.setattr(modulo_de_cupones, "canjear", espia)
    with app.app_context():
        estudio, _, cupon = _escenario(crear_estudio, crear_presupuesto, crear_cupon)

        pago = pagar_particular(estudio, estudio.paciente.usuario, "400.00", cupon.codigo)
        db.session.commit()

        assert (pago.importe_usd, pago.descuento_usd, pago.cupon_id) == (
            Decimal("400.00"),
            Decimal("100.00"),
            cupon.id,
        )
        asientos = {
            a.tipo: a
            for a in db.session.scalars(
                sa.select(AsientoFinanciero).where(AsientoFinanciero.estudio_id == estudio.id)
            )
        }
        assert asientos[TipoAsiento.PAGO_PARTICULAR].importe_usd == Decimal("400.00")
        assert asientos[TipoAsiento.DESCUENTO_CUPON].importe_usd == Decimal("100.00")
        assert asientos[TipoAsiento.DESCUENTO_CUPON].pago_id == pago.id
        assert cupon.estado == EstadoCupon.UTILIZADO
        assert cupon.utilizado_en is not None
        assert llamadas == [(estudio.paciente.id, cupon.codigo)]
        assert estudio.estado == EstadoEstudio.HABILITADO_TURNO
        assert deuda_por_paciente() == []


def test_pagar_con_cupon_exige_el_importe_con_descuento(
    app, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, cupon = _escenario(crear_estudio, crear_presupuesto, crear_cupon)

        with pytest.raises(ErrorDePago, match="400.00"):
            pagar_particular(estudio, estudio.paciente.usuario, "500.00", cupon.codigo)

        assert cupon.estado == EstadoCupon.VIGENTE
        assert db.session.scalars(sa.select(Pago)).all() == []


def test_un_cupon_del_100_por_ciento_no_se_puede_usar_todavia(
    app, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, cupon = _escenario(
            crear_estudio, crear_presupuesto, crear_cupon, porcentaje=100
        )

        with pytest.raises(ErrorDePago, match="cubre todo el importe"):
            pagar_particular(estudio, estudio.paciente.usuario, "0.00", cupon.codigo)


def test_si_el_modulo_cae_al_vencer_no_hay_pago(
    app, client, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, cupon = _escenario(
            crear_estudio, crear_presupuesto, crear_cupon, codigo="CAIDO001"
        )
        _entrar_como(client, estudio.paciente.usuario)

        respuesta = client.post(
            f"/estudios/{estudio.id}/pago",
            data={"importe": "400.00", "cupon_codigo": "CAIDO001"},
        )

        assert respuesta.status_code == 503
        db.session.expire_all()
        assert db.session.scalars(sa.select(Pago)).all() == []
        asientos = db.session.scalars(
            sa.select(AsientoFinanciero.tipo).where(AsientoFinanciero.estudio_id == estudio.id)
        ).all()
        assert asientos == [TipoAsiento.PRESUPUESTO_EMITIDO]
        assert db.session.get(Cupon, cupon.id).estado == EstadoCupon.VIGENTE
        assert db.session.get(Estudio, estudio.id).estado == EstadoEstudio.PRESUPUESTADO


def test_un_segundo_uso_del_cupon_se_rechaza(app, crear_estudio, crear_presupuesto, crear_cupon):
    with app.app_context():
        estudio, _, cupon = _escenario(crear_estudio, crear_presupuesto, crear_cupon)
        paciente = estudio.paciente.usuario
        pagar_particular(estudio, paciente, "400.00", cupon.codigo)
        db.session.commit()

        with pytest.raises(ErrorDeCupon, match="ya fue utilizado"):
            resolver_cupon(paciente, cupon.codigo)
        with pytest.raises(ErrorDePago):
            pagar_particular(estudio, paciente, "400.00", cupon.codigo)
        assert len(db.session.scalars(sa.select(Pago)).all()) == 1


def test_el_paciente_paga_con_cupon_desde_la_pantalla(
    app, client, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, cupon = _escenario(crear_estudio, crear_presupuesto, crear_cupon)
        _entrar_como(client, estudio.paciente.usuario)

        respuesta = client.post(
            f"/estudios/{estudio.id}/pago",
            data={"importe": "400.00", "cupon_codigo": cupon.codigo},
        )

        assert respuesta.status_code == 302
        db.session.expire_all()
        pago = db.session.scalars(sa.select(Pago)).one()
        assert pago.cupon_id == cupon.id
        assert db.session.get(Estudio, estudio.id).estado == EstadoEstudio.HABILITADO_TURNO


# --- G7 PDF ---


def test_el_codigo_se_lee_del_texto_del_pdf(app, crear_estudio, crear_presupuesto, crear_cupon):
    with app.app_context():
        _escenario(crear_estudio, crear_presupuesto, crear_cupon, codigo="ABC12345")

        pdf = _pdf_con_texto("Cupon de descuento. Codigo: ABC12345")

        assert codigo_desde_pdf(pdf) == "ABC12345"


@pytest.mark.parametrize(
    "contenido", [_pdf_con_texto(""), _pdf_con_texto("Codigo: ZZZ99999"), b"no es un pdf"]
)
def test_si_no_se_puede_leer_el_codigo_se_pide_escribirlo(app, contenido):
    with app.app_context(), pytest.raises(ErrorDeCupon, match="a mano|Escribilo"):
        codigo_desde_pdf(contenido)


def test_el_paciente_sube_el_pdf_y_se_aplica_el_cupon(
    app, client, crear_estudio, crear_presupuesto, crear_cupon
):
    with app.app_context():
        estudio, _, _ = _escenario(crear_estudio, crear_presupuesto, crear_cupon, "PDF00001")
        _entrar_como(client, estudio.paciente.usuario)

        respuesta = client.post(
            f"/estudios/{estudio.id}/pago/cupon",
            data={"pdf": (io.BytesIO(_pdf_con_texto("Codigo: PDF00001")), "cupon.pdf")},
            content_type="multipart/form-data",
        )

        assert respuesta.status_code == 200
        assert "400.00 USD" in respuesta.get_data(as_text=True)


# --- permisos ---


def test_los_roles_sin_permiso_reciben_403(
    app, client, usuario_rapido, crear_paciente, crear_cupon
):
    with app.app_context():
        paciente = crear_paciente()
        medico = paciente.medico_tratante.usuario
        cupon = crear_cupon(medico)
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        db.session.commit()

        _entrar_como(client, medico)
        assert client.get("/cupones/generar").status_code == 403
        assert client.post("/cupones/generar", data={}).status_code == 403
        assert client.get("/cupones").status_code == 403

        _entrar_como(client, paciente.usuario)
        assert client.get("/cupones/generar").status_code == 403
        assert client.post(f"/cupones/{cupon.id}/asignar", data={}).status_code == 403

        _entrar_como(client, gerente)
        assert client.get("/cupones/mios").status_code == 403
        assert client.post(f"/cupones/{cupon.id}/asignar", data={}).status_code == 403


def test_sin_sesion_redirige_al_login(client):
    assert client.get("/cupones/mios").status_code == 302
    assert client.post("/cupones/1/asignar").status_code == 302


def test_el_pdf_solo_lo_baja_quien_lo_genero_lo_recibio_o_lo_tiene(
    app, client, crear_paciente, crear_cupon, storage_en_disco
):
    with app.app_context():
        paciente, otro = crear_paciente(), crear_paciente()
        medico = paciente.medico_tratante.usuario
        cupon = crear_cupon(medico, paciente=paciente)
        db.session.commit()
        (storage_en_disco / "cupones").mkdir()
        (storage_en_disco / cupon.pdf_path).write_bytes(b"%PDF-1.4 cupon")

        _entrar_como(client, medico)
        assert client.get(f"/cupones/{cupon.id}/pdf").data == b"%PDF-1.4 cupon"
        _entrar_como(client, paciente.usuario)
        assert client.get(f"/cupones/{cupon.id}/pdf").status_code == 200
        _entrar_como(client, otro.usuario)
        assert client.get(f"/cupones/{cupon.id}/pdf").status_code == 404
        _entrar_como(client, otro.medico_tratante.usuario)
        assert client.get(f"/cupones/{cupon.id}/pdf").status_code == 404
