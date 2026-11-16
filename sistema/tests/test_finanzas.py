"""E41 Registrar operación financiera: registrar_asiento, caja y deudas."""

import subprocess
import sys
from decimal import Decimal

import pytest
import sqlalchemy as sa

from src.core.database import db
from src.core.finanzas import (
    Pago,
    TipoAsiento,
    TipoPago,
    caja,
    deuda_por_obra_social,
    deuda_por_paciente,
    registrar_asiento,
)


def _pago(estudio, importe):
    pago = Pago(estudio_id=estudio.id, tipo=TipoPago.PARTICULAR, importe_usd=importe)
    db.session.add(pago)
    db.session.flush()
    return pago


def test_caja_suma_pagos_particulares_y_cobros_de_obras_sociales(
    app, crear_estudio, crear_obra_social
):
    with app.app_context():
        estudio = crear_estudio()
        obra = crear_obra_social()
        pago = _pago(estudio, 200)
        registrar_asiento(TipoAsiento.PAGO_PARTICULAR, estudio, 200, pago=pago)
        registrar_asiento(TipoAsiento.COBRO_OBRA_SOCIAL, estudio, "100.50", obra_social=obra)
        # No entran en la caja.
        registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, estudio, 500)
        registrar_asiento(
            TipoAsiento.COBERTURA_OBRA_SOCIAL, estudio, 300, pago=pago, obra_social=obra
        )

        assert caja() == Decimal("300.50")


def test_caja_vacia_es_cero(app):
    with app.app_context():
        assert caja() == Decimal(0)


def test_deuda_por_paciente(app, crear_estudio, crear_obra_social):
    with app.app_context():
        sin_pagar = crear_estudio()
        pagado = crear_estudio()
        parcial = crear_estudio()
        obra = crear_obra_social()
        for estudio in (sin_pagar, pagado, parcial):
            registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, estudio, 500)
        registrar_asiento(TipoAsiento.PAGO_PARTICULAR, pagado, 500, pago=_pago(pagado, 500))
        pago_parcial = _pago(parcial, 100)
        registrar_asiento(
            TipoAsiento.COBERTURA_OBRA_SOCIAL, parcial, 300, pago=pago_parcial, obra_social=obra
        )
        registrar_asiento(TipoAsiento.DESCUENTO_CUPON, parcial, 50, pago=pago_parcial)

        deudas = {d.estudio_id: d for d in deuda_por_paciente()}

        assert set(deudas) == {sin_pagar.id, parcial.id}
        assert deudas[sin_pagar.id].importe_usd == Decimal("500.00")
        assert deudas[sin_pagar.id].paciente_id == sin_pagar.paciente_id
        assert deudas[parcial.id].importe_usd == Decimal("150.00")


def test_deuda_por_obra_social(app, crear_estudio, crear_obra_social):
    with app.app_context():
        a, b = crear_obra_social("Obra A"), crear_obra_social("Obra B")
        e1, e2 = crear_estudio(), crear_estudio()
        pago1, pago2 = _pago(e1, 1), _pago(e2, 1)
        registrar_asiento(TipoAsiento.COBERTURA_OBRA_SOCIAL, e1, 400, pago=pago1, obra_social=a)
        registrar_asiento(TipoAsiento.COBERTURA_OBRA_SOCIAL, e2, 250, pago=pago2, obra_social=a)
        registrar_asiento(TipoAsiento.COBRO_OBRA_SOCIAL, e1, 400, obra_social=a)
        registrar_asiento(TipoAsiento.COBERTURA_OBRA_SOCIAL, e2, 100, pago=pago2, obra_social=b)

        deudas = {d.codigo: d for d in deuda_por_obra_social()}

        assert deudas[a.codigo].importe_usd == Decimal("250.00")
        assert deudas[a.codigo].nombre == "Obra A"
        assert deudas[b.codigo].importe_usd == Decimal("100.00")


@pytest.mark.parametrize("importe", [0, -5])
def test_asiento_con_importe_no_positivo_falla(app, crear_estudio, importe):
    with app.app_context(), pytest.raises(ValueError, match="mayor a cero"):
        registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, crear_estudio(), importe)


def test_reglas_de_obra_social_y_de_pago(app, crear_estudio, crear_obra_social):
    with app.app_context():
        estudio = crear_estudio()
        obra = crear_obra_social()
        pago = _pago(estudio, 10)
        with pytest.raises(ValueError, match="exige una obra social"):
            registrar_asiento(TipoAsiento.COBERTURA_OBRA_SOCIAL, estudio, 10, pago=pago)
        with pytest.raises(ValueError, match="no admite una obra social"):
            registrar_asiento(TipoAsiento.PAGO_PARTICULAR, estudio, 10, pago=pago, obra_social=obra)
        with pytest.raises(ValueError, match="exige el pago"):
            registrar_asiento(TipoAsiento.PAGO_PARTICULAR, estudio, 10)
        with pytest.raises(ValueError, match="tipo de asiento"):
            registrar_asiento("inventado", estudio, 10)


def test_la_base_rechaza_un_asiento_con_importe_cero(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()
        with pytest.raises(sa.exc.IntegrityError):
            db.session.execute(
                sa.text(
                    "insert into asientos_financieros (tipo, estudio_id, importe_usd) "
                    "values ('presupuesto_emitido', :e, 0)"
                ),
                {"e": estudio.id},
            )
        db.session.rollback()


def test_los_asientos_no_se_modifican_ni_se_borran(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()
        asiento = registrar_asiento(TipoAsiento.PRESUPUESTO_EMITIDO, estudio, 500)

        with pytest.raises(sa.exc.DBAPIError, match="solo se insertan"):
            db.session.execute(
                sa.text("update asientos_financieros set importe_usd = 1 where id = :i"),
                {"i": asiento.id},
            )
        db.session.rollback()


def test_finanzas_no_depende_de_pagos():
    """#33 y #38 llaman a las dos: finanzas se importa sola, sin cargar core/pagos."""
    codigo = (
        "import sys, src.core.finanzas as f;"
        "from src.core.database import Base;"
        'assert not [m for m in sys.modules if m.startswith("src.core.pagos")];'
        "Base.metadata.sorted_tables"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo], check=False, capture_output=True, text=True
    )
    assert resultado.returncode == 0, resultado.stderr
