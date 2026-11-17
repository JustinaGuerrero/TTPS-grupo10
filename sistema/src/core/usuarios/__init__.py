"""Usuarios y roles. Es el módulo de referencia (E03): un módulo nuevo copia esta estructura.

- modelos.py   modelos SQLAlchemy (Rol, Usuario y los perfiles Medico y Transportista).
- roles.py     códigos de los roles, para no escribirlos a mano.
- servicios.py crear usuarios, buscarlos, listar los activos de un rol y validar credenciales (E04).
- alta.py      E03: validar los datos, dar de alta y mandar las credenciales por mail.
- busqueda.py  E03: grilla con búsqueda, filtro, orden y paginación del lado del servidor.
- registro.py  E01 y E02: auto registro y especialidades SNOMED.

Ninguna función hace commit: lo decide el controlador.
"""

from src.core.usuarios import roles
from src.core.usuarios.alta import (
    LARGO_MAXIMO,
    Alta,
    DatosDeAlta,
    ErrorDeValidacion,
    dar_de_alta_usuario,
    enviar_credenciales,
    generar_contrasena_provisoria,
    provincias_con_transportista,
    roles_de_alta,
    validar_alta,
)
from src.core.usuarios.busqueda import (
    COLUMNAS_DE_ORDEN,
    USUARIOS_POR_PAGINA,
    BusquedaDeUsuarios,
    buscar_usuarios,
)
from src.core.usuarios.especialidades import MedicoEspecialidad
from src.core.usuarios.modelos import (
    CodigoVerificacion,
    DispositivoConfiable,
    Medico,
    Rol,
    Transportista,
    Usuario,
)
from src.core.usuarios.registro import (
    ROLES_DE_REGISTRO,
    DatosDeRegistro,
    guardar_especialidades,
    registrar_usuario,
    roles_de_registro,
    validar_registro,
)
from src.core.usuarios.servicios import (
    buscar_por_email,
    buscar_por_id,
    cambiar_contrasena_provisoria,
    crear_perfil_medico,
    crear_usuario,
    hashear_contrasena,
    listar_activos_por_rol,
    listar_roles,
    validar_credenciales,
)

__all__ = [
    "COLUMNAS_DE_ORDEN",
    "LARGO_MAXIMO",
    "ROLES_DE_REGISTRO",
    "USUARIOS_POR_PAGINA",
    "Alta",
    "BusquedaDeUsuarios",
    "CodigoVerificacion",
    "DatosDeAlta",
    "DatosDeRegistro",
    "DispositivoConfiable",
    "ErrorDeValidacion",
    "Medico",
    "MedicoEspecialidad",
    "Rol",
    "Transportista",
    "Usuario",
    "buscar_por_email",
    "buscar_por_id",
    "buscar_usuarios",
    "cambiar_contrasena_provisoria",
    "crear_perfil_medico",
    "crear_usuario",
    "dar_de_alta_usuario",
    "enviar_credenciales",
    "generar_contrasena_provisoria",
    "guardar_especialidades",
    "hashear_contrasena",
    "listar_activos_por_rol",
    "listar_roles",
    "provincias_con_transportista",
    "registrar_usuario",
    "roles",
    "roles_de_alta",
    "roles_de_registro",
    "validar_alta",
    "validar_credenciales",
    "validar_registro",
]
