"""Datos de prueba que carga `flask seeds`. Son todos inventados: nunca datos reales de pacientes.

Se puede correr más de una vez: crea lo que falta y no toca lo que ya existe.
"""

from datetime import date

import sqlalchemy as sa

from src.core.database import db
from src.core.pacientes import Paciente, TipoSospecha
from src.core.usuarios import Medico, buscar_por_email, crear_perfil_medico, crear_usuario, roles

# Un usuario de prueba por cada rol del LEL. ".test" es un dominio reservado: ningún mail llega.
USUARIOS_DE_PRUEBA = (
    # (email, nombre, apellido, rol)
    ("paciente@exoma.test", "Paula", "Paciente", roles.PACIENTE),
    ("medico@exoma.test", "Martín", "Médico", roles.MEDICO_TRATANTE),
    ("administrativo@exoma.test", "Ana", "Administrativa", roles.ADMINISTRATIVO),
    ("bioinformatico@exoma.test", "Bruno", "Bioinformático", roles.BIOINFORMATICO),
    ("transportista@exoma.test", "Tomás", "Transportista", roles.TRANSPORTISTA),
    ("gerente@exoma.test", "Gabriela", "Gerente", roles.GERENTE_MEDICO),
    ("admin@exoma.test", "Adrián", "Administrador", roles.ADMINISTRADOR_GENERAL),
)

# Perfil de médico (matrícula) de los usuarios de prueba que lo necesitan.
MATRICULAS_DE_PRUEBA = {
    "medico@exoma.test": "MP-TEST-0001",
    "gerente@exoma.test": "MP-TEST-0002",
}

# Ficha del paciente de prueba (E06), dada de alta por medico@exoma.test.
PACIENTE_DE_PRUEBA = {
    "email": "paciente@exoma.test",
    "medico_tratante": "medico@exoma.test",
    "dni": "00000001",
    "fecha_nacimiento": date(1990, 5, 17),
    "tipo_sospecha": TipoSospecha.CLINICA,
    "resumen_historia_clinica": "Paciente inventado para probar el sistema.",
}


def cargar_usuarios_de_prueba(contrasena: str) -> list[tuple[str, str, bool]]:
    """Crea los usuarios de prueba que falten, con sus perfiles de médico y de paciente.

    Devuelve (email, rol, creado) por cada usuario.
    """
    resultado = []
    for email, nombre, apellido, rol in USUARIOS_DE_PRUEBA:
        creado = buscar_por_email(email) is None
        if creado:
            crear_usuario(email, contrasena, nombre, apellido, rol)
        resultado.append((email, rol, creado))
    db.session.flush()

    for email, matricula in MATRICULAS_DE_PRUEBA.items():
        usuario = buscar_por_email(email)
        if db.session.get(Medico, usuario.id) is None:
            crear_perfil_medico(usuario, matricula)
    _cargar_paciente_de_prueba()

    db.session.commit()
    return resultado


def _cargar_paciente_de_prueba() -> None:
    datos = dict(PACIENTE_DE_PRUEBA)
    usuario = buscar_por_email(datos.pop("email"))
    existe = db.session.scalar(sa.select(Paciente.id).where(Paciente.usuario_id == usuario.id))
    if existe is None:
        medico = buscar_por_email(datos.pop("medico_tratante"))
        db.session.add(Paciente(usuario=usuario, medico_tratante_id=medico.id, **datos))
