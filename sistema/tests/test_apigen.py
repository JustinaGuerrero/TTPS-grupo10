"""Cliente de Apigen (apigen/contrato.md, v1).

Cada función se prueba de dos maneras: en modo mock, con los archivos de
tests/fixtures/apis/apigen/, y contra un httpx.MockTransport que controla el pedido que se arma
(URL, filtros, cuerpo y headers) y responde como Apigen. Ningún test sale a la red.
"""

import json

import httpx
import pytest

from src.integraciones import apigen
from src.integraciones.apigen import (
    Clasificacion,
    GenAcmg,
    ResultadoDiagnostico,
    Variante,
)
from src.integraciones.base import ClienteApi, ErrorDeIntegracion

URL = "https://apigen.prueba.test/rest/v1"


class ApigenFalsa:
    """Responde siempre lo mismo y guarda los pedidos para revisarlos."""

    def __init__(self, respuesta: httpx.Response | Exception) -> None:
        self.respuesta = respuesta
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

    def cliente(self) -> ClienteApi:
        return ClienteApi(
            "Apigen", URL, headers={"apikey": "clave"}, transport=httpx.MockTransport(self)
        )

    @property
    def pedido(self) -> httpx.Request:
        return self.pedidos[-1]

    @property
    def cuerpo(self):
        return json.loads(self.pedido.content)


@pytest.fixture
def mocks() -> ClienteApi:
    """Cliente en modo mock con los archivos de tests/fixtures/apis/apigen/."""
    return ClienteApi("Apigen", URL, usar_mocks=True)


# --- Configuración ---


def test_el_cliente_por_defecto_sale_de_la_configuracion(app):
    app.config.update(APIGEN_URL=URL, APIGEN_KEY="clave-de-config", USE_MOCKS=False)
    with app.app_context():
        cliente = apigen.cliente_por_defecto()

    assert cliente.nombre == "Apigen"
    assert cliente.url_base == URL
    # La clave va en el header apikey, no como Authorization: Bearer.
    assert cliente.headers == {"apikey": "clave-de-config"}
    assert "Authorization" not in cliente.headers
    assert cliente.usar_mocks is False


def test_en_los_tests_las_funciones_usan_los_mocks(app):
    with app.app_context():
        assert apigen.cliente_por_defecto().usar_mocks is True
        assert apigen.genes_de_patologia("POMPE") == ["GAA"]


# --- Genes de una patología (endpoint 3) ---


@pytest.mark.parametrize(
    ("patologia", "genes"),
    [
        ("FABRY", ["GLA"]),
        ("POMPE", ["GAA"]),
        ("GAUCHER", ["GBA1"]),
        ("MPS1", ["IDUA"]),
        ("ASMD", ["SMPD1"]),
    ],
)
def test_genes_de_patologia_con_mocks(mocks, patologia, genes):
    assert apigen.genes_de_patologia(patologia, cliente=mocks) == genes


def test_genes_de_patologia_con_mocks_patologia_inexistente(mocks):
    with pytest.raises(ErrorDeIntegracion) as error:
        apigen.genes_de_patologia("MPS2", cliente=mocks)

    assert error.value.mensaje == "Patología inexistente: MPS2"


def test_genes_de_patologia_arma_el_pedido_del_contrato():
    falsa = ApigenFalsa(httpx.Response(200, json=["GAA"]))

    genes = apigen.genes_de_patologia(" pompe ", cliente=falsa.cliente())

    assert genes == ["GAA"]
    assert falsa.pedido.method == "POST"
    assert str(falsa.pedido.url) == f"{URL}/rpc/genes_por_patologia"
    assert falsa.pedido.headers["apikey"] == "clave"
    assert falsa.cuerpo == {"p_patologia": "POMPE", "p_grupo_id": "grupo10"}


def test_genes_de_patologia_muestra_el_error_de_apigen():
    cuerpo = {
        "code": "P0001",
        "details": None,
        "hint": None,
        "message": "Patología inexistente: XYZ",
    }
    falsa = ApigenFalsa(httpx.Response(400, json=cuerpo))

    with pytest.raises(ErrorDeIntegracion) as error:
        apigen.genes_de_patologia("XYZ", cliente=falsa.cliente())

    assert error.value.mensaje == "Patología inexistente: XYZ"


def test_genes_de_patologia_sin_codigo_no_llama_a_apigen():
    falsa = ApigenFalsa(httpx.Response(200, json=[]))

    with pytest.raises(ValueError):
        apigen.genes_de_patologia("  ", cliente=falsa.cliente())

    assert falsa.pedidos == []


def test_genes_de_patologia_rechaza_una_respuesta_fuera_del_contrato():
    falsa = ApigenFalsa(httpx.Response(200, json={"genes": ["GAA"]}))

    with pytest.raises(ErrorDeIntegracion) as error:
        apigen.genes_de_patologia("POMPE", cliente=falsa.cliente())

    assert error.value.mensaje == "Apigen respondió con datos que el sistema no entiende."


