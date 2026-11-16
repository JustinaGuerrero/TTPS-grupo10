"""E13 Emitir presupuesto y E14 Pagar estudio: importes, reglas, transacción y permisos."""

from decimal import Decimal

import pytest
import sqlalchemy as sa

from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.finanzas import AsientoFinanciero, Pago, TipoAsiento
from src.core.notificaciones import Aviso
from src.core.pagos import (
    ErrorDePago,
    Presupuesto,
    calcular_importe,
    emitir_presupuesto,
    pagar_particular,
)
from src.core.usuarios import roles

GENES = ("GAA", "GBA", "GLA", "IDUA", "SMPD1", "HEXA", "HEXB", "NPC1", "NPC2", "CTSA")


def _asientos(estudio, tipo=None):
    consulta = sa.select(AsientoFinanciero).where(AsientoFinanciero.estudio_id == estudio.id)
    if tipo:
        consulta = consulta.where(AsientoFinanciero.tipo == tipo)
    return db.session.scalars(consulta).all()


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


def _estado_guardado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _estudio_presupuestado(crear_estudio, crear_presupuesto, genes=("GAA",)):
    estudio = crear_estudio(genes=genes)
    presupuesto = crear_presupuesto(estudio)
    return estudio, presupuesto


# --- calcular_importe ---


@pytest.mark.parametrize(
    ("genes", "importe"), [(1, "500.00"), (5, "500.00"), (6, "530.00"), (10, "650.00")]
)
def test_importe_segun_la_cantidad_de_genes(genes, importe):
    assert calcular_importe(genes) == Decimal(importe)


def test_importe_sin_genes_falla():
    with pytest.raises(ValueError):
        calcular_importe(0)


# --- E13 emitir ---


@pytest.mark.parametrize(
    ("cantidad", "total"), [(1, "500.00"), (5, "500.00"), (6, "530.00"), (10, "650.00")]
)
def test_emitir_presupuesto_calcula_cambia_estado_registra_asiento_y_avisa(
    app, crear_estudio, usuario_rapido, cantidad, total
):
    with app.app_context():
        estudio = crear_estudio(genes=GENES[:cantidad])
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        presupuesto = emitir_presupuesto(estudio, administrativo)
        db.session.commit()

        assert presupuesto.cantidad_genes == cantidad
        assert presupuesto.total_usd == Decimal(total)
        assert presupuesto.emitido_por == administrativo.id
        assert estudio.estado == EstadoEstudio.PRESUPUESTADO
        asientos = _asientos(estudio)
        assert [a.tipo for a in asientos] == [TipoAsiento.PRESUPUESTO_EMITIDO]
        assert asientos[0].importe_usd == Decimal(total)
        aviso = db.session.scalars(
            sa.select(Aviso).where(Aviso.usuario_id == estudio.paciente.usuario_id)
        ).one()
        assert aviso.estudio_id == estudio.id
        assert aviso.link == f"/estudios/{estudio.id}/presupuesto"
        ultimo = estudio.historial[-1]
        assert (ultimo.estado_anterior, ultimo.estado_nuevo, ultimo.usuario_id) == (
            EstadoEstudio.CREADO,
            EstadoEstudio.PRESUPUESTADO,
            administrativo.id,
        )


def test_los_genes_a_mano_cuentan_y_los_hallazgos_secundarios_no(
    app, crear_estudio, usuario_rapido
):
    """O13: los genes ACMG no se guardan, así que no suman; los agregados a mano sí."""
    with app.app_context():
        estudio = crear_estudio(
            genes=GENES[:5], genes_agregados_a_mano=("ABCD1",), evalua_hallazgos_secundarios=True
        )
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        assert emitir_presupuesto(estudio, administrativo).total_usd == Decimal("530.00")


def test_emitir_dos_veces_falla_y_no_duplica(app, crear_estudio, usuario_rapido):
    with app.app_context():
        estudio = crear_estudio()
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()
        emitir_presupuesto(estudio, administrativo)
        db.session.commit()

        with pytest.raises(ErrorDePago, match="ya tiene presupuesto"):
            emitir_presupuesto(estudio, administrativo)

        assert len(db.session.scalars(sa.select(Presupuesto)).all()) == 1
        assert len(_asientos(estudio)) == 1


def test_emitir_con_estudio_que_no_esta_en_creado_falla(app, crear_estudio, usuario_rapido):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.HABILITADO_TURNO)
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        with pytest.raises(ErrorDePago, match="Creado"):
            emitir_presupuesto(estudio, administrativo)

        assert estudio.estado == EstadoEstudio.HABILITADO_TURNO
        assert _asientos(estudio) == []


