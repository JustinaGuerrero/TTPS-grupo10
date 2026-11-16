"""Tests del buscador de términos SNOMED (E07)."""

import httpx
import pytest

from src.core.usuarios import roles
from src.integraciones import snomed
from src.integraciones.base import ClienteApi, ErrorDeIntegracion


def _cliente(handler) -> ClienteApi:
    return ClienteApi("SNOMED", "http://snomed.test", transport=httpx.MockTransport(handler))


def test_menos_de_3_letras_devuelve_lista_vacia_sin_llamar():
    def handler(request):
        raise AssertionError("No debería llamar al módulo")

    assert snomed.buscar_terminos("fi", "sintoma", cliente=_cliente(handler)) == []
    assert snomed.buscar_terminos("  ", "sintoma", cliente=_cliente(handler)) == []


def test_devuelve_los_terminos_que_coinciden():
    def handler(request):
        assert request.url.params["q"] == "fieb"
        assert request.url.params["tipo"] == "sintoma"
        return httpx.Response(200, json=[{"codigo": "386661006", "termino": "Fiebre"}])

    terminos = snomed.buscar_terminos("fieb", "sintoma", cliente=_cliente(handler))
    assert terminos == [snomed.TerminoSnomed("386661006", "Fiebre")]


def test_tipo_invalido_falla():
    with pytest.raises(ValueError):
        snomed.buscar_terminos("fiebre", "otro", cliente=_cliente(lambda r: httpx.Response(200)))


def test_snomed_sin_respuesta_da_error_legible():
    def handler(request):
        raise httpx.ConnectTimeout("lento")

    with pytest.raises(ErrorDeIntegracion) as error:
        snomed.buscar_terminos("fiebre", "sintoma", cliente=_cliente(handler))
    assert "SNOMED no respondió a tiempo" in error.value.mensaje


def test_respuesta_fuera_del_contrato_da_error():
    cliente = _cliente(lambda r: httpx.Response(200, json={"algo": "raro"}))
    with pytest.raises(ErrorDeIntegracion):
        snomed.buscar_terminos("fiebre", "sintoma", cliente=cliente)


def test_con_mocks_lee_el_archivo_de_sintomas():
    cliente = ClienteApi("SNOMED", None, usar_mocks=True)
    terminos = snomed.buscar_terminos("fiebre", "sintoma", cliente=cliente)
    assert any(t.termino == "Fiebre" for t in terminos)


# --- endpoint GET /snomed/terminos ---------------------------------------------------------


def test_el_endpoint_devuelve_json_para_el_gerente_medico(login_como, monkeypatch):
    monkeypatch.setattr(
        snomed,
        "buscar_terminos",
        lambda texto, tipo, **kw: [snomed.TerminoSnomed("1", "Fiebre")],
    )
    respuesta = login_como(roles.GERENTE_MEDICO).get("/snomed/terminos?q=fie&tipo=sintoma")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [{"codigo": "1", "termino": "Fiebre"}]


def test_el_endpoint_con_snomed_caido_devuelve_json_de_error(login_como, monkeypatch):
    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("SNOMED", "SNOMED no respondió a tiempo.")

    monkeypatch.setattr(snomed, "buscar_terminos", caido)
    respuesta = login_como(roles.MEDICO_TRATANTE).get("/snomed/terminos?q=fie&tipo=sintoma")
    assert respuesta.status_code == 503
    assert "SNOMED no respondió a tiempo." in respuesta.get_json()["error"]


def test_el_paciente_no_entra_al_endpoint(login_como):
    respuesta = login_como(roles.PACIENTE).get("/snomed/terminos?q=fie&tipo=sintoma")
    assert respuesta.status_code == 403
