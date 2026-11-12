def test_inicio_responde_200_con_el_layout(client):
    respuesta = client.get("/")

    assert respuesta.status_code == 200
    assert "Sistema de exoma clínico" in respuesta.text
    assert "· Exoma clínico</title>" in respuesta.text


def test_ruta_inexistente_muestra_pagina_404(client):
    respuesta = client.get("/no-existe")

    assert respuesta.status_code == 404
    assert "Página no encontrada" in respuesta.text


def test_error_inesperado_muestra_pagina_500(app):
    @app.get("/explota")
    def explota():
        raise RuntimeError("falla de prueba")

    # Sin propagar la excepción, como en producción, para que actúe el handler.
    app.config["PROPAGATE_EXCEPTIONS"] = False
    respuesta = app.test_client().get("/explota")

    assert respuesta.status_code == 500
    assert "Error del sistema" in respuesta.text
