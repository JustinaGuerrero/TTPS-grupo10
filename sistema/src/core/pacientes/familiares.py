"""Vinculación automática de familiares con pacientes por DNI (G13)."""

from datetime import UTC, datetime

import sqlalchemy as sa

from src.core.auditoria import Accion, Entidad, registrar
from src.core.database import db
from src.core.pacientes.modelos import Familiar, Paciente
from src.core.usuarios.modelos import Usuario


def vincular_familiares(paciente: Paciente, usuario: Usuario | None = None) -> int:
    """Vincula por DNI en los dos sentidos y registra los cambios en la misma transacción."""
    usuario = usuario or paciente.medico_tratante.usuario
    ahora = datetime.now(UTC)
    vinculados = 0

    familiares = list(
        db.session.scalars(
            sa.select(Familiar).where(
                Familiar.paciente_id == paciente.id,
                Familiar.dni.is_not(None),
                Familiar.paciente_vinculado_id.is_(None),
            )
        )
    )
    for familiar in familiares:
        vinculo = db.session.scalar(
            sa.select(Paciente).where(Paciente.dni == familiar.dni, Paciente.id != paciente.id)
        )
        if vinculo is None:
            continue
        familiar.paciente_vinculado = vinculo
        familiar.vinculado_en = ahora
        vinculados += 1

    familiares_ajenos = list(
        db.session.scalars(
            sa.select(Familiar).where(
                Familiar.dni == paciente.dni,
                Familiar.paciente_id != paciente.id,
                Familiar.paciente_vinculado_id.is_(None),
            )
        )
    )
    por_paciente: dict[int, list[Familiar]] = {}
    for familiar in familiares_ajenos:
        familiar.paciente_vinculado = paciente
        familiar.vinculado_en = ahora
        por_paciente.setdefault(familiar.paciente_id, []).append(familiar)
        vinculados += 1

    db.session.flush()
    for paciente_id, filas in por_paciente.items():
        cambios = {}
        for fila in filas:
            prefijo = f"familiar[{fila.id}]"
            cambios[f"{prefijo}.paciente_vinculado_id"] = (None, paciente.id)
            cambios[f"{prefijo}.vinculado_en"] = (None, fila.vinculado_en)
        registrar(
            Entidad.PACIENTE,
            paciente_id,
            usuario,
            Accion.MODIFICACION,
            cambios,
        )
    return vinculados
