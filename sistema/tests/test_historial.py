"""E11 Consultar historial de estudios: paciente y médico tratante, con estudios propios y ajenos.

Los estudios salen de la fábrica crear_estudio en el estado que necesita cada test. El PDF del
resultado lo genera #20: acá se sube uno de prueba con el mock de Storage (USE_MOCKS=1).
"""

from datetime import UTC, datetime

import pytest

from src.core.database import db
from src.core.estudios import Analisis, EstadoEstudio, TipoAnalisis, cambiar_estado
from src.core.estudios import crear_estudio as crear_estudio_en_core
from src.core.historial import (
    BusquedaDeEstudios,
    analisis_visible,
    estudio_del_paciente,
    estudio_visible,
    estudios_del_medico,
    puede_ver,
)
from src.core.usuarios import roles
from src.integraciones import storage

PDF_DE_PRUEBA = b"%PDF-1.4\n% resultado de prueba\n%%EOF\n"
OTROS_ROLES = [
    roles.ADMINISTRATIVO,
    roles.BIOINFORMATICO,
    roles.TRANSPORTISTA,
    roles.GERENTE_MEDICO,
    roles.ADMINISTRADOR_GENERAL,
]


@pytest.fixture
def storage_mock(app, tmp_path):
    """Los archivos del mock de Storage van a una carpeta temporal de este test."""
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)
    return tmp_path


@pytest.fixture
def entrar_como(client):
    """Inicia la sesión de `client` como `usuario` (los de las fábricas no tienen contraseña)."""

    def _entrar(usuario):
        with client.session_transaction() as sesion:
            sesion["usuario_id"] = usuario.id
        return client

    return _entrar


@pytest.fixture
def contexto(app):
    """Un solo app_context para todo el test: dos anidados se pisarían los savepoints de la base."""
    with app.app_context():
        yield


@pytest.fixture
def estudio(contexto, crear_estudio):
    """Un estudio En análisis, para los tests que no dependen del estado."""
    return crear_estudio(EstadoEstudio.EN_ANALISIS)


@pytest.fixture
def ajeno(contexto, crear_estudio):
    """Estudio de otro paciente y de otro médico tratante."""
    return crear_estudio(EstadoEstudio.CREADO)


def _paciente(estudio):
    return estudio.paciente.usuario


def _medico(estudio):
    return estudio.medico_tratante.usuario


def _finalizar(estudio, resultado="positivo", con_pdf=True):
    """Deja el análisis inicial con resultado y, si se pide, con su PDF en Storage (lo hace #20)."""
    analisis = estudio.analisis_actual
    analisis.resultado = resultado
    analisis.finalizado_en = datetime.now(UTC)
    if con_pdf:
        analisis.resultado_path = storage.subir(
            f"estudios/{estudio.id}/resultado-{analisis.numero}.pdf", PDF_DE_PRUEBA
        )
    db.session.commit()
    return analisis


# --- Episodios 1 y 2: el historial con el estado actual ---


def test_el_paciente_ve_su_estudio_con_el_estado_actual(estudio, entrar_como):
    respuesta = entrar_como(_paciente(estudio)).get("/historial")

    assert respuesta.status_code == 200
    assert estudio.codigo in respuesta.text
    assert "En análisis" in respuesta.text
    assert f"/historial/estudios/{estudio.id}" in respuesta.text


def test_el_paciente_no_ve_estudios_ajenos_en_su_historial(estudio, ajeno, entrar_como):
    respuesta = entrar_como(_paciente(estudio)).get("/historial")

    assert ajeno.codigo not in respuesta.text


def test_el_paciente_sin_estudio_ve_un_aviso(app, login_como):
    respuesta = login_como(roles.PACIENTE).get("/historial")

    assert respuesta.status_code == 200
    assert "Todavía no tenés un estudio" in respuesta.text


def test_el_medico_ve_los_estudios_de_sus_pacientes_y_no_los_de_otro(estudio, ajeno, entrar_como):
    respuesta = entrar_como(_medico(estudio)).get("/historial")

    assert respuesta.status_code == 200
    assert estudio.codigo in respuesta.text
    assert estudio.paciente.dni in respuesta.text
    assert ajeno.codigo not in respuesta.text


def test_el_medico_busca_por_dni_o_por_nombre(app, crear_estudio, crear_paciente, entrar_como):
    with app.app_context():
        primero = crear_estudio(EstadoEstudio.CREADO)
        medico = _medico(primero)
        # Segundo estudio del mismo médico tratante, de un paciente con otro apellido y DNI.
        otro = crear_paciente()
        otro.usuario.apellido = "Zárate"
        segundo = crear_estudio_en_core(
            otro, medico, genes=["GLA"], evalua_hallazgos_secundarios=False
        )
        db.session.commit()

        cliente = entrar_como(medico)
        por_dni = cliente.get("/historial", query_string={"texto": primero.paciente.dni[-4:]})
        por_nombre = cliente.get("/historial", query_string={"texto": "zára"})
        sin_resultados = cliente.get("/historial", query_string={"texto": "inexistente"})

    assert primero.codigo in por_dni.text and segundo.codigo not in por_dni.text
    assert segundo.codigo in por_nombre.text and primero.codigo not in por_nombre.text
    assert "Ningún estudio coincide con la búsqueda" in sin_resultados.text


