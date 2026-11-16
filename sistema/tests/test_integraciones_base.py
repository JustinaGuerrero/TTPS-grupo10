"""Cliente base de las APIs externas (decisión S10): timeout, errores legibles y modo mock.

Ningún test sale a la red: los pedidos reales los responde un httpx.MockTransport.
"""

import json

import httpx
import pytest

from src.integraciones.base import TIMEOUT_EN_SEGUNDOS, ClienteApi, ErrorDeIntegracion


def _cliente(manejador, **opciones) -> ClienteApi:
    return ClienteApi(
        "Prueba",
        "https://api.prueba.test/v1",
        headers={"apikey": "clave-de-prueba"},
        transport=httpx.MockTransport(manejador),
        **opciones,
    )


def _error_de(cliente: ClienteApi) -> ErrorDeIntegracion:
    with pytest.raises(ErrorDeIntegracion) as error:
        cliente.get("algo", mock="algo")
    return error.value


# --- Pedidos que salen bien ---


def test_get_devuelve_el_json_y_los_headers():
    pedidos = []

    def manejador(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, json=[{"simbolo": "GAA"}], headers={"Content-Range": "0-0/1"})

    respuesta = _cliente(manejador).get("gen", params={"simbolo": "eq.GAA"}, mock="gen")

    assert respuesta.datos == [{"simbolo": "GAA"}]
    assert respuesta.headers["content-range"] == "0-0/1"
    assert str(pedidos[0].url) == "https://api.prueba.test/v1/gen?simbolo=eq.GAA"
    assert pedidos[0].headers["apikey"] == "clave-de-prueba"


def test_post_manda_el_cuerpo_en_json_y_suma_headers_del_pedido():
    pedidos = []

    def manejador(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, json="positivo")

    respuesta = _cliente(manejador).post(
        "rpc/funcion", json={"p_x": [1, 2]}, headers={"Prefer": "count=exact"}, mock="x"
    )

    assert respuesta.datos == "positivo"
    assert pedidos[0].method == "POST"
    assert pedidos[0].url.path == "/v1/rpc/funcion"
    assert json.loads(pedidos[0].content) == {"p_x": [1, 2]}
    assert pedidos[0].headers["Prefer"] == "count=exact"
    assert pedidos[0].headers["apikey"] == "clave-de-prueba"


def test_el_timeout_es_de_5_segundos():
    pedidos = []

    def manejador(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return httpx.Response(200, json=[])

    _cliente(manejador).get("algo", mock="algo")

    assert TIMEOUT_EN_SEGUNDOS == 5
    assert pedidos[0].extensions["timeout"] == {
        "connect": 5.0,
        "read": 5.0,
        "write": 5.0,
        "pool": 5.0,
    }


# --- La API no responde: errores legibles, nunca excepciones de httpx ---


@pytest.mark.parametrize(
    "falla",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
        httpx.PoolTimeout("timed out"),
    ],
)
def test_si_la_api_no_responde_a_tiempo_da_un_error_legible(falla):
    def manejador(pedido: httpx.Request) -> httpx.Response:
        raise falla

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Prueba no respondió a tiempo. Probá de nuevo en unos minutos."
    assert str(error) == error.mensaje
    assert error.api == "Prueba"
    assert error.status is None
    # No encadena la excepción de httpx: el mensaje es lo único que importa.
    assert error.__cause__ is None


@pytest.mark.parametrize(
    "falla",
    [httpx.ConnectError("Name or service not known"), httpx.RemoteProtocolError("cortó")],
)
def test_si_no_hay_conexion_da_un_error_legible(falla):
    def manejador(pedido: httpx.Request) -> httpx.Response:
        raise falla

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "No se pudo conectar con Prueba. Probá de nuevo en unos minutos."
    assert error.status is None


def test_sin_url_configurada_da_un_error_legible():
    cliente = ClienteApi("Prueba", None)

    assert _error_de(cliente).mensaje == "Falta configurar la URL de Prueba."


