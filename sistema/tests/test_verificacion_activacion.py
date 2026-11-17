"""Verificación de dispositivo y activación de la cuenta del paciente (E04, E05)."""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from conftest import CONTRASENA_DE_TEST, codigo_de_verificacion
from werkzeug.security import check_password_hash

from src.core.database import db
from src.core.usuarios import Usuario, buscar_por_email, roles
from src.core.usuarios.modelos import CodigoVerificacion, DispositivoConfiable
from src.integraciones.mail import mail


def _iniciar_sesion(client, email: str, contrasena: str = CONTRASENA_DE_TEST):
    with mail.record_messages() as enviados:
        respuesta = client.post("/login", data={"email": email, "contrasena": contrasena})
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/verificar"
    assert len(enviados) == 1
    return codigo_de_verificacion(enviados[0])


def test_dispositivo_nuevo_verifica_codigo_hash_y_confia_la_combinacion(app, client, crear_usuario):
    email = crear_usuario(roles.PACIENTE)
    codigo = _iniciar_sesion(client, email)
    cookie_de_sesion_pendiente = client.get_cookie("session").value

    protegido = client.get("/historial")

    assert protegido.status_code == 302
    assert protegido.headers["Location"] == "/verificar"
    assert client.get_cookie("exoma_dispositivo") is None

    respuesta = client.post("/verificar", data={"codigo": codigo})

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"
    assert client.get_cookie("session").value != cookie_de_sesion_pendiente
    cookie_dispositivo = client.get_cookie("exoma_dispositivo").value
    assert len(cookie_dispositivo) >= 40
    assert client.get("/").status_code == 200

    with app.app_context():
        usuario = buscar_por_email(email)
        registro_codigo = db.session.scalar(
            sa.select(CodigoVerificacion).where(CodigoVerificacion.usuario_id == usuario.id)
        )
        dispositivo = db.session.scalar(
            sa.select(DispositivoConfiable).where(DispositivoConfiable.usuario_id == usuario.id)
        )

    assert registro_codigo.codigo_hash != codigo
    assert registro_codigo.intentos == 0
    assert registro_codigo.usado_en is not None
    assert dispositivo.huella_hash != cookie_dispositivo
    assert dispositivo.huella_hash not in ("127.0.0.1", "")


def test_dispositivo_confiable_no_pide_codigo_y_otra_ip_si(app, client, crear_usuario):
    email = crear_usuario(roles.ADMINISTRATIVO)
    codigo = _iniciar_sesion(client, email)
    client.post("/verificar", data={"codigo": codigo})
    client.post("/logout")

    with mail.record_messages() as enviados:
        respuesta = client.post("/login", data={"email": email, "contrasena": CONTRASENA_DE_TEST})

    assert respuesta.headers["Location"] == "/"
    assert enviados == []
    client.post("/logout")

    with mail.record_messages() as enviados:
        nueva_red = client.post(
            "/login",
            data={"email": email, "contrasena": CONTRASENA_DE_TEST},
            environ_overrides={"REMOTE_ADDR": "203.0.113.17"},
        )

    assert nueva_red.headers["Location"] == "/verificar"
    assert len(enviados) == 1


def test_codigo_incorrecto_cinco_veces_deja_de_ser_valido(app, client, crear_usuario, monkeypatch):
    monkeypatch.setattr("src.core.usuarios.verificacion.secrets.randbelow", lambda _: 123456)
    email = crear_usuario(roles.PACIENTE)
    correcto = _iniciar_sesion(client, email)

    for _ in range(5):
        respuesta = client.post("/verificar", data={"codigo": "654321"})
        assert respuesta.status_code == 400

    assert client.post("/verificar", data={"codigo": correcto}).status_code == 400
    with app.app_context():
        registro = db.session.scalar(sa.select(CodigoVerificacion))
    assert registro.intentos == 5
    assert registro.usado_en is not None


