"""Consultas de pacientes visibles para el médico tratante (E06)."""

import sqlalchemy as sa
from sqlalchemy.orm import joinedload, selectinload

from src.core.database import db
from src.core.pacientes.modelos import (
    DiagnosticoPresuntivo,
    Familiar,
    FamiliarPatologia,
    FamiliarSintoma,
    Paciente,
    PacienteSintoma,
)
from src.core.usuarios.modelos import Usuario


def listar_del_medico(medico: Usuario, busqueda: str = "") -> list[Paciente]:
    consulta = (
        sa.select(Paciente)
        .join(Paciente.usuario)
        .where(Paciente.medico_tratante_id == medico.id)
        .options(joinedload(Paciente.usuario))
        .order_by(sa.func.lower(Usuario.apellido), sa.func.lower(Usuario.nombre), Paciente.id)
    )
    texto = (busqueda or "").strip()
    if texto:
        patron = f"%{texto.replace('%', r'\%').replace('_', r'\_')}%"
        consulta = consulta.where(
            sa.or_(
                Paciente.dni.ilike(patron, escape="\\"),
                sa.func.concat(Usuario.nombre, " ", Usuario.apellido).ilike(patron, escape="\\"),
                Usuario.email.ilike(patron, escape="\\"),
            )
        )
    return list(db.session.scalars(consulta).unique())


def paciente_del_medico(paciente_id: int, medico: Usuario) -> Paciente | None:
    consulta = (
        sa.select(Paciente)
        .where(Paciente.id == paciente_id, Paciente.medico_tratante_id == medico.id)
        .options(
            joinedload(Paciente.usuario),
            selectinload(Paciente.sintomas).joinedload(PacienteSintoma.termino),
            selectinload(Paciente.diagnosticos_presuntivos).joinedload(
                DiagnosticoPresuntivo.patologia
            ),
            selectinload(Paciente.familiares)
            .joinedload(Familiar.paciente_vinculado)
            .joinedload(Paciente.usuario),
            selectinload(Paciente.familiares)
            .selectinload(Familiar.sintomas)
            .joinedload(FamiliarSintoma.termino),
            selectinload(Paciente.familiares)
            .selectinload(Familiar.patologias)
            .joinedload(FamiliarPatologia.patologia),
        )
    )
    return db.session.scalars(consulta).unique().one_or_none()
