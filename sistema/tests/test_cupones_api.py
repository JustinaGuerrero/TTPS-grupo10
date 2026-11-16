"""integraciones/cupones.py: cuerpos, headers, paginación y errores de la API de cupones.

Ningún test sale a la red: los pedidos los responde un httpx.MockTransport.
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from src.integraciones import cupones
from src.integraciones.base import ClienteApi, ErrorDeIntegracion


def _cliente(manejador) -> ClienteApi:
    return ClienteApi(
        "Cupones",
        "https://cupones.test/functions/v1/cupones-api",
        headers={"X-API-Key": "clave-de-prueba"},
        transport=httpx.MockTransport(manejador),
    )


def _item(codigo, estado="paciente", vencimiento="2099-12-31"):
    return {
        "id": "00000000-0000-4000-8000-000000000001",
        "codigo": codigo,
        "estado": estado,
        "gerente_id": "G-1",
        "medico_id": "M-2",
        "paciente_id": "P-3",
        "porcentaje_descuento": 20,
        "fecha_vencimiento": vencimiento,
        "fecha_uso": None,
    }


def test_generar_manda_el_cuerpo_de_la_guia_con_la_clave_y_sin_grupo():
    pedidos = []

    def manejador(request):
        pedidos.append(request)
        return httpx.Response(200, json=[{"codigo_cupon": "53399388", "porcentaje": 20}] * 2)

    generados = cupones.generar(7, Decimal(20), 2, cliente=_cliente(manejador))

    pedido = pedidos[0]
    assert pedido.url.path.endswith("/generar_cupones_gerencia")
    assert pedido.headers["X-API-Key"] == "clave-de-prueba"
    assert "authorization" not in pedido.headers
    assert json.loads(pedido.content) == {
        "p_gerente_id": "G-7",
        "p_cantidad": 2,
        "p_porcentaje_descuento": 20.0,
    }
    assert generados == [cupones.CuponGenerado("53399388", Decimal(20))] * 2


def test_generar_con_menos_cupones_de_los_pedidos_es_un_formato_inesperado():
    cliente = _cliente(lambda r: httpx.Response(200, json=[{"codigo_cupon": "1", "porcentaje": 5}]))

    with pytest.raises(ErrorDeIntegracion, match="no entiende"):
        cupones.generar(1, 5, 3, cliente=cliente)


def test_las_asignaciones_y_el_canje_arman_los_ids_con_prefijo():
    cuerpos = {}

    def manejador(request):
        cuerpos[request.url.path.rsplit("/", 1)[1]] = json.loads(request.content)
        return httpx.Response(200, json=True)

    cliente = _cliente(manejador)
    cupones.asignar_a_medico(1, 2, "ABC", cliente=cliente)
    cupones.asignar_a_paciente(2, 3, "ABC", cliente=cliente)
    cupones.canjear(3, "ABC", cliente=cliente)

    assert cuerpos == {
        "asignar_cupon_a_medico": {"p_gerente_id": "G-1", "p_medico_id": "M-2", "p_codigo": "ABC"},
        "asignar_cupon_a_paciente": {
            "p_medico_id": "M-2",
            "p_paciente_id": "P-3",
            "p_codigo": "ABC",
        },
        "canjear_cupon": {"p_paciente_id": "P-3", "p_codigo": "ABC"},
    }


def test_consultar_recorre_las_paginas_hasta_encontrar_el_codigo():
    desde = []

    def manejador(request):
        offset = int(request.url.params["offset"])
        desde.append(offset)
        assert request.url.params["limit"] == "100"
        assert request.url.params["medico_id"] == "M-2"
        items = [_item(f"C{offset + n}") for n in range(100)]
        return httpx.Response(
            200, json={"items": items, "total": 250, "limit": 100, "offset": offset}
        )

    cupon = cupones.consultar("C150", medico_id=2, cliente=_cliente(manejador))

    assert desde == [0, 100]
    assert cupon.codigo == "C150"
    assert cupon.estado == "paciente"
    assert cupon.porcentaje == Decimal(20)
    assert cupon.paciente_id == "P-3"
    assert cupon.fecha_vencimiento == date(2099, 12, 31)


def test_consultar_un_codigo_que_no_esta_devuelve_none():
    cliente = _cliente(
        lambda r: httpx.Response(
            200, json={"items": [_item("A")], "total": 1, "limit": 100, "offset": 0}
        )
    )

    assert cupones.consultar("OTRO", cliente=cliente) is None


def test_un_cupon_vence_segun_su_fecha():
    ayer = (datetime.now(UTC) - timedelta(days=2)).date().isoformat()
    cliente = _cliente(
        lambda r: httpx.Response(
            200,
            json={"items": [_item("V", vencimiento=ayer)], "total": 1, "limit": 100, "offset": 0},
        )
    )

    assert cupones.consultar("V", cliente=cliente).vencido is True


@pytest.mark.parametrize(
    ("status", "cuerpo"),
    [(409, {"code": "PT409", "message": "Cupón ya canjeado"}), (404, {"message": "No existe"})],
)
def test_los_rechazos_del_modulo_conservan_el_status_y_el_mensaje(status, cuerpo):
    cliente = _cliente(lambda r: httpx.Response(status, json=cuerpo))

    with pytest.raises(ErrorDeIntegracion) as error:
        cupones.canjear(1, "ABC", cliente=cliente)

    assert error.value.status == status
    assert error.value.mensaje == cuerpo["message"]


def test_una_caida_del_modulo_es_un_error_legible():
    cliente = _cliente(lambda r: httpx.Response(503, json={"code": "HTTP503", "message": "x"}))

    with pytest.raises(ErrorDeIntegracion, match="error interno"):
        cupones.canjear(1, "ABC", cliente=cliente)


def test_un_codigo_con_espacios_no_sale_al_modulo():
    def manejador(request):
        raise AssertionError("No debería llamar al módulo")

    with pytest.raises(ValueError):
        cupones.canjear(1, "AB C", cliente=_cliente(manejador))
