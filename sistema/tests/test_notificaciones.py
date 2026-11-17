"""E39 Notificar: notificar() guarda el aviso y manda el mail, y "Mis avisos" en el layout."""

import smtplib

import pytest
import sqlalchemy as sa

from src.core.database import db
from src.core.notificaciones import (
    AVISOS_POR_PAGINA,
    Aviso,
    avisos_de,
    contar_sin_leer,
    marcar_leido,
    notificar,
)
from src.core.usuarios import Usuario, buscar_por_email, roles
from src.integraciones.mail import mail

# --- notificar() (episodios 1 a 3) ---


def test_notificar_guarda_el_aviso_y_manda_el_mail(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        with mail.record_messages() as enviados:
            aviso = notificar(
                medico, "Resultado disponible", "Ya está el resultado.", "/estudios/7"
            )
        db.session.commit()

        guardado = db.session.get(Aviso, aviso.id)
        assert guardado.usuario_id == medico.id
        assert guardado.asunto == "Resultado disponible"
        assert guardado.mensaje == "Ya está el resultado."
        assert guardado.link == "/estudios/7"
        assert guardado.estudio_id is None
        assert guardado.creada_en is not None
        assert guardado.mail_enviado_en is not None
        assert guardado.leida_en is None

    assert len(enviados) == 1
    assert enviados[0].recipients == [medico.email]
    assert enviados[0].subject == "Resultado disponible"
    assert "Ya está el resultado." in enviados[0].body
    # El mail lleva el link absoluto (URL_BASE de los tests es http://exoma.test).
    assert "http://exoma.test/estudios/7" in enviados[0].body
    assert enviados[0].sender == "Exoma clínico <no-responder@exoma.test>"


def test_notificar_puede_indicar_el_estudio_que_lo_origina(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio()

        aviso = notificar(
            estudio.medico_tratante.usuario, "Novedad", "Cambió el estudio.", "/", estudio=estudio
        )

        assert aviso.estudio_id == estudio.id


def test_si_el_mail_no_sale_el_aviso_se_guarda_igual(app, usuario_rapido, monkeypatch):
    def servidor_caido(mensaje):
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    monkeypatch.setattr(mail, "send", servidor_caido)
    with app.app_context():
        paciente = usuario_rapido(roles.PACIENTE)
        db.session.flush()

        aviso = notificar(paciente, "Turno", "Sacá tu turno de extracción.", "/turnos")
        db.session.commit()

        guardado = db.session.get(Aviso, aviso.id)
        assert guardado is not None
        assert guardado.mail_enviado_en is None
        assert contar_sin_leer(paciente) == 1


@pytest.mark.parametrize(
    ("asunto", "mensaje", "link"),
    [
        ("", "Mensaje", "/estudios/1"),
        ("Asunto", "   ", "/estudios/1"),
        ("Asunto", "Mensaje", ""),
        ("Asunto", "Mensaje", "estudios/1"),
        ("Asunto", "Mensaje", "https://otro-sitio.com"),
        ("Asunto", "Mensaje", "//otro-sitio.com"),
    ],
)
def test_notificar_rechaza_datos_invalidos(app, usuario_rapido, asunto, mensaje, link):
    with app.app_context():
        usuario = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        with mail.record_messages() as enviados, pytest.raises(ValueError):
            notificar(usuario, asunto, mensaje, link)

        assert enviados == []


# --- Consultar los avisos (episodio 4) ---


def test_contar_sin_leer_y_marcar_leido(app, usuario_rapido):
    with app.app_context():
        ana, beto = usuario_rapido(roles.PACIENTE), usuario_rapido(roles.PACIENTE)
        db.session.flush()
        primero = notificar(ana, "Uno", "Primer aviso.", "/")
        notificar(ana, "Dos", "Segundo aviso.", "/")
        notificar(beto, "Otro", "Aviso de Beto.", "/")

        assert contar_sin_leer(ana) == 2
        assert marcar_leido(primero.id, beto) is None
        assert contar_sin_leer(ana) == 2

        leido = marcar_leido(primero.id, ana)
        assert leido is primero
        assert leido.leida_en is not None
        assert contar_sin_leer(ana) == 1
        assert contar_sin_leer(beto) == 1

        # Abrirlo de nuevo no cambia cuándo se leyó.
        fecha = leido.leida_en
        assert marcar_leido(primero.id, ana).leida_en == fecha


def test_marcar_leido_un_aviso_inexistente_devuelve_none(app, usuario_rapido):
    with app.app_context():
        usuario = usuario_rapido(roles.PACIENTE)
        db.session.flush()

        assert marcar_leido(999_999, usuario) is None


def test_avisos_de_pagina_los_mas_nuevos_primero(app, usuario_rapido):
    with app.app_context():
        usuario = usuario_rapido(roles.BIOINFORMATICO)
        db.session.flush()
        for numero in range(1, AVISOS_POR_PAGINA + 2):
            notificar(usuario, f"Aviso {numero}", "Mensaje.", "/")

        primera = avisos_de(usuario)
        segunda = avisos_de(usuario, pagina=2)

    assert primera.total == AVISOS_POR_PAGINA + 1
    assert len(primera.items) == AVISOS_POR_PAGINA
    assert primera.items[0].asunto == f"Aviso {AVISOS_POR_PAGINA + 1}"
    assert not primera.hay_anterior
    assert primera.hay_siguiente
    assert [aviso.asunto for aviso in segunda.items] == ["Aviso 1"]
    assert segunda.hay_anterior
    assert not segunda.hay_siguiente


# --- Pantalla "Mis avisos" y layout ---


@pytest.fixture
def entrar(crear_usuario, app, autenticar_como):
    """Fábrica: `entrar(rol)` loguea a un usuario nuevo de ese rol y devuelve su id."""

    def _entrar(rol: str = roles.PACIENTE) -> int:
        email = crear_usuario(rol)
        autenticar_como(email)
        with app.app_context():
            return buscar_por_email(email).id

    return _entrar


def _notificar_a(app, usuario_id: int, asunto: str, link: str = "/") -> int:
    with app.app_context():
        aviso = notificar(
            db.session.get(Usuario, usuario_id), asunto, f"Mensaje de {asunto}.", link
        )
        db.session.commit()
        return aviso.id


def test_mis_avisos_pide_iniciar_sesion(client):
    respuesta = client.get("/avisos")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].startswith("/login")


def test_el_layout_muestra_mis_avisos_con_la_cantidad_sin_leer(app, client, entrar):
    usuario_id = entrar(roles.TRANSPORTISTA)

    sin_avisos = client.get("/")
    _notificar_a(app, usuario_id, "Retiro pendiente")
    _notificar_a(app, usuario_id, "Otro retiro")
    con_avisos = client.get("/")

    assert "Mis avisos" in sin_avisos.text
    assert 'id="avisos-sin-leer"' not in sin_avisos.text
    assert 'id="avisos-sin-leer"' in con_avisos.text
    assert '2<span class="visually-hidden"> sin leer</span>' in con_avisos.text


def test_mis_avisos_muestra_solo_los_del_usuario(app, client, entrar, usuario_rapido):
    usuario_id = entrar(roles.MEDICO_TRATANTE)
    _notificar_a(app, usuario_id, "Aviso para mí")
    with app.app_context():
        otro = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()
        notificar(otro, "Aviso para otro", "No es mío.", "/")
        db.session.commit()

    respuesta = client.get("/avisos")

    assert respuesta.status_code == 200
    assert "Aviso para mí" in respuesta.text
    assert "Mensaje de Aviso para mí." in respuesta.text
    assert "Aviso para otro" not in respuesta.text


def test_mis_avisos_sin_avisos(client, entrar):
    entrar(roles.GERENTE_MEDICO)

    respuesta = client.get("/avisos")

    assert respuesta.status_code == 200
    assert "No tenés avisos." in respuesta.text


def test_abrir_un_aviso_lo_marca_leido_y_lleva_a_la_tarea(app, client, entrar):
    usuario_id = entrar(roles.ADMINISTRATIVO)
    aviso_id = _notificar_a(app, usuario_id, "Presupuestar estudio", link="/estudios/42")

    respuesta = client.post(f"/avisos/{aviso_id}/abrir")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/estudios/42"
    with app.app_context():
        assert db.session.get(Aviso, aviso_id).leida_en is not None
    assert 'id="avisos-sin-leer"' not in client.get("/").text


def test_abrir_un_aviso_de_otro_usuario_da_404(app, client, entrar, usuario_rapido):
    entrar(roles.PACIENTE)
    with app.app_context():
        otro = usuario_rapido(roles.PACIENTE)
        db.session.flush()
        aviso_id = notificar(otro, "Ajeno", "No es tuyo.", "/").id
        db.session.commit()

    respuesta = client.post(f"/avisos/{aviso_id}/abrir")

    assert respuesta.status_code == 404
    with app.app_context():
        assert db.session.get(Aviso, aviso_id).leida_en is None


def test_abrir_un_aviso_con_link_externo_no_sale_del_sistema(app, client, entrar):
    usuario_id = entrar(roles.PACIENTE)
    # notificar() no lo permite; se guarda a mano para probar la defensa del controlador.
    with app.app_context():
        aviso = Aviso(usuario_id=usuario_id, asunto="Raro", mensaje="Link raro.", link="//otro.com")
        db.session.add(aviso)
        db.session.commit()
        aviso_id = aviso.id

    respuesta = client.post(f"/avisos/{aviso_id}/abrir")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/avisos"


def test_la_tabla_rechaza_links_que_no_son_rutas(app, usuario_rapido):
    with app.app_context():
        usuario = usuario_rapido(roles.PACIENTE)
        db.session.flush()
        db.session.add(
            Aviso(usuario_id=usuario.id, asunto="A", mensaje="M", link="https://otro.com")
        )

        with pytest.raises(sa.exc.IntegrityError):
            db.session.flush()
