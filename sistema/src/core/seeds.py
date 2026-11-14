"""Datos de prueba que carga `flask seeds`. Son todos inventados: nunca datos reales de pacientes.

Se puede correr más de una vez: crea lo que falta y no toca lo que ya existe.
"""

from src.core.database import db
from src.core.usuarios import buscar_por_email, crear_usuario, roles

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


def cargar_usuarios_de_prueba(contrasena: str) -> list[tuple[str, str, bool]]:
    """Crea los usuarios de prueba que falten. Devuelve (email, rol, creado) por cada uno."""
    resultado = []
    for email, nombre, apellido, rol in USUARIOS_DE_PRUEBA:
        creado = buscar_por_email(email) is None
        if creado:
            crear_usuario(email, contrasena, nombre, apellido, rol)
        resultado.append((email, rol, creado))
    db.session.commit()
    return resultado
