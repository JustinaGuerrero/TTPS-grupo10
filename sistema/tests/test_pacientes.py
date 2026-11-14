"""Modelo mínimo del paciente (datos de E06) y perfil de médico que lo da de alta."""

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.database import db
from src.core.pacientes import Paciente, TipoSospecha
from src.core.usuarios import crear_perfil_medico, roles


def test_inserta_y_lee_un_paciente(app, crear_paciente):
    with app.app_context():
        paciente = crear_paciente()
        db.session.commit()
        paciente_id, dni = paciente.id, paciente.dni

    with app.app_context():
        paciente = db.session.get(Paciente, paciente_id)

        assert paciente.dni == dni
        assert paciente.tipo_sospecha == TipoSospecha.CLINICA
        assert paciente.usuario.rol_codigo == roles.PACIENTE
        assert paciente.medico_tratante.usuario.rol_codigo == roles.MEDICO_TRATANTE
        assert paciente.medico_tratante.matricula.startswith("MP-TEST-")
        assert paciente.familiograma_path is None
        assert paciente.creado_en is not None


def test_rechaza_un_dni_repetido(app, crear_paciente):
    with app.app_context():
        primero = crear_paciente()
        segundo = crear_paciente()
        segundo.dni = primero.dni

        with pytest.raises(IntegrityError, match="pacientes_dni_key"):
            db.session.flush()


def test_la_base_rechaza_un_tipo_de_sospecha_desconocido(app, crear_paciente):
    with app.app_context():
        paciente = crear_paciente()

        with pytest.raises(IntegrityError, match="pacientes_tipo_sospecha_check"):
            db.session.execute(
                sa.text("update pacientes set tipo_sospecha = 'otra' where id = :id"),
                {"id": paciente.id},
            )


def test_solo_los_medicos_tienen_matricula(app, usuario_rapido):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)

        with pytest.raises(ValueError, match="matrícula"):
            crear_perfil_medico(administrativo, "MP-0001")
