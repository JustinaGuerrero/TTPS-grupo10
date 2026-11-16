"""Herramientas para probar a mano: `flask demo <estado>`, `flask migrar-local` y los seeds."""

import pytest
import sqlalchemy as sa

from src.core import demo, migraciones
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.pacientes import Paciente
from src.core.usuarios import buscar_por_email, listar_activos_por_rol, roles

# --- flask demo <estado> ---


@pytest.fixture
def con_seeds(app):
    resultado = app.test_cli_runner().invoke(args=["seeds"])
    assert resultado.exit_code == 0, resultado.output


def _estudio_de(app, email: str) -> tuple[EstadoEstudio, list[str]]:
    with app.app_context():
        usuario = buscar_por_email(email)
        estudio = db.session.scalars(
            sa.select(Estudio).join(Estudio.paciente).where(Paciente.usuario_id == usuario.id)
        ).one()
        historial = db.session.scalars(
            sa.select(HistorialEstado.estado_nuevo)
            .where(HistorialEstado.estudio_id == estudio.id)
            .order_by(HistorialEstado.id)
        ).all()
        return estudio.estado, [str(estado) for estado in historial]


def test_demo_habilitado_turno_crea_un_paciente_nuevo_con_el_historial_completo(app, con_seeds):
    resultado = app.test_cli_runner().invoke(args=["demo", "habilitado_turno"])

    assert resultado.exit_code == 0, resultado.output
    assert "en Habilitado para turno." in resultado.output
    assert "Paciente: demo.1@exoma.test" in resultado.output
    estado, historial = _estudio_de(app, "demo.1@exoma.test")
    assert estado == EstadoEstudio.HABILITADO_TURNO
    assert historial == ["creado", "presupuestado", "habilitado_turno"]

    # El paciente de demo entra con la contraseña de los seeds.
    respuesta = app.test_client().post(
        "/login",
        data={"email": "demo.1@exoma.test", "contrasena": app.config["SEEDS_CONTRASENA"]},
    )
    assert respuesta.status_code == 302


def test_cada_demo_es_un_paciente_nuevo(app, con_seeds):
    runner = app.test_cli_runner()
    runner.invoke(args=["demo", "creado"])

    resultado = runner.invoke(args=["demo", "creado"])

    assert "Paciente: demo.2@exoma.test" in resultado.output


def test_demo_de_un_estado_que_necesita_filas_de_otro_issue_lo_dice(app, con_seeds):
    resultado = app.test_cli_runner().invoke(args=["demo", "en_laboratorio_central"])

    assert resultado.exit_code != 0
    assert "falta el turno de extracción (#7), la muestra (#8)" in resultado.output
    with app.app_context():
        assert buscar_por_email("demo.1@exoma.test") is None


def test_demo_usa_datos_por_estado_cuando_el_issue_los_agrega(app, con_seeds, monkeypatch):
    vistos = []
    monkeypatch.setitem(
        demo.DATOS_POR_ESTADO,
        EstadoEstudio.TURNO_SACADO,
        lambda estudio: vistos.append(estudio.estado),
    )

    resultado = app.test_cli_runner().invoke(args=["demo", "turno_sacado"])

    assert resultado.exit_code == 0, resultado.output
    # La función corre con el estudio todavía en el estado anterior.
    assert vistos == [EstadoEstudio.HABILITADO_TURNO]


def test_demo_sin_seeds_pide_correrlos(app):
    resultado = app.test_cli_runner().invoke(args=["demo", "creado"])

    assert resultado.exit_code != 0
    assert "corré `flask seeds`" in resultado.output


def test_demo_rechaza_un_estado_desconocido(app):
    resultado = app.test_cli_runner().invoke(args=["demo", "volando"])

    assert resultado.exit_code != 0
    assert "Invalid value" in resultado.output


# --- Seeds: el paciente de prueba tiene su estudio en Creado ---


def test_seeds_deja_el_estudio_del_paciente_en_creado(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seeds"])
    runner.invoke(args=["seeds"])

    estado, historial = _estudio_de(app, "paciente@exoma.test")

    assert estado == EstadoEstudio.CREADO
    assert historial == ["creado"]


# --- flask migrar-local ---


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres.abc:clave@aws-0-sa-east-1.pooler.supabase.com:5432/postgres",
        "postgresql://postgres:clave@db.abc.supabase.co:5432/postgres",
    ],
)
def test_migrar_local_se_niega_con_una_url_de_supabase(app, monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL_LOCAL", url)

    resultado = app.test_cli_runner().invoke(args=["migrar-local", "--si"])

    assert resultado.exit_code != 0
    assert "la URL es de Supabase" in resultado.output


def test_migrar_local_se_niega_si_es_la_base_compartida(app, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:x@servidor:5432/compartida")
    monkeypatch.setenv("DATABASE_URL_LOCAL", "postgresql+psycopg://postgres:x@servidor/compartida")

    resultado = app.test_cli_runner().invoke(args=["migrar-local", "--si"])

    assert resultado.exit_code != 0
    assert "es la misma base que DATABASE_URL" in resultado.output


def test_migrar_local_sin_url_explica_que_falta(app, monkeypatch):
    monkeypatch.delenv("DATABASE_URL_LOCAL", raising=False)

    resultado = app.test_cli_runner().invoke(args=["migrar-local", "--si"])

    assert resultado.exit_code != 0
    assert "Falta DATABASE_URL_LOCAL" in resultado.output


def test_migrar_local_pide_confirmacion(app, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_LOCAL", "postgresql://postgres:x@localhost:5432/exoma_local")
    monkeypatch.setattr(migraciones, "aplicar_migraciones", pytest.fail)

    resultado = app.test_cli_runner().invoke(args=["migrar-local"], input="n\n")

    assert resultado.exit_code != 0
    assert "Se borran todos los datos" in resultado.output


def test_migrar_local_aplica_las_migraciones_en_una_base_local(app, monkeypatch):
    url_de_test = sa.make_url(app.config["DATABASE_URL"])
    url_local = url_de_test.set(database=f"{url_de_test.database}_migrar_local")
    texto = url_local.render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL_LOCAL", texto)
    try:
        resultado = app.test_cli_runner().invoke(args=["migrar-local", "--si"])

        assert resultado.exit_code == 0, resultado.output
        assert "aplicada  20261112041337_inicial.sql" in resultado.output
        motor = sa.create_engine(texto)
        with motor.connect() as conexion:
            provincias = conexion.scalar(sa.text("select count(*) from provincias"))
        motor.dispose()
        assert provincias == 24
    finally:
        _borrar_base(url_local)


def _borrar_base(url: sa.URL) -> None:
    motor = sa.create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with motor.connect() as conexion:
        nombre = conexion.dialect.identifier_preparer.quote(url.database)
        conexion.exec_driver_sql(f"drop database if exists {nombre} with (force)")
    motor.dispose()


# --- listar_activos_por_rol ---


def test_listar_activos_por_rol_deja_afuera_a_los_inactivos_y_a_otros_roles(app, usuario_rapido):
    with app.app_context():
        activo = usuario_rapido(roles.BIOINFORMATICO)
        inactivo = usuario_rapido(roles.BIOINFORMATICO)
        inactivo.activo = False
        usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()

        assert listar_activos_por_rol(roles.BIOINFORMATICO) == [activo]
        with pytest.raises(ValueError, match="Rol desconocido"):
            listar_activos_por_rol("jefe")