# --- Episodios 3 y 4: el detalle del estudio ---


def test_el_detalle_muestra_estado_linea_de_tiempo_y_analisis(estudio, entrar_como):
    respuesta = entrar_como(_paciente(estudio)).get(f"/historial/estudios/{estudio.id}")

    assert respuesta.status_code == 200
    assert estudio.codigo in respuesta.text
    # Cada cambio del historial_estados, con el nombre del LEL.
    for cambio in estudio.historial:
        assert cambio.estado_nuevo.nombre in respuesta.text
    assert "Análisis inicial" in respuesta.text
    assert "GAA" in respuesta.text
    assert "Sin resultado todavía" in respuesta.text
    assert "Descargar resultado" not in respuesta.text


def test_el_medico_ve_el_detalle_de_su_paciente(estudio, entrar_como):
    respuesta = entrar_como(_medico(estudio)).get(f"/historial/estudios/{estudio.id}")

    assert respuesta.status_code == 200
    assert estudio.paciente.dni in respuesta.text


@pytest.mark.parametrize("quien", [_paciente, _medico])
def test_un_estudio_ajeno_o_inexistente_responde_404(estudio, ajeno, entrar_como, quien):
    cliente = entrar_como(quien(estudio))

    assert cliente.get(f"/historial/estudios/{ajeno.id}").status_code == 404
    assert cliente.get("/historial/estudios/999999999").status_code == 404


def test_finalizado_con_resultado_muestra_el_resultado_y_la_descarga(
    app, crear_estudio, storage_mock, entrar_como
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.FINALIZADO)
        analisis = _finalizar(estudio, resultado="portador")
        cliente = entrar_como(_paciente(estudio))

        detalle = cliente.get(f"/historial/estudios/{estudio.id}")
        descarga = cliente.get(f"/historial/analisis/{analisis.id}/resultado")

    assert "Finalizado" in detalle.text
    assert "Resultado: Portador" in detalle.text
    assert f"/historial/analisis/{analisis.id}/resultado" in detalle.text
    assert descarga.status_code == 200
    assert descarga.mimetype == "application/pdf"
    assert descarga.data == PDF_DE_PRUEBA
    assert "attachment" in descarga.headers["Content-Disposition"]
    assert f"{estudio.codigo}-resultado-1.pdf" in descarga.headers["Content-Disposition"]
    assert descarga.headers["Cache-Control"] == "no-store"


def test_el_medico_descarga_el_resultado_de_su_paciente(
    app, crear_estudio, storage_mock, entrar_como
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.FINALIZADO)
        analisis = _finalizar(estudio)
        descarga = entrar_como(_medico(estudio)).get(f"/historial/analisis/{analisis.id}/resultado")

    assert descarga.status_code == 200
    assert descarga.data == PDF_DE_PRUEBA


def test_finalizado_sin_pdf_no_muestra_la_descarga_y_responde_404(app, crear_estudio, entrar_como):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.FINALIZADO)
        analisis = _finalizar(estudio, resultado="negativo", con_pdf=False)
        cliente = entrar_como(_paciente(estudio))

        detalle = cliente.get(f"/historial/estudios/{estudio.id}")
        descarga = cliente.get(f"/historial/analisis/{analisis.id}/resultado")

    assert "Resultado: Negativo" in detalle.text
    assert "Descargar resultado" not in detalle.text
    assert "El PDF del resultado todavía no está disponible" in detalle.text
    assert descarga.status_code == 404


def test_un_estudio_en_analisis_no_tiene_descarga(estudio, entrar_como):
    cliente = entrar_como(_paciente(estudio))

    respuesta = cliente.get(f"/historial/analisis/{estudio.analisis_actual.id}/resultado")

    assert respuesta.status_code == 404


@pytest.mark.parametrize("quien", [_paciente, _medico])
def test_la_descarga_de_un_resultado_ajeno_responde_404(
    app, crear_estudio, storage_mock, entrar_como, quien
):
    with app.app_context():
        propio = crear_estudio(EstadoEstudio.CREADO)
        ajeno = crear_estudio(EstadoEstudio.FINALIZADO)
        analisis = _finalizar(ajeno)
        respuesta = entrar_como(quien(propio)).get(f"/historial/analisis/{analisis.id}/resultado")

    assert respuesta.status_code == 404
    assert PDF_DE_PRUEBA not in respuesta.data


