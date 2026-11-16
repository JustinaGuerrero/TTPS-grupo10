"""Reglas de negocio de los términos SNOMED elegidos."""

from src.core.database import db
from src.core.snomed.modelos import TerminoSnomed

SINTOMA = "sintoma"
ESPECIALIDAD = "especialidad"
TIPOS = (SINTOMA, ESPECIALIDAD)


def buscar_termino(codigo: str) -> TerminoSnomed | None:
    return db.session.get(TerminoSnomed, (codigo or "").strip())


def guardar_termino(codigo: str, termino: str, tipo: str) -> TerminoSnomed:
    """Inserta el término elegido o actualiza su texto si ya estaba (upsert). No hace commit."""
    codigo = (codigo or "").strip()
    termino = (termino or "").strip()
    if not codigo or not termino:
        raise ValueError("Falta el código o el término SNOMED.")
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de término inválido: {tipo!r}")

    existente = db.session.get(TerminoSnomed, codigo)
    if existente is None:
        existente = TerminoSnomed(codigo=codigo, termino=termino, tipo=tipo)
        db.session.add(existente)
    else:
        existente.termino = termino
        existente.tipo = tipo
    db.session.flush()
    return existente
