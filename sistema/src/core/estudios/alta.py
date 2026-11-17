"""Alta de un estudio por el médico tratante (E10).

dar_de_alta_estudio() junta lo que el escenario pide antes y después de crear_estudio(): los
genes de Apigen para el diagnóstico presuntivo, los genes a mano, el Pompe urgente, las patologías
del análisis, el registro de cambios y el aviso a los administrativos. Si Apigen falla, lanza
ErrorDeIntegracion antes de insertar nada. No hace commit: lo decide el controlador.
"""

import calendar
from collections.abc import Iterable
from datetime import date

import sqlalchemy as sa

from src.core.auditoria import Accion, Entidad, registrar
from src.core.database import db
from src.core.estudios.analisis_patologias import AnalisisPatologia
from src.core.estudios.modelos import Estudio
from src.core.estudios.servicios import crear_estudio
from src.core.notificaciones import notificar
from src.core.pacientes.modelos import Paciente
from src.core.patologias.modelos import Patologia
from src.core.usuarios import listar_activos_por_rol, roles
from src.core.usuarios.alta import ErrorDeValidacion
from src.core.usuarios.modelos import Usuario
from src.integraciones import apigen

PATOLOGIA_POMPE = "POMPE"
MESES_POMPE_URGENTE = 4
# Dónde el administrativo emite el presupuesto del estudio recién creado (E13).
LINK_DEL_AVISO = "/pagos/presupuestos"


def genes_para(patologias: Iterable[Patologia]) -> list[str]:
    """Genes que Apigen asocia a las patologías, sin repetir y ordenados.

    Lo usan el alta (E10) y el reanálisis (E12). Lanza ErrorDeIntegracion si Apigen falla.
    """
    genes: set[str] = set()
    for patologia in patologias:
        genes.update(apigen.genes_de_patologia(patologia.codigo_apigen))
    return sorted(genes)


def es_pompe_urgente(
    patologias: Iterable[Patologia], fecha_nacimiento: date, hoy: date | None = None
) -> bool:
    """Pompe urgente (O14): diagnóstico presuntivo con Pompe y menos de 4 meses al dar de alta."""
    if not any(p.codigo_apigen == PATOLOGIA_POMPE for p in patologias):
        return False
    return (hoy or date.today()) < _sumar_meses(fecha_nacimiento, MESES_POMPE_URGENTE)


def validar_genes_a_mano(simbolos: Iterable[str]) -> list[str]:
    """Los símbolos normalizados (mayúsculas, sin repetir) o ErrorDeValidacion si alguno no existe.

    Lanza ErrorDeIntegracion si Apigen falla.
    """
    normalizados = sorted({s.strip().upper() for s in simbolos if s and s.strip()})
    inexistentes = [s for s in normalizados if s not in _existentes(s)]
    if inexistentes:
        plural = len(inexistentes) > 1
        raise ErrorDeValidacion(
            {
                "genes_a_mano": (
                    f"{'Los genes' if plural else 'El gen'} {', '.join(inexistentes)} "
                    f"no {'existen' if plural else 'existe'} en Apigen."
                )
            }
        )
    return normalizados


def dar_de_alta_estudio(
    paciente: Paciente,
    medico: Usuario,
    genes_a_mano: Iterable[str] = (),
    evalua_hallazgos_secundarios: bool = False,
    hoy: date | None = None,
) -> Estudio:
    """Da de alta el estudio del paciente en Creado y avisa a los administrativos activos.

    Lanza ErrorDeValidacion si el paciente ya tiene estudio, no tiene diagnóstico presuntivo o
    un gen a mano no existe; ValueError si `medico` no puede darlo de alta (lo controla
    crear_estudio) y ErrorDeIntegracion si Apigen no responde. En esos casos no se crea nada.
    """
    if _tiene_estudio(paciente):
        raise ErrorDeValidacion(
            {
                "paciente": (
                    "El paciente ya tiene un estudio. Una sospecha nueva se pide por reanálisis."
                )
            }
        )
    patologias = [d.patologia for d in paciente.diagnosticos_presuntivos]
    if not patologias:
        raise ErrorDeValidacion({"paciente": "El paciente no tiene diagnóstico presuntivo."})

    de_apigen = genes_para(patologias)
    a_mano = validar_genes_a_mano(genes_a_mano)
    urgente = es_pompe_urgente(patologias, paciente.fecha_nacimiento, hoy)

    estudio = crear_estudio(
        paciente,
        medico,
        de_apigen,
        evalua_hallazgos_secundarios,
        genes_agregados_a_mano=a_mano,
        pompe_urgente=urgente,
    )
    analisis = estudio.analisis[0]
    db.session.add_all(
        AnalisisPatologia(analisis_id=analisis.id, patologia_id=p.id) for p in patologias
    )
    registrar(
        Entidad.ESTUDIO,
        estudio.id,
        medico,
        Accion.ALTA,
        {
            "paciente_id": (None, paciente.id),
            "patologias": (None, ", ".join(sorted(p.nombre for p in patologias))),
            "genes": (None, ", ".join(g.gen_simbolo for g in analisis.genes)),
            "genes_a_mano": (None, ", ".join(a_mano)),
            "evalua_hallazgos_secundarios": (None, evalua_hallazgos_secundarios),
            "pompe_urgente": (None, urgente),
        },
    )
    _avisar_a_administrativos(estudio, paciente, urgente)
    return estudio


def _avisar_a_administrativos(estudio: Estudio, paciente: Paciente, urgente: bool) -> None:
    asunto = "Pompe urgente: estudio para presupuestar" if urgente else "Estudio para presupuestar"
    mensaje = (
        f"El estudio {estudio.codigo} de {paciente.usuario.nombre_completo} está en Creado. "
        "Falta emitir el presupuesto."
    )
    for administrativo in listar_activos_por_rol(roles.ADMINISTRATIVO):
        notificar(administrativo, asunto, mensaje, LINK_DEL_AVISO, estudio=estudio)


def _tiene_estudio(paciente: Paciente) -> bool:
    consulta = sa.select(Estudio.id).where(Estudio.paciente_id == paciente.id)
    return db.session.scalar(consulta) is not None


def _existentes(simbolo: str) -> set[str]:
    return {s.upper() for s in apigen.buscar_genes(simbolo)}


def _sumar_meses(fecha: date, meses: int) -> date:
    indice = fecha.year * 12 + fecha.month - 1 + meses
    anio, mes = divmod(indice, 12)
    mes += 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))
