"""E40 Consultar chatbot: cliente del chatbot de GenLab (docs/apis/chatbot.md) y pantalla del paciente.

El cliente se prueba en modo mock (tests/fixtures/apis/chatbot/) y contra un httpx.MockTransport
que controla el pedido (URL, headers y cuerpo) y responde como el chatbot. Ningún test sale a la red.
"""

import json
import logging

import httpx
import pytest

from src.core.usuarios import roles
from src.integraciones import chatbot
from src.integraciones.base import ErrorDeIntegracion
from src.integraciones.chatbot import (
    APAGADO,
    DEMASIADAS_PREGUNTAS,
    NO_DISPONIBLE,
    ClienteChatbot,
    PreguntaInvalida,
    RespuestaDelChatbot,
    TipoDeRespuesta,
)
from src.web.controllers.chatbot import CLAVE_DE_CONVERSACION

URL = "https://chatbot.prueba.test/functions/v1/chat"
RESPUESTA_DEL_MOCK = "El exoma clínico es el estudio de la parte del ADN"


class ChatbotFalso:
    """Responde siempre lo mismo y guarda los pedidos para revisarlos."""

    def __init__(self, respuesta: httpx.Response | Exception) -> None:
        self.respuesta = respuesta
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

    def cliente(self) -> ClienteChatbot:
        return ClienteChatbot(
            "Chatbot",
            URL,
            headers={"apikey": "clave-publishable", "x-chatbot-token": "token-del-grupo"},
            timeout=chatbot.TIMEOUT_EN_SEGUNDOS,
            transport=httpx.MockTransport(self),
        )

    @property
    def cuerpo(self):
        return json.loads(self.pedidos[-1].content)


def _ok(**datos) -> httpx.Response:
    cuerpo = {
        "respuesta": "Respuesta del chatbot.",
        "conversacion_id": "conv-1",
        "tipo": "respuesta",
    }
    return httpx.Response(200, json={**cuerpo, **datos})


@pytest.fixture
def paciente(login_como):
    return login_como(roles.PACIENTE)


@pytest.fixture
def chatbot_caido(monkeypatch):
    """Hace que el controlador use un chatbot que responde `respuesta`."""

    def _caido(respuesta):
        falso = ChatbotFalso(respuesta)
        monkeypatch.setattr(chatbot, "cliente_por_defecto", falso.cliente)
        return falso

    return _caido


# --- Cliente: configuración y mocks ---


def test_el_cliente_por_defecto_sale_de_la_configuracion(app):
    app.config.update(
        CHATBOT_URL=URL, CHATBOT_APIKEY="clave", CHATBOT_TOKEN="token", USE_MOCKS=False
    )
    with app.app_context():
        cliente = chatbot.cliente_por_defecto()

    assert cliente.url_base == URL
    assert cliente.headers == {"apikey": "clave", "x-chatbot-token": "token"}
    assert cliente.timeout == 20
    assert cliente.usar_mocks is False


def test_con_mocks_responde_el_archivo_de_fixtures(app):
    with app.app_context():
        respuesta = chatbot.preguntar("¿Qué es un exoma clínico?")

    assert respuesta.texto.startswith(RESPUESTA_DEL_MOCK)
    assert respuesta.conversacion_id == "00000000-0000-4000-8000-000000000001"
    assert respuesta.tipo is TipoDeRespuesta.RESPUESTA


# --- Cliente: el pedido del contrato ---


def test_preguntar_arma_el_pedido_del_contrato():
    falso = ChatbotFalso(_ok(conversacion_id="conv-2", tipo="derivar_medico"))

    respuesta = chatbot.preguntar("  ¿Y cómo se hereda?  ", "conv-1", cliente=falso.cliente())

    pedido = falso.pedidos[-1]
    assert pedido.method == "POST"
    # CHATBOT_URL es el endpoint completo: sin barra ni ruta agregadas.
    assert str(pedido.url) == URL
    assert pedido.headers["apikey"] == "clave-publishable"
    assert pedido.headers["x-chatbot-token"] == "token-del-grupo"
    assert falso.cuerpo == {"mensaje": "¿Y cómo se hereda?", "conversacion_id": "conv-1"}
    assert respuesta == RespuestaDelChatbot(
        "Respuesta del chatbot.", "conv-2", TipoDeRespuesta.DERIVAR_MEDICO
    )


def test_sin_conversacion_manda_null():
    falso = ChatbotFalso(_ok())

    chatbot.preguntar("Hola", cliente=falso.cliente())

    assert falso.cuerpo["conversacion_id"] is None


