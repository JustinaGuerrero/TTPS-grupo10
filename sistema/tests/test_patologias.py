"""Tests de E36 (alta y modificación de patologías) y de sus permisos."""

import pytest

from src.core.patologias import buscar_por_codigo, buscar_por_id
from src.core.snomed import buscar_termino
from src.core.usuarios import roles
from src.integraciones import apigen
from src.integraciones.base import ErrorDeIntegracion


def _formulario_de_alta(**cambios) -> dict:
    datos = {
        "nombre": "Enfermedad nueva",
        "codigo_apigen": "NUEVA",
        "herencia": "autosomica_recesiva",
        "genes": "GLA, GAA",
        "cardinal": "S1|Síntoma uno",
        "secundarios": ["S2|Síntoma dos", "S3|Síntoma tres"],
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def apigen_responde(monkeypatch):
    """El alta en Apigen funciona: no se llama a la API."""
    monkeypatch.setattr(apigen, "alta_patologia", lambda *args, **kwargs: None)


# --- permisos --------------------------------------------------------------------------------


def test_sin_sesion_redirige_al_login(client):
    assert client.get("/patologias").status_code == 302


@pytest.mark.parametrize("rol", [roles.MEDICO_TRATANTE, roles.ADMINISTRATIVO, roles.PACIENTE])
def test_otros_roles_no_entran(login_como, rol):
    cliente = login_como(rol)
    assert cliente.get("/patologias").status_code == 403
    assert cliente.get("/patologias/nueva").status_code == 403
    assert cliente.post("/patologias/nueva", data=_formulario_de_alta()).status_code == 403


def test_el_gerente_medico_ve_el_listado(app, login_como, crear_patologia):
    with app.app_context():
        crear_patologia(nombre="Patología visible")
    respuesta = login_como(roles.GERENTE_MEDICO).get("/patologias")
    assert respuesta.status_code == 200
    assert "Patología visible" in respuesta.get_data(as_text=True)


# --- alta (E36.1 a E36.4) --------------------------------------------------------------------


def test_alta_guarda_la_patologia_con_sus_sintomas(app, login_como, apigen_responde):
    respuesta = login_como(roles.GERENTE_MEDICO).post(
        "/patologias/nueva", data=_formulario_de_alta()
    )
    assert respuesta.status_code == 302

    with app.app_context():
        patologia = buscar_por_codigo("NUEVA")
        assert patologia is not None
        assert patologia.cardinal == "S1"
        assert patologia.secundarios == {"S2", "S3"}
        assert buscar_termino("S1").termino == "Síntoma uno"


def test_alta_sin_sintoma_cardinal_se_rechaza(app, login_como, apigen_responde):
    respuesta = login_como(roles.GERENTE_MEDICO).post(
        "/patologias/nueva", data=_formulario_de_alta(cardinal="")
    )
    assert respuesta.status_code == 400
    assert "Falta el síntoma cardinal" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert buscar_por_codigo("NUEVA") is None


def test_alta_con_dos_cardinales_se_rechaza(app, login_como, apigen_responde):
    respuesta = login_como(roles.GERENTE_MEDICO).post(
        "/patologias/nueva", data=_formulario_de_alta(cardinal=["S1|Uno", "S2|Dos"], secundarios=[])
    )
    assert respuesta.status_code == 400
    assert "un solo síntoma cardinal" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert buscar_por_codigo("NUEVA") is None


def test_alta_con_codigo_repetido_se_rechaza(app, login_como, crear_patologia, apigen_responde):
    with app.app_context():
        crear_patologia()  # código PAT_1
    respuesta = login_como(roles.GERENTE_MEDICO).post(
        "/patologias/nueva", data=_formulario_de_alta(codigo_apigen="PAT_1")
    )
    assert respuesta.status_code == 400
    assert "Ya existe una patología con ese código" in respuesta.get_data(as_text=True)


def test_si_apigen_falla_no_queda_nada_guardado(app, login_como, monkeypatch):
    def apigen_caido(*args, **kwargs):
        raise ErrorDeIntegracion("Apigen", "Apigen no respondió a tiempo.")

    monkeypatch.setattr(apigen, "alta_patologia", apigen_caido)

    respuesta = login_como(roles.GERENTE_MEDICO).post(
        "/patologias/nueva", data=_formulario_de_alta()
    )
    assert respuesta.status_code == 503
    assert "Apigen no respondió a tiempo." in respuesta.get_data(as_text=True)
    with app.app_context():
        assert buscar_por_codigo("NUEVA") is None
        assert buscar_termino("S1") is None


# --- modificación de síntomas (E36.5) --------------------------------------------------------


def test_modificar_cambia_el_cardinal_y_los_secundarios(app, login_como, crear_patologia):
    with app.app_context():
        patologia = crear_patologia(
            cardinal=("S1", "Síntoma uno"), secundarios=(("S2", "Síntoma dos"),)
        )
        patologia_id, codigo = patologia.id, patologia.codigo_apigen

    respuesta = login_como(roles.GERENTE_MEDICO).post(
        f"/patologias/{patologia_id}/editar",
        # El cardinal anterior pasa a secundario y entra un cardinal nuevo.
        data={"cardinal": "S3|Síntoma tres", "secundarios": ["S1|Síntoma uno"]},
    )
    assert respuesta.status_code == 302

    with app.app_context():
        patologia = buscar_por_codigo(codigo)
        assert patologia.cardinal == "S3"
        assert patologia.secundarios == {"S1"}


def test_modificar_sin_cardinal_se_rechaza_y_no_cambia_nada(app, login_como, crear_patologia):
    with app.app_context():
        patologia = crear_patologia(cardinal=("S1", "Síntoma uno"))
        patologia_id, codigo = patologia.id, patologia.codigo_apigen

    respuesta = login_como(roles.GERENTE_MEDICO).post(
        f"/patologias/{patologia_id}/editar", data={"cardinal": "", "secundarios": ["S2|Dos"]}
    )
    assert respuesta.status_code == 400
    with app.app_context():
        assert buscar_por_codigo(codigo).cardinal == "S1"


def test_editar_una_patologia_inexistente_da_404(login_como):
    assert login_como(roles.GERENTE_MEDICO).get("/patologias/999999/editar").status_code == 404


# --- activar y desactivar --------------------------------------------------------------------


def test_el_gerente_desactiva_y_reactiva_una_patologia(app, login_como, crear_patologia):
    with app.app_context():
        patologia = crear_patologia()
        patologia_id = patologia.id

    cliente = login_como(roles.GERENTE_MEDICO)
    assert cliente.post(f"/patologias/{patologia_id}/activa").status_code == 302
    with app.app_context():
        assert buscar_por_id(patologia_id).activa is False

    assert cliente.post(f"/patologias/{patologia_id}/activa").status_code == 302
    with app.app_context():
        assert buscar_por_id(patologia_id).activa is True


@pytest.mark.parametrize("rol", [roles.MEDICO_TRATANTE, roles.ADMINISTRATIVO, roles.PACIENTE])
def test_otros_roles_no_pueden_activar_ni_editar(app, login_como, crear_patologia, rol):
    with app.app_context():
        patologia = crear_patologia()
        patologia_id = patologia.id

    cliente = login_como(rol)
    assert cliente.post(f"/patologias/{patologia_id}/activa").status_code == 403
    assert cliente.get(f"/patologias/{patologia_id}/editar").status_code == 403
    assert (
        cliente.post(
            f"/patologias/{patologia_id}/editar",
            data={"cardinal": "S9|Nuevo", "secundarios": []},
        ).status_code
        == 403
    )

    # El 403 no tiene que haber cambiado nada.
    with app.app_context():
        assert buscar_por_id(patologia_id).activa is True


def test_activar_una_patologia_inexistente_da_404(login_como):
    assert login_como(roles.GERENTE_MEDICO).post("/patologias/999999/activa").status_code == 404


def test_el_listado_muestra_el_boton_y_el_estado(app, login_como, crear_patologia):
    with app.app_context():
        patologia = crear_patologia(nombre="Patología botón")
        patologia_id = patologia.id

    cliente = login_como(roles.GERENTE_MEDICO)
    html = cliente.get("/patologias").get_data(as_text=True)
    assert 'text-bg-success">Activa<' in html
    assert "Desactivar" in html
    assert f"/patologias/{patologia_id}/activa" in html

    cliente.post(f"/patologias/{patologia_id}/activa")
    html = cliente.get("/patologias").get_data(as_text=True)
    assert 'text-bg-secondary">Inactiva<' in html
    assert "Desactivar" not in html
    assert "Activar" in html
