"""Regla de E08: validar el diagnóstico presuntivo contra los síntomas del paciente.

Función pura: no usa la base ni Flask. Quien la llama arma los datos.
"""

from collections.abc import Iterable
from dataclasses import dataclass

TIPOS_DE_SOSPECHA = ("clinica", "familiar")
MINIMO_DE_SECUNDARIOS = 2


@dataclass(frozen=True)
class PatologiaSospechada:
    codigo: str  # codigo_apigen, por ejemplo "POMPE"
    nombre: str
    cardinal: str  # termino_codigo SNOMED del síntoma cardinal
    secundarios: frozenset[str]  # termino_codigo SNOMED de los secundarios


@dataclass(frozen=True)
class Inconsistencia:
    patologia: str  # nombre de la patología que no cumple
    falta: str  # qué falta, para informar al médico (E08.5)


@dataclass(frozen=True)
class ResultadoValidacion:
    acepta: bool
    inconsistencias: list[Inconsistencia]


def validar_diagnostico_presuntivo(
    sintomas: Iterable[str],
    patologias: Iterable[PatologiaSospechada],
    tipo_sospecha: str,
    patologias_de_familiares: Iterable[str],
) -> ResultadoValidacion:
    """Acepta el alta solo si todas las patologías del diagnóstico presuntivo cumplen (G2).

    sintomas: términos SNOMED del paciente.
    patologias_de_familiares: códigos de las patologías con las que ya está diagnosticado
    algún familiar.
    """
    if tipo_sospecha not in TIPOS_DE_SOSPECHA:
        raise ValueError(f"Tipo de sospecha inválido: {tipo_sospecha}")
    del_paciente = set(sintomas)
    de_familiares = set(patologias_de_familiares)

    inconsistencias = []
    for patologia in patologias:
        if tipo_sospecha == "familiar":
            # O2: con sospecha familiar alcanza que un familiar tenga esa patología.
            if patologia.codigo not in de_familiares:
                inconsistencias.append(
                    Inconsistencia(
                        patologia.nombre,
                        "ningún familiar tiene diagnóstico de esta patología",
                    )
                )
            continue
        secundarios_presentes = del_paciente & patologia.secundarios
        if (
            patologia.cardinal not in del_paciente
            and len(secundarios_presentes) < MINIMO_DE_SECUNDARIOS
        ):
            inconsistencias.append(
                Inconsistencia(
                    patologia.nombre,
                    "falta el síntoma cardinal o al menos "
                    f"{MINIMO_DE_SECUNDARIOS} secundarios "
                    f"(tiene {len(secundarios_presentes)})",
                )
            )
    return ResultadoValidacion(not inconsistencias, inconsistencias)