@pytest.mark.parametrize("tipo", list(TipoDeRespuesta))
def test_acepta_los_cuatro_tipos_del_contrato(tipo):
    falso = ChatbotFalso(_ok(tipo=tipo.value))

    assert chatbot.preguntar("Hola", cliente=falso.cliente()).tipo is tipo


def test_un_tipo_desconocido_igual_muestra_la_respuesta():
    falso = ChatbotFalso(_ok(tipo="otro_tipo_nuevo"))

    respuesta = chatbot.preguntar("Hola", cliente=falso.cliente())

    assert respuesta.texto == "Respuesta del chatbot."
    assert respuesta.tipo is TipoDeRespuesta.RESPUESTA


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("", "Escribí tu pregunta."),
        ("   \n ", "Escribí tu pregunta."),
        (None, "Escribí tu pregunta."),
        ("a" * 1001, "La pregunta puede tener hasta 1000 caracteres (tiene 1001)."),
    ],
)
def test_una_pregunta_invalida_no_llama_al_chatbot(texto, mensaje):
    falso = ChatbotFalso(_ok())

    with pytest.raises(PreguntaInvalida) as error:
        chatbot.preguntar(texto, cliente=falso.cliente())

    assert error.value.mensaje == mensaje
    assert falso.pedidos == []


def test_una_pregunta_de_1000_caracteres_se_manda():
    falso = ChatbotFalso(_ok())

    chatbot.preguntar("a" * 1000, cliente=falso.cliente())

    assert len(falso.cuerpo["mensaje"]) == 1000


# --- Cliente: errores legibles ---


@pytest.mark.parametrize(
    ("falla", "mensaje", "status"),
    [
        (httpx.Response(401, json={"detail": "Token inválido"}), NO_DISPONIBLE, 401),
        (
            httpx.Response(422, json={"detail": [{"loc": ["mensaje"]}]}),
            chatbot.PREGUNTA_RECHAZADA,
            422,
        ),
        (
            httpx.Response(429, json={"detail": "Límite"}, headers={"Retry-After": "30"}),
            DEMASIADAS_PREGUNTAS,
            429,
        ),
        (httpx.Response(500, json={"detail": "Error"}), NO_DISPONIBLE, 500),
        (
            httpx.Response(503, json={"detail": "El chatbot está en mantenimiento."}),
            "El chatbot está en mantenimiento.",
            503,
        ),
        (httpx.Response(503, text="Service Unavailable"), APAGADO, 503),
        (httpx.ReadTimeout("timed out"), NO_DISPONIBLE, None),
        (httpx.ConnectError("connection refused"), NO_DISPONIBLE, None),
        (httpx.Response(200, text="<html>no es JSON</html>"), NO_DISPONIBLE, None),
        (httpx.Response(200, json={"conversacion_id": "x"}), NO_DISPONIBLE, None),
        (httpx.Response(200, json=["no", "es", "un", "objeto"]), NO_DISPONIBLE, None),
    ],
)
def test_si_el_chatbot_falla_da_un_error_legible(falla, mensaje, status):
    falso = ChatbotFalso(falla)

    with pytest.raises(ErrorDeIntegracion) as error:
        chatbot.preguntar("¿Qué es Fabry?", cliente=falso.cliente())

    assert error.value.mensaje == mensaje
    assert error.value.status == status
    # Sin reintentos automáticos (decisión S18).
    assert len(falso.pedidos) == 1


def test_un_401_se_loguea_como_error_de_configuracion(caplog):
    falso = ChatbotFalso(httpx.Response(401, json={"detail": "Token inválido"}))

    with caplog.at_level(logging.ERROR), pytest.raises(ErrorDeIntegracion):
        chatbot.preguntar("Hola", cliente=falso.cliente())

    assert "CHATBOT_TOKEN" in caplog.text


def test_con_mocks_puede_simular_el_chatbot_apagado(tmp_path):
    carpeta = tmp_path / "chatbot"
    carpeta.mkdir()
    (carpeta / "respuesta.error.json").write_text(
        json.dumps({"status": 503, "message": "Apagado por mantenimiento."}), encoding="utf-8"
    )
    cliente = ClienteChatbot("Chatbot", URL, usar_mocks=True, carpeta_de_mocks=tmp_path)

    with pytest.raises(ErrorDeIntegracion) as error:
        chatbot.preguntar("Hola", cliente=cliente)

    assert error.value.mensaje == "Apagado por mantenimiento."


# --- Pantalla del paciente (episodios 1 a 3) ---