def test_si_el_pdf_no_esta_en_storage_vuelve_al_detalle_con_un_aviso(
    app, crear_estudio, storage_mock, entrar_como
):
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.FINALIZADO)
        analisis = _finalizar(estudio, con_pdf=False)
        analisis.resultado_path = f"estudios/{estudio.id}/no-existe.pdf"
        db.session.commit()
        cliente = entrar_como(_paciente(estudio))

        respuesta = cliente.get(
            f"/historial/analisis/{analisis.id}/resultado", follow_redirects=True
        )

    assert respuesta.status_code == 200
    assert respuesta.request.path == f"/historial/estudios/{estudio.id}"
    assert "El PDF del resultado todavía no está disponible." in respuesta.text


def test_con_un_reanalisis_en_curso_se_ve_el_resultado_del_analisis_anterior(
    app, crear_estudio, storage_mock, entrar_como
):
    """O20: un solo estudio con sus análisis. El reanálisis (E12, #21) lo arma acá el test."""
    with app.app_context():
        estudio = crear_estudio(EstadoEstudio.FINALIZADO)
        inicial = _finalizar(estudio)
        medico = _medico(estudio)
        db.session.add(
            Analisis(
                estudio=estudio,
                numero=2,
                tipo=TipoAnalisis.REANALISIS,
                evalua_hallazgos_secundarios=False,
                solicitado_por=medico.id,
            )
        )
        cambiar_estado(estudio, EstadoEstudio.EN_AREA_BIOINFORMATICA, medico)
        db.session.commit()

        respuesta = entrar_como(_paciente(estudio)).get(f"/historial/estudios/{estudio.id}")

    assert "En área de bioinformática" in respuesta.text
    assert "Reanálisis 1" in respuesta.text
    assert "Análisis inicial" in respuesta.text
    assert "Resultado: Positivo" in respuesta.text
    assert f"/historial/analisis/{inicial.id}/resultado" in respuesta.text


# --- Acceso de cada rol ---


@pytest.mark.parametrize("rol", OTROS_ROLES)
def test_los_otros_roles_no_entran_al_historial(estudio, login_como, rol):
    cliente = login_como(rol)

    assert cliente.get("/historial").status_code == 403
    assert cliente.get(f"/historial/estudios/{estudio.id}").status_code == 403
    assert (
        cliente.get(f"/historial/analisis/{estudio.analisis_actual.id}/resultado").status_code
        == 403
    )


def test_sin_sesion_el_historial_lleva_al_login(client):
    respuesta = client.get("/historial")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


def test_el_menu_muestra_el_historial_al_paciente_y_al_medico(estudio, entrar_como):
    del_paciente = entrar_como(_paciente(estudio)).get("/historial").text
    assert "Mi estudio" in del_paciente
    assert 'href="/chatbot"' in del_paciente

    del_medico = entrar_como(_medico(estudio)).get("/historial").text
    assert "Estudios" in del_medico
    assert 'href="/chatbot"' not in del_medico


# --- Core: consultas de solo lectura ---


def test_core_estudio_del_paciente(estudio, usuario_rapido):
    assert estudio_del_paciente(_paciente(estudio)).id == estudio.id
    assert estudio_del_paciente(usuario_rapido(roles.PACIENTE)) is None


def test_core_puede_ver_solo_el_paciente_y_su_medico(estudio, ajeno, usuario_rapido):
    assert puede_ver(_paciente(estudio), estudio)
    assert puede_ver(_medico(estudio), estudio)
    assert not puede_ver(_paciente(ajeno), estudio)
    assert not puede_ver(_medico(ajeno), estudio)
    for rol in OTROS_ROLES:
        assert not puede_ver(usuario_rapido(rol), estudio)


def test_core_un_estudio_o_analisis_ajeno_es_none(estudio, ajeno):
    assert estudio_visible(_paciente(estudio), estudio.id).id == estudio.id
    assert estudio_visible(_paciente(estudio), ajeno.id) is None
    assert estudio_visible(_paciente(estudio), 999999999) is None
    assert analisis_visible(_medico(estudio), estudio.analisis_actual.id) is not None
    assert analisis_visible(_medico(estudio), ajeno.analisis_actual.id) is None


def test_core_estudios_del_medico_pagina(estudio):
    pagina = estudios_del_medico(_medico(estudio), BusquedaDeEstudios(), por_pagina=1)

    assert pagina.total == 1
    assert [e.id for e in pagina.items] == [estudio.id]


def test_la_busqueda_descarta_parametros_invalidos():
    busqueda = BusquedaDeEstudios.desde({"texto": "  ana   gómez ", "pagina": "x"})

    assert busqueda.texto == "ana gómez"
    assert busqueda.pagina == 1
    assert busqueda.parametros(pagina=3) == {"texto": "ana gómez", "pagina": 3}