def test_solo_el_administrativo_emite(app, crear_estudio, usuario_rapido):
    with app.app_context():
        estudio = crear_estudio()
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        with pytest.raises(ErrorDePago, match="administrativo"):
            emitir_presupuesto(estudio, medico)

        assert estudio.estado == EstadoEstudio.CREADO


def test_la_base_rechaza_un_presupuesto_con_total_cero(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        presupuesto = crear_presupuesto(crear_estudio())
        presupuesto.total_usd = Decimal(0)
        with pytest.raises(sa.exc.IntegrityError):
            db.session.flush()
        db.session.rollback()


# --- E14 pagar ---


def test_pagar_crea_pago_y_asiento_habilita_turno_y_avisa(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio, presupuesto = _estudio_presupuestado(crear_estudio, crear_presupuesto, GENES[:6])
        paciente = estudio.paciente.usuario

        pago = pagar_particular(estudio, paciente, "530.00")
        db.session.commit()

        assert pago.tipo == "particular"
        assert pago.importe_usd == Decimal("530.00")
        assert pago.cupon_id is None
        assert estudio.estado == EstadoEstudio.HABILITADO_TURNO
        asiento = _asientos(estudio, TipoAsiento.PAGO_PARTICULAR)[0]
        assert asiento.pago_id == pago.id
        assert asiento.importe_usd == presupuesto.total_usd
        asuntos = db.session.scalars(
            sa.select(Aviso.asunto).where(Aviso.usuario_id == paciente.id)
        ).all()
        assert "Pago registrado" in asuntos


@pytest.mark.parametrize("importe", ["499.99", "500.01", "250", "0", "abc", ""])
def test_importe_distinto_al_final_se_rechaza_y_no_cambia_nada(
    app, crear_estudio, crear_presupuesto, importe
):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)

        with pytest.raises(ErrorDePago):
            pagar_particular(estudio, estudio.paciente.usuario, importe)

        assert estudio.estado == EstadoEstudio.PRESUPUESTADO
        assert db.session.scalars(sa.select(Pago)).all() == []
        assert _asientos(estudio, TipoAsiento.PAGO_PARTICULAR) == []


def test_pagar_dos_veces_falla(app, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        pagar_particular(estudio, estudio.paciente.usuario, "500")
        db.session.commit()

        with pytest.raises(ErrorDePago):
            pagar_particular(estudio, estudio.paciente.usuario, "500")

        assert len(db.session.scalars(sa.select(Pago)).all()) == 1


@pytest.mark.parametrize("estado", [EstadoEstudio.CREADO, EstadoEstudio.HABILITADO_TURNO])
def test_pagar_con_estado_invalido_falla(app, crear_estudio, estado):
    with app.app_context():
        estudio = crear_estudio(estado=estado)

        with pytest.raises(ErrorDePago, match="Presupuestado"):
            pagar_particular(estudio, estudio.paciente.usuario, "500")

        assert estudio.estado == estado


def test_un_paciente_ajeno_no_paga(app, crear_estudio, crear_presupuesto, crear_paciente):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        otro = crear_paciente().usuario
        db.session.flush()

        with pytest.raises(ErrorDePago, match="paciente del estudio"):
            pagar_particular(estudio, otro, "500")

        assert estudio.estado == EstadoEstudio.PRESUPUESTADO


def test_si_falla_el_cambio_de_estado_no_quedan_ni_pago_ni_asiento(
    app, crear_estudio, crear_presupuesto, monkeypatch
):
    """Pago, asiento y estado van juntos: un fallo al final los deshace con el rollback."""
    from src.core.pagos import servicios

    def falla(*args, **kwargs):
        raise RuntimeError("falla el cambio de estado")

    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        paciente = estudio.paciente.usuario
        monkeypatch.setattr(servicios, "cambiar_estado", falla)

        with pytest.raises(RuntimeError):
            pagar_particular(estudio, paciente, "500")
        db.session.rollback()

        assert db.session.scalars(sa.select(Pago)).all() == []
        assert _estado_guardado(estudio_id) == EstadoEstudio.PRESUPUESTADO
        habilitados = db.session.scalar(
            sa.select(sa.func.count())
            .select_from(HistorialEstado)
            .where(
                HistorialEstado.estudio_id == estudio_id,
                HistorialEstado.estado_nuevo == EstadoEstudio.HABILITADO_TURNO,
            )
        )
        assert habilitados == 0
        pagos_registrados = db.session.scalar(
            sa.select(sa.func.count())
            .select_from(AsientoFinanciero)
            .where(
                AsientoFinanciero.estudio_id == estudio_id,
                AsientoFinanciero.tipo == TipoAsiento.PAGO_PARTICULAR,
            )
        )
        assert pagos_registrados == 0


# --- rutas ---


def test_administrativo_ve_los_creados_y_emite(app, client, login_como, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(genes=GENES[:6])
        estudio_id, codigo = estudio.id, estudio.codigo
    login_como(roles.ADMINISTRATIVO)

    lista = client.get("/presupuestos")
    assert lista.status_code == 200
    assert codigo in lista.text
    assert "530.00 USD" in lista.text

    respuesta = client.post(f"/presupuestos/{estudio_id}", follow_redirects=True)
    assert respuesta.status_code == 200
    assert "Se emitió el presupuesto" in respuesta.text
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.PRESUPUESTADO


def test_emitir_dos_veces_por_la_ruta_muestra_el_error(app, client, login_como, crear_estudio):
    with app.app_context():
        estudio_id = crear_estudio().id
    login_como(roles.ADMINISTRATIVO)
    client.post(f"/presupuestos/{estudio_id}")

    respuesta = client.post(f"/presupuestos/{estudio_id}", follow_redirects=True)

    assert "ya tiene presupuesto" in respuesta.text
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Presupuesto)) == 1


def test_emitir_estudio_inexistente_da_404(client, login_como):
    login_como(roles.ADMINISTRATIVO)

    assert client.post("/presupuestos/999999").status_code == 404


def test_paciente_ve_su_presupuesto_y_lo_paga(app, client, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario)

    vista = client.get(f"/estudios/{estudio_id}/presupuesto")
    assert vista.status_code == 200
    assert "500.00 USD" in vista.text
    confirmacion = client.get(f"/estudios/{estudio_id}/pago")
    assert "Confirmar pago de 500.00 USD" in confirmacion.text

    pagado = client.post(f"/estudios/{estudio_id}/pago", data={"importe": "500.00"})
    assert pagado.status_code == 302
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.HABILITADO_TURNO


def test_la_ruta_rechaza_un_importe_distinto(app, client, crear_estudio, crear_presupuesto):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.post(f"/estudios/{estudio_id}/pago", data={"importe": "1"})

    assert respuesta.status_code == 400
    assert "importe final" in respuesta.text
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.PRESUPUESTADO


def test_el_paciente_entra_a_su_presupuesto_desde_el_menu(
    app, client, crear_estudio, crear_presupuesto
):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        _entrar_como(client, estudio.paciente.usuario)

    respuesta = client.get("/mi-presupuesto")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith(f"/estudios/{estudio_id}/presupuesto")


def test_paciente_ajeno_recibe_404(app, client, crear_estudio, crear_presupuesto, crear_paciente):
    with app.app_context():
        estudio, _ = _estudio_presupuestado(crear_estudio, crear_presupuesto)
        estudio_id = estudio.id
        otro = crear_paciente().usuario
        db.session.commit()
        _entrar_como(client, otro)

    assert client.get(f"/estudios/{estudio_id}/presupuesto").status_code == 404
    assert client.get(f"/estudios/{estudio_id}/pago").status_code == 404
    assert client.post(f"/estudios/{estudio_id}/pago", data={"importe": "500"}).status_code == 404
    with app.app_context():
        assert _estado_guardado(estudio_id) == EstadoEstudio.PRESUPUESTADO


@pytest.mark.parametrize(
    "rol",
    [roles.ADMINISTRATIVO, roles.MEDICO_TRATANTE, roles.BIOINFORMATICO, roles.GERENTE_MEDICO],
)
def test_otros_roles_no_entran_a_las_rutas_del_paciente(client, login_como, rol):
    login_como(rol)

    assert client.get("/estudios/1/presupuesto").status_code == 403
    assert client.get("/estudios/1/pago").status_code == 403
    assert client.post("/estudios/1/pago", data={"importe": "500"}).status_code == 403
    assert client.get("/mi-presupuesto").status_code == 403


@pytest.mark.parametrize("rol", [roles.PACIENTE, roles.MEDICO_TRATANTE, roles.TRANSPORTISTA])
def test_solo_el_administrativo_entra_a_los_presupuestos(client, login_como, rol):
    login_como(rol)

    assert client.get("/presupuestos").status_code == 403
    assert client.post("/presupuestos/1").status_code == 403


def test_sin_sesion_redirige_al_login(client):
    assert client.get("/presupuestos").status_code == 302
    assert client.get("/estudios/1/presupuesto").status_code == 302
