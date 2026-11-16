"""Códigos de los 7 roles del LEL (símbolo Usuario). Coinciden con la tabla roles de la migración.

Se usan en vez de escribir el texto a mano: `rol_requerido(roles.ADMINISTRATIVO)`.
"""

PACIENTE = "paciente"
MEDICO_TRATANTE = "medico_tratante"
ADMINISTRATIVO = "administrativo"
BIOINFORMATICO = "bioinformatico"
TRANSPORTISTA = "transportista"
GERENTE_MEDICO = "gerente_medico"
ADMINISTRADOR_GENERAL = "administrador_general"

TODOS = (
    PACIENTE,
    MEDICO_TRATANTE,
    ADMINISTRATIVO,
    BIOINFORMATICO,
    TRANSPORTISTA,
    GERENTE_MEDICO,
    ADMINISTRADOR_GENERAL,
)

# Roles que da de alta el administrador general (E03, episodio 1). El paciente lo da de alta el
# médico tratante (E06) y el administrador general no se da de alta desde el sistema.
DE_ALTA_POR_ADMINISTRADOR = (
    MEDICO_TRATANTE,
    GERENTE_MEDICO,
    ADMINISTRATIVO,
    BIOINFORMATICO,
    TRANSPORTISTA,
)

# Roles con perfil de médico, que se registran con matrícula (E01, tabla medicos).
CON_MATRICULA = (MEDICO_TRATANTE, GERENTE_MEDICO)
