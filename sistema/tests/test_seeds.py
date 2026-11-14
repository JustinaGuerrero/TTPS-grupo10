"""`flask seeds`: un usuario de prueba por cada uno de los 7 roles del LEL."""

import sqlalchemy as sa

from src.core.database import db
from src.core.pacientes import Paciente
from src.core.seeds import USUARIOS_DE_PRUEBA
from src.core.usuarios import Medico, Rol, Usuario, roles

UNO_POR_ROL = {rol: 1 for rol in roles.TODOS}


def _perfiles(app) -> tuple[set[str], list[tuple[str, str]]]:
    """Mails con perfil de médico y (mail del paciente, mail de su médico tratante)."""
    with app.app_context():
        medicos = set(db.session.scalars(sa.select(Usuario.email).join(Medico)))
        pacientes = [
            (paciente.usuario.email, paciente.medico_tratante.usuario.email)
            for paciente in db.session.scalars(sa.select(Paciente))
        ]
    return medicos, pacientes


def _lineas_que_empiezan_con(salida: str, estado: str) -> int:
    return sum(linea.startswith(estado) for linea in salida.splitlines())


def _usuarios_por_rol(app) -> dict[str, int]:
    consulta = sa.select(Usuario.rol_codigo, sa.func.count()).group_by(Usuario.rol_codigo)
    with app.app_context():
        return dict(db.session.execute(consulta).all())


def test_seeds_crea_un_usuario_por_cada_rol_del_lel(app):
    resultado = app.test_cli_runner().invoke(args=["seeds"])

    assert resultado.exit_code == 0, resultado.output
    assert _lineas_que_empiezan_con(resultado.output, "creado") == 7
    assert _usuarios_por_rol(app) == UNO_POR_ROL


def test_seeds_se_puede_correr_dos_veces(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seeds"])

    segunda = runner.invoke(args=["seeds"])

    assert segunda.exit_code == 0, segunda.output
    assert _lineas_que_empiezan_con(segunda.output, "ya existía") == 7
    assert _usuarios_por_rol(app) == UNO_POR_ROL
    medicos, pacientes = _perfiles(app)
    assert len(medicos) == 2
    assert len(pacientes) == 1


def test_seeds_crea_los_perfiles_de_medico_y_de_paciente(app):
    app.test_cli_runner().invoke(args=["seeds"])

    medicos, pacientes = _perfiles(app)

    assert medicos == {"medico@exoma.test", "gerente@exoma.test"}
    assert pacientes == [("paciente@exoma.test", "medico@exoma.test")]


def test_cada_usuario_de_prueba_inicia_sesion_y_ve_su_rol(app):
    app.test_cli_runner().invoke(args=["seeds"])
    contrasena = app.config["SEEDS_CONTRASENA"]
    with app.app_context():
        nombre_del_rol = dict(db.session.execute(sa.select(Rol.codigo, Rol.nombre)).all())

    for email, nombre, apellido, rol in USUARIOS_DE_PRUEBA:
        client = app.test_client()
        respuesta = client.post("/login", data={"email": email, "contrasena": contrasena})

        assert respuesta.status_code == 302, email
        inicio = client.get("/").text
        assert f"{nombre} {apellido}" in inicio
        assert nombre_del_rol[rol] in inicio


def test_seeds_sin_contrasena_no_crea_usuarios(app):
    app.config["SEEDS_CONTRASENA"] = None

    resultado = app.test_cli_runner().invoke(args=["seeds"])

    assert resultado.exit_code != 0
    assert "Falta SEEDS_CONTRASENA" in resultado.output
    assert _usuarios_por_rol(app) == {}
