"""crear_estudio(): el alta del estudio en Creado con su análisis inicial (core de E10)."""

import re

import pytest

from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, TipoAnalisis
from src.core.estudios import crear_estudio as crear_estudio_en_core
from src.core.usuarios import crear_perfil_medico, roles


def test_queda_en_creado_con_su_analisis_inicial(app, crear_estudio):
    with app.app_context():
        estudio = crear_estudio(
            genes=("GAA", " GLA "),
            genes_agregados_a_mano=("GLA", "NPC1"),
            evalua_hallazgos_secundarios=True,
        )
        estudio_id, medico_id = estudio.id, estudio.medico_tratante_id

    with app.app_context():
        estudio = db.session.get(Estudio, estudio_id)

        assert estudio.estado == EstadoEstudio.CREADO
        assert re.fullmatch(r"EX-\d{4}-\d{5}", estudio.codigo)
        assert estudio.pompe_urgente is False
        assert estudio.creado_en is not None

        [primera] = estudio.historial
        assert (primera.estado_anterior, primera.estado_nuevo) == (None, EstadoEstudio.CREADO)
        assert primera.usuario_id == medico_id

        [analisis] = estudio.analisis
        assert analisis is estudio.analisis_actual
        assert (analisis.numero, analisis.tipo) == (1, TipoAnalisis.INICIAL)
        assert analisis.evalua_hallazgos_secundarios is True
        assert analisis.solicitado_por == medico_id
        # GLA vino de Apigen, así que no cuenta como agregado a mano aunque el médico lo repita.
        assert [(g.gen_simbolo, g.agregado_a_mano) for g in analisis.genes] == [
            ("GAA", False),
            ("GLA", False),
            ("NPC1", True),
        ]


def test_cada_estudio_tiene_su_codigo(app, crear_estudio):
    with app.app_context():
        codigos = {crear_estudio().codigo for _ in range(3)}

    assert len(codigos) == 3


def test_solo_un_medico_tratante_da_de_alta_un_estudio(app, crear_paciente, usuario_rapido):
    with app.app_context():
        paciente = crear_paciente()
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        crear_perfil_medico(gerente, "MP-GERENTE")

        with pytest.raises(ValueError, match="Solo un médico tratante"):
            crear_estudio_en_core(
                paciente, gerente, genes=["GAA"], evalua_hallazgos_secundarios=False
            )


def test_el_medico_tratante_necesita_su_matricula(app, crear_paciente, usuario_rapido):
    with app.app_context():
        paciente = crear_paciente()
        sin_perfil = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        with pytest.raises(ValueError, match="matrícula"):
            crear_estudio_en_core(
                paciente, sin_perfil, genes=["GAA"], evalua_hallazgos_secundarios=False
            )


def test_el_estudio_necesita_al_menos_un_gen(app, crear_paciente):
    with app.app_context():
        paciente = crear_paciente()

        with pytest.raises(ValueError, match="al menos un gen"):
            crear_estudio_en_core(
                paciente,
                paciente.medico_tratante.usuario,
                genes=[],
                genes_agregados_a_mano=["  "],
                evalua_hallazgos_secundarios=False,
            )


def test_un_solo_estudio_por_paciente(app, crear_estudio):
    with app.app_context():
        primero = crear_estudio()

        with pytest.raises(ValueError, match="ya tiene un estudio"):
            crear_estudio_en_core(
                primero.paciente,
                primero.medico_tratante.usuario,
                genes=["GLA"],
                evalua_hallazgos_secundarios=False,
            )