# --- Genes de hallazgos secundarios (endpoint 4) ---


def test_genes_hallazgos_secundarios_con_mocks(mocks):
    genes = apigen.genes_hallazgos_secundarios(cliente=mocks)

    assert GenAcmg("BRCA1", "Cáncer de mama y ovario hereditario", "dominante") in genes
    assert {gen.herencia for gen in genes} == {"dominante", "recesiva", "ligada_x"}


def test_genes_hallazgos_secundarios_arma_el_pedido_del_contrato():
    fila = {
        "gen": "BRCA1",
        "condicion": "Cáncer de mama y ovario hereditario",
        "herencia": "dominante",
    }
    falsa = ApigenFalsa(httpx.Response(200, json=[fila]))

    genes = apigen.genes_hallazgos_secundarios(cliente=falsa.cliente())

    assert genes == [GenAcmg("BRCA1", "Cáncer de mama y ovario hereditario", "dominante")]
    assert falsa.pedido.method == "GET"
    assert falsa.pedido.url.path == "/rest/v1/genes_hallazgos_secundarios"
    assert dict(falsa.pedido.url.params) == {"select": "gen,condicion,herencia", "order": "gen"}


def test_genes_hallazgos_secundarios_rechaza_filas_incompletas():
    falsa = ApigenFalsa(httpx.Response(200, json=[{"gen": "BRCA1"}]))

    with pytest.raises(ErrorDeIntegracion):
        apigen.genes_hallazgos_secundarios(cliente=falsa.cliente())


# --- Variantes de un gen (endpoint 5) ---


def test_variantes_de_gen_con_mocks(mocks):
    pagina = apigen.variantes_de_gen("GAA", cliente=mocks)

    assert pagina.total == len(pagina.variantes) == 6
    assert pagina.variantes[0] == Variante(
        "GAA:c.-32-13T>G", "c.-32-13T>G", None, Clasificacion.PATOGENICA
    )
    assert not pagina.hay_siguiente


def test_variantes_de_gen_con_mocks_gen_sin_archivo_devuelve_lista_vacia(mocks):
    pagina = apigen.variantes_de_gen("BRCA1", cliente=mocks)

    assert pagina.variantes == []
    assert pagina.total == 0


def test_variantes_de_gen_arma_el_pedido_del_contrato():
    fila = {
        "id": "GAA:c.-32-13T>G",
        "hgvs_c": "c.-32-13T>G",
        "proteina": None,
        "clasificacion": "patogenica",
    }
    falsa = ApigenFalsa(httpx.Response(200, json=[fila], headers={"Content-Range": "50-50/3672"}))

    pagina = apigen.variantes_de_gen(
        "gaa",
        texto="32-13*",
        clasificacion="patogenica",
        limite=50,
        desde=50,
        cliente=falsa.cliente(),
    )

    assert falsa.pedido.method == "GET"
    assert falsa.pedido.url.path == "/rest/v1/variantes"
    assert dict(falsa.pedido.url.params) == {
        "gen": "eq.GAA",
        "select": "id,hgvs_c,proteina,clasificacion",
        "order": "hgvs_c",
        "limit": "50",
        "offset": "50",
        "hgvs_c": "ilike.*32-13*",
        "clasificacion": "eq.patogenica",
    }
    assert falsa.pedido.headers["Prefer"] == "count=exact"
    assert pagina.variantes == [
        Variante("GAA:c.-32-13T>G", "c.-32-13T>G", None, Clasificacion.PATOGENICA)
    ]
    assert pagina.total == 3672
    assert pagina.desde == 50
    assert pagina.hay_siguiente


def test_variantes_de_gen_sin_variantes():
    falsa = ApigenFalsa(httpx.Response(200, json=[], headers={"Content-Range": "*/0"}))

    pagina = apigen.variantes_de_gen("XYZ1", cliente=falsa.cliente())

    assert pagina.variantes == []
    assert pagina.total == 0


@pytest.mark.parametrize(
    "argumentos",
    [
        {"gen": " "},
        {"gen": "GAA", "limite": 0},
        {"gen": "GAA", "limite": 1001},
        {"gen": "GAA", "desde": -1},
    ],
)
def test_variantes_de_gen_valida_los_argumentos(argumentos):
    falsa = ApigenFalsa(httpx.Response(200, json=[]))

    with pytest.raises(ValueError):
        apigen.variantes_de_gen(**argumentos, cliente=falsa.cliente())

    assert falsa.pedidos == []


def test_variantes_de_gen_rechaza_una_clasificacion_desconocida():
    fila = {"id": "GAA:c.1A>G", "hgvs_c": "c.1A>G", "proteina": None, "clasificacion": "rara"}
    falsa = ApigenFalsa(httpx.Response(200, json=[fila]))

    with pytest.raises(ErrorDeIntegracion):
        apigen.variantes_de_gen("GAA", cliente=falsa.cliente())


# --- Resultado del diagnóstico (endpoint 7) ---


