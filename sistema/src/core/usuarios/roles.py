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
