from src.core.usuarios import roles


def test_inicio_muestra_el_layout_con_bootstrap_local(login_como):
    client = login_como(roles.ADMINISTRATIVO)

    respuesta = client.get("/")

    assert respuesta.status_code == 200
    assert "Hola, Nombre" in respuesta.text
    assert "· Exoma clínico</title>" in respuesta.text
    assert 'name="viewport"' in respuesta.text
    assert "/static/vendor/bootstrap/css/bootstrap.min.css" in respuesta.text
    assert "/static/vendor/bootstrap/js/bootstrap.bundle.min.js" in respuesta.text


def test_bootstrap_se_sirve_localmente_sin_sesion(client):
    css = client.get("/static/vendor/bootstrap/css/bootstrap.min.css")
    js = client.get("/static/vendor/bootstrap/js/bootstrap.bundle.min.js")

    assert css.status_code == 200
    assert b"Bootstrap  v5.3.8" in css.data
    assert js.status_code == 200
    css.close()
    js.close()


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