def test_codigo_vencido_se_rechaza(app, client, crear_usuario):
    email = crear_usuario(roles.PACIENTE)
    codigo = _iniciar_sesion(client, email)

    with app.app_context():
        registro = db.session.scalar(sa.select(CodigoVerificacion))
        registro.expira_en = datetime.now(UTC) - timedelta(seconds=1)
        db.session.commit()

    respuesta = client.post("/verificar", data={"codigo": codigo})

    assert respuesta.status_code == 400
    assert "no es válido o venció" in respuesta.text


def test_reenviar_invalida_el_codigo_anterior(app, client, crear_usuario, monkeypatch):
    codigos = iter((111111, 222222))
    monkeypatch.setattr("src.core.usuarios.verificacion.secrets.randbelow", lambda _: next(codigos))
    email = crear_usuario(roles.PACIENTE)
    anterior = _iniciar_sesion(client, email)

    with mail.record_messages() as enviados:
        respuesta = client.post("/verificar/reenviar")

    assert respuesta.headers["Location"] == "/verificar"
    assert len(enviados) == 1
    nuevo = codigo_de_verificacion(enviados[0])
    assert nuevo != anterior
    assert client.post("/verificar", data={"codigo": anterior}).status_code == 400
    assert client.post("/verificar", data={"codigo": nuevo}).status_code == 302

    with app.app_context():
        registros = db.session.scalars(
            sa.select(CodigoVerificacion).order_by(CodigoVerificacion.id)
        ).all()
    assert len(registros) == 2
    assert all(registro.usado_en is not None for registro in registros)


def test_contrasena_provisoria_fuerza_cambio_y_permite_solo_logout_y_static(app, login_como):
    client = login_como(roles.PACIENTE)
    with client.session_transaction() as sesion:
        usuario_id = sesion["usuario_id"]
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        usuario.debe_cambiar_contrasena = True
        db.session.commit()

    assert client.get("/").headers["Location"] == "/cambiar-contrasena"
    assert client.get("/historial").headers["Location"] == "/cambiar-contrasena"
    assert client.get("/login").headers["Location"] == "/cambiar-contrasena"
    assert client.get("/static/vendor/bootstrap/css/bootstrap.min.css").status_code == 200
    assert client.post("/logout").headers["Location"] == "/login"


def test_contrasena_provisoria_no_se_puede_reutilizar_y_se_exige_confirmacion(app, login_como):
    client = login_como(roles.PACIENTE)
    with client.session_transaction() as sesion:
        usuario_id = sesion["usuario_id"]
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        usuario.debe_cambiar_contrasena = True
        hash_original = usuario.hash_contrasena
        db.session.commit()

    reutilizada = client.post(
        "/cambiar-contrasena",
        data={
            "contrasena": CONTRASENA_DE_TEST,
            "confirmar_contrasena": CONTRASENA_DE_TEST,
        },
    )
    corta = client.post(
        "/cambiar-contrasena",
        data={"contrasena": "corta", "confirmar_contrasena": "otra"},
    )

    assert reutilizada.status_code == 400
    assert "igual a la provisoria" in reutilizada.text
    assert corta.status_code == 400
    assert "al menos 8 caracteres" in corta.text
    assert "no coinciden" in corta.text
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.debe_cambiar_contrasena is True
        assert usuario.hash_contrasena == hash_original


def test_paciente_cambia_contrasena_y_llega_al_historial(app, client, crear_usuario):
    email = crear_usuario(roles.PACIENTE)
    with app.app_context():
        usuario = db.session.scalar(sa.select(Usuario).where(Usuario.email == email))
        usuario_id = usuario.id
        usuario.debe_cambiar_contrasena = True
        db.session.commit()

    codigo = _iniciar_sesion(client, email)
    respuesta = client.post("/verificar", data={"codigo": codigo})

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/cambiar-contrasena"
    assert client.get("/historial").headers["Location"] == "/cambiar-contrasena"

    respuesta = client.post(
        "/cambiar-contrasena",
        data={
            "contrasena": "paciente-segura-2026",
            "confirmar_contrasena": "paciente-segura-2026",
        },
    )

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/historial"
    assert client.get("/historial").status_code == 200
    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        assert usuario.debe_cambiar_contrasena is False
        assert check_password_hash(usuario.hash_contrasena, "paciente-segura-2026")
