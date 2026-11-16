import pytest

from src.core.patologias.validacion import (
    PatologiaSospechada,
    validar_diagnostico_presuntivo,
)

POMPE = PatologiaSospechada("POMPE", "Pompe", "CARD", frozenset({"S1", "S2", "S3"}))
FABRY = PatologiaSospechada("FABRY", "Fabry", "CARD_F", frozenset({"F1", "F2"}))


def validar(sintomas, patologias=(POMPE,), tipo="clinica", familiares=()):
    return validar_diagnostico_presuntivo(sintomas, patologias, tipo, familiares)


def test_solo_cardinal_acepta():
    assert validar({"CARD"}).acepta


def test_dos_secundarios_acepta():
    assert validar({"S1", "S2"}).acepta


def test_un_secundario_rechaza():
    resultado = validar({"S1"})
    assert not resultado.acepta
    assert resultado.inconsistencias[0].patologia == "Pompe"


def test_ninguno_rechaza_con_la_inconsistencia():
    resultado = validar(set())
    assert not resultado.acepta
    assert "cardinal" in resultado.inconsistencias[0].falta


def test_dos_patologias_con_una_que_falla_rechaza():
    resultado = validar({"CARD"}, patologias=(POMPE, FABRY))
    assert not resultado.acepta
    assert [i.patologia for i in resultado.inconsistencias] == ["Fabry"]


def test_sospecha_familiar_con_familiar_diagnosticado_acepta():
    assert validar(set(), tipo="familiar", familiares={"POMPE"}).acepta


def test_sospecha_familiar_sin_familiar_diagnosticado_rechaza():
    assert not validar({"CARD"}, tipo="familiar", familiares={"FABRY"}).acepta


def test_tipo_de_sospecha_invalido():
    with pytest.raises(ValueError):
        validar({"CARD"}, tipo="otra")