@pytest.mark.parametrize(
    ("patologia", "resultado"),
    [
        ("POMPE", ResultadoDiagnostico.PORTADOR),
        ("FABRY", ResultadoDiagnostico.POSITIVO),
        ("GAUCHER", ResultadoDiagnostico.NEGATIVO),
    ],
)
def test_resultado_diagnostico_con_mocks(mocks, patologia, resultado):
    assert apigen.resultado_diagnostico(patologia, ["X:c.1A>G"], cliente=mocks) is resultado


@pytest.mark.parametrize("resultado", ["positivo", "portador", "negativo"])
def test_resultado_diagnostico_arma_el_pedido_del_contrato(resultado):
    falsa = ApigenFalsa(httpx.Response(200, json=resultado))

    obtenido = apigen.resultado_diagnostico(
        "pompe", ["GAA:c.-32-13T>G", " GAA:c.-32-13T>G ", ""], cliente=falsa.cliente()
    )

    assert obtenido == ResultadoDiagnostico(resultado)
    assert falsa.pedido.method == "POST"
    assert str(falsa.pedido.url) == f"{URL}/rpc/resultado_diagnostico"
    # La homocigota va repetida; las vacías no se mandan.
    assert falsa.cuerpo == {
        "p_patologia": "POMPE",
        "p_variantes": ["GAA:c.-32-13T>G", "GAA:c.-32-13T>G"],
        "p_grupo_id": "grupo10",
    }


def test_resultado_diagnostico_muestra_el_error_de_variante():
    falsa = ApigenFalsa(
        httpx.Response(400, json={"message": "Variante inexistente: GAA:c.99999A>G"})
    )

    with pytest.raises(ErrorDeIntegracion) as error:
        apigen.resultado_diagnostico("POMPE", ["GAA:c.99999A>G"], cliente=falsa.cliente())

    assert error.value.mensaje == "Variante inexistente: GAA:c.99999A>G"


def test_resultado_diagnostico_rechaza_un_valor_fuera_del_contrato():
    falsa = ApigenFalsa(httpx.Response(200, json=True))

    with pytest.raises(ErrorDeIntegracion):
        apigen.resultado_diagnostico("POMPE", ["GAA:c.525del"], cliente=falsa.cliente())


# --- Apigen no responde: ninguna función rompe con una excepción de httpx ---


LLAMADAS = {
    "genes_de_patologia": lambda cliente: apigen.genes_de_patologia("POMPE", cliente=cliente),
    "genes_hallazgos_secundarios": lambda cliente: apigen.genes_hallazgos_secundarios(
        cliente=cliente
    ),
    "variantes_de_gen": lambda cliente: apigen.variantes_de_gen("GAA", cliente=cliente),
    "resultado_diagnostico": lambda cliente: apigen.resultado_diagnostico(
        "POMPE", ["GAA:c.525del"], cliente=cliente
    ),
}


@pytest.mark.parametrize("funcion", LLAMADAS)
@pytest.mark.parametrize(
    ("falla", "mensaje"),
    [
        (
            httpx.ReadTimeout("timed out"),
            "Apigen no respondió a tiempo. Probá de nuevo en unos minutos.",
        ),
        (
            httpx.ConnectError("connection refused"),
            "No se pudo conectar con Apigen. Probá de nuevo en unos minutos.",
        ),
        (
            httpx.Response(503, text="Service Unavailable"),
            "Apigen tuvo un error interno. Probá de nuevo en unos minutos.",
        ),
    ],
)
def test_si_apigen_no_responde_cada_funcion_da_un_error_legible(funcion, falla, mensaje):
    falsa = ApigenFalsa(falla)

    with pytest.raises(ErrorDeIntegracion) as error:
        LLAMADAS[funcion](falsa.cliente())

    assert error.value.mensaje == mensaje
    assert len(falsa.pedidos) == 1


def test_si_apigen_no_responde_la_pagina_muestra_el_mensaje(app, client, login_como):
    """Un controlador que atrapa ErrorDeIntegracion muestra el mensaje y no da 500."""
    from flask import flash, render_template_string

    from src.core.usuarios import roles
    from src.web.helpers.auth import login_required, rol_requerido

    falsa = ApigenFalsa(httpx.ReadTimeout("timed out"))

    @app.get("/prueba-apigen")
    @login_required
    @rol_requerido(roles.MEDICO_TRATANTE)
    def prueba_apigen():
        try:
            genes = apigen.genes_de_patologia("POMPE", cliente=falsa.cliente())
        except ErrorDeIntegracion as error:
            flash(error.mensaje, "error")
            genes = []
        return render_template_string(
            '{% extends "layout.html" %}{% block content %}Genes: {{ genes|length }}{% endblock %}',
            genes=genes,
        )

    respuesta = login_como(roles.MEDICO_TRATANTE).get("/prueba-apigen")

    assert respuesta.status_code == 200
    assert "Apigen no respondió a tiempo." in respuesta.text
    assert "Genes: 0" in respuesta.text