# --- La API responde con un error ---


def test_un_400_muestra_el_mensaje_de_la_api():
    def manejador(pedido: httpx.Request) -> httpx.Response:
        cuerpo = {
            "code": "P0001",
            "details": None,
            "hint": None,
            "message": "Patología inexistente: XYZ",
        }
        return httpx.Response(400, json=cuerpo)

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Patología inexistente: XYZ"
    assert error.status == 400


def test_un_400_sin_mensaje_da_un_error_generico():
    def manejador(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Prueba respondió con un error (400)."


@pytest.mark.parametrize("status", [401, 403])
def test_una_clave_rechazada_no_muestra_el_detalle_tecnico(status):
    def manejador(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "Invalid API key"})

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Prueba rechazó la clave de acceso del sistema."
    assert error.status == status


@pytest.mark.parametrize("status", [500, 502, 503])
def test_un_error_del_servidor_da_un_error_legible(status):
    def manejador(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="<html>Bad Gateway</html>")

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Prueba tuvo un error interno. Probá de nuevo en unos minutos."
    assert error.status == status


def test_una_respuesta_que_no_es_json_da_un_error_legible():
    def manejador(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Mantenimiento</html>")

    error = _error_de(_cliente(manejador))

    assert error.mensaje == "Prueba respondió con datos que el sistema no entiende."


# --- Modo mock ---


@pytest.fixture
def carpeta_de_mocks(tmp_path):
    carpeta = tmp_path / "prueba"
    carpeta.mkdir()
    (carpeta / "genes_POMPE.json").write_text('["GAA"]', encoding="utf-8")
    (carpeta / "genes.json").write_text("[]", encoding="utf-8")
    (carpeta / "genes_MPS2.error.json").write_text(
        '{"status": 400, "message": "Patología inexistente: MPS2"}', encoding="utf-8"
    )
    return tmp_path


def _cliente_mock(carpeta) -> ClienteApi:
    def sin_red(pedido: httpx.Request) -> httpx.Response:
        raise AssertionError("En modo mock no se llama a la API")

    return ClienteApi(
        "Prueba",
        "https://api.prueba.test/v1",
        usar_mocks=True,
        carpeta_de_mocks=carpeta,
        transport=httpx.MockTransport(sin_red),
    )


def test_el_mock_lee_la_respuesta_del_archivo(carpeta_de_mocks):
    respuesta = _cliente_mock(carpeta_de_mocks).post("rpc/genes", json={}, mock="genes_POMPE")

    assert respuesta.datos == ["GAA"]


def test_el_mock_usa_la_primera_clave_que_tiene_archivo(carpeta_de_mocks):
    cliente = _cliente_mock(carpeta_de_mocks)

    assert cliente.get("genes", mock=["genes_GAUCHER", "genes"]).datos == []
    assert cliente.get("genes", mock=["genes_POMPE", "genes"]).datos == ["GAA"]


def test_el_mock_puede_simular_un_error(carpeta_de_mocks):
    with pytest.raises(ErrorDeIntegracion) as error:
        _cliente_mock(carpeta_de_mocks).post("rpc/genes", json={}, mock="genes_MPS2")

    assert error.value.mensaje == "Patología inexistente: MPS2"
    assert error.value.status == 400


def test_sin_archivo_de_mock_da_un_error_legible(carpeta_de_mocks):
    with pytest.raises(ErrorDeIntegracion) as error:
        _cliente_mock(carpeta_de_mocks).get("genes", mock="genes_XYZ")

    assert "No hay respuesta simulada de Prueba para «genes_XYZ»" in error.value.mensaje


def test_las_claves_de_mock_no_salen_de_la_carpeta(carpeta_de_mocks):
    (carpeta_de_mocks / "secreto.json").write_text('"no"', encoding="utf-8")

    with pytest.raises(ErrorDeIntegracion):
        _cliente_mock(carpeta_de_mocks).get("x", mock="../secreto")