def test_el_paciente_ve_la_pantalla_con_el_aviso_de_asistente_automatico(paciente):
    respuesta = paciente.get("/chatbot")

    assert respuesta.status_code == 200
    assert "asistente automático" in respuesta.text
    assert "No reemplaza a tu médico" in respuesta.text
    assert 'name="pregunta"' in respuesta.text
    assert 'maxlength="1000"' in respuesta.text


def test_el_paciente_pregunta_y_ve_la_respuesta(paciente):
    respuesta = paciente.post("/chatbot", data={"pregunta": "¿Qué es un exoma clínico?"})

    assert respuesta.status_code == 200
    assert "¿Qué es un exoma clínico?" in respuesta.text
    assert RESPUESTA_DEL_MOCK in respuesta.text
    # Solo se guarda el id de la conversación en la sesión, no el texto.
    with paciente.session_transaction() as sesion:
        assert sesion[CLAVE_DE_CONVERSACION] == "00000000-0000-4000-8000-000000000001"
        assert not any("exoma" in str(valor) for valor in sesion.values())


def test_la_repregunta_sigue_la_misma_conversacion(paciente, chatbot_caido):
    falso = chatbot_caido(_ok(conversacion_id="conv-7"))

    paciente.post("/chatbot", data={"pregunta": "¿Qué es Pompe?"})
    segunda = paciente.post("/chatbot", data={"pregunta": "¿Y cómo se hereda?"})

    assert segunda.status_code == 200
    assert json.loads(falso.pedidos[0].content)["conversacion_id"] is None
    assert json.loads(falso.pedidos[1].content)["conversacion_id"] == "conv-7"
    assert "Seguí preguntando" in segunda.text


def test_nueva_conversacion_olvida_el_id(paciente):
    paciente.post("/chatbot", data={"pregunta": "Hola"})

    respuesta = paciente.post("/chatbot/nueva")

    assert respuesta.status_code == 302
    with paciente.session_transaction() as sesion:
        assert CLAVE_DE_CONVERSACION not in sesion


@pytest.mark.parametrize("pregunta", ["", "    ", "a" * 1001])
def test_una_pregunta_vacia_o_larga_responde_400(paciente, chatbot_caido, pregunta):
    falso = chatbot_caido(_ok())

    respuesta = paciente.post("/chatbot", data={"pregunta": pregunta})

    assert respuesta.status_code == 400
    assert "is-invalid" in respuesta.text
    assert falso.pedidos == []


@pytest.mark.parametrize(
    ("falla", "mensaje"),
    [
        (httpx.ReadTimeout("timed out"), NO_DISPONIBLE),
        (httpx.Response(500, json={"detail": "Error"}), NO_DISPONIBLE),
        (
            httpx.Response(503, json={"detail": "El chatbot está apagado hasta el lunes."}),
            "El chatbot está apagado hasta el lunes.",
        ),
        (httpx.Response(429, json={"detail": "Límite"}), DEMASIADAS_PREGUNTAS),
    ],
)
def test_si_el_chatbot_esta_caido_la_pantalla_muestra_un_aviso(
    paciente, chatbot_caido, falla, mensaje
):
    chatbot_caido(falla)

    respuesta = paciente.post("/chatbot", data={"pregunta": "¿Qué es Gaucher?"})

    assert respuesta.status_code == 200
    assert mensaje in respuesta.text
    # La pregunta queda escrita para volver a mandarla.
    assert "¿Qué es Gaucher?" in respuesta.text
    with paciente.session_transaction() as sesion:
        assert CLAVE_DE_CONVERSACION not in sesion


def test_un_401_no_le_muestra_el_problema_de_configuracion_al_paciente(paciente, chatbot_caido):
    chatbot_caido(httpx.Response(401, json={"detail": "Token inválido"}))

    respuesta = paciente.post("/chatbot", data={"pregunta": "Hola"})

    assert NO_DISPONIBLE in respuesta.text
    assert "Token inválido" not in respuesta.text
    assert "rechazó la clave" not in respuesta.text


# --- Acceso de cada rol ---


@pytest.mark.parametrize(
    "rol",
    [
        roles.MEDICO_TRATANTE,
        roles.ADMINISTRATIVO,
        roles.BIOINFORMATICO,
        roles.TRANSPORTISTA,
        roles.GERENTE_MEDICO,
        roles.ADMINISTRADOR_GENERAL,
    ],
)
def test_solo_el_paciente_entra_al_chatbot(login_como, rol):
    cliente = login_como(rol)

    assert cliente.get("/chatbot").status_code == 403
    assert cliente.post("/chatbot", data={"pregunta": "Hola"}).status_code == 403
    assert cliente.post("/chatbot/nueva").status_code == 403


def test_sin_sesion_el_chatbot_lleva_al_login(client):
    respuesta = client.get("/chatbot")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]
