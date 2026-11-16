"""Auto registro de médicos y personal del laboratorio (E01 y E02)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.database import db
from src.core.snomed import ESPECIALIDAD, guardar_termino
from src.core.usuarios import roles
from src.core.usuarios.alta import (
    LARGO_MAXIMO,
    MINIMO_DE_DIGITOS_DEL_TELEFONO,
    PATRON_EMAIL,
    PATRON_TELEFONO,
    ErrorDeValidacion,
)
from src.core.usuarios.especialidades import MedicoEspecialidad
from src.core.usuarios.modelos import Medico, Rol, Usuario
from src.core.usuarios.servicios import buscar_por_email, crear_perfil_medico, crear_usuario

ROLES_MEDICOS = roles.CON_MATRICULA
ROLES_DE_REGISTRO = (
    *ROLES_MEDICOS,
    roles.ADMINISTRATIVO,
    roles.BIOINFORMATICO,
)

CAMPO_DE_CADA_RESTRICCION = {
    "usuarios_email_unico": "email",
    "medicos_matricula_key": "matricula",
}


@dataclass(frozen=True)
class DatosDeRegistro:
    """Datos enviados en el formulario público de registro."""

    rol_codigo: str = ""
    nombre: str = ""
    apellido: str = ""
    email: str = ""
    telefono: str = ""
    matricula: str = ""
    contrasena: str = ""
    confirmar_contrasena: str = ""
    especialidades: tuple[tuple[str, str], ...] = ()

    @classmethod
    def desde(
        cls,
        valores: Mapping[str, str],
        especialidades: Iterable[tuple[str, str]] = (),
    ) -> "DatosDeRegistro":
        datos = {}
        for campo in fields(cls):
            if campo.name == "especialidades":
                continue
            valor = valores.get(campo.name) or ""
            datos[campo.name] = (
                valor
                if campo.name
                in (
                    "contrasena",
                    "confirmar_contrasena",
                )
                else valor.strip()
            )
        datos["especialidades"] = tuple(especialidades)
        return cls(**datos)


def roles_de_registro() -> list[Rol]:
    """Roles que puede elegir una persona en E01 y E02, en el orden del formulario."""
    por_codigo = {
        rol.codigo: rol
        for rol in db.session.scalars(sa.select(Rol).where(Rol.codigo.in_(ROLES_DE_REGISTRO)))
    }
    return [por_codigo[codigo] for codigo in ROLES_DE_REGISTRO]


def validar_registro(datos: DatosDeRegistro) -> dict[str, str]:
    """Errores por campo del formulario de registro."""
    errores: dict[str, str] = {}
    rol_valido = datos.rol_codigo in ROLES_DE_REGISTRO
    es_medico = datos.rol_codigo in ROLES_MEDICOS

    if not rol_valido:
        errores["rol_codigo"] = "Elegí un rol habilitado para registrarse."

    for campo, texto in (("nombre", "el nombre"), ("apellido", "el apellido")):
        valor = getattr(datos, campo)
        if not valor:
            errores[campo] = f"Completá {texto}."
        elif len(valor) > LARGO_MAXIMO[campo]:
            errores[campo] = f"Usá como máximo {LARGO_MAXIMO[campo]} caracteres."

    if not datos.email:
        errores["email"] = "Completá el mail."
    elif len(datos.email) > LARGO_MAXIMO["email"] or not PATRON_EMAIL.fullmatch(datos.email):
        errores["email"] = "Ingresá un mail válido, por ejemplo nombre@dominio.com."
    elif buscar_por_email(datos.email) is not None:
        errores["email"] = "Ya hay un usuario con ese mail."

    digitos = sum(caracter.isdigit() for caracter in datos.telefono)
    if not datos.telefono:
        errores["telefono"] = "Completá el teléfono."
    elif (
        len(datos.telefono) > LARGO_MAXIMO["telefono"]
        or not PATRON_TELEFONO.fullmatch(datos.telefono)
        or digitos < MINIMO_DE_DIGITOS_DEL_TELEFONO
    ):
        errores["telefono"] = "Ingresá un teléfono válido: solo números, espacios, guiones y +."

    if len(datos.contrasena) < 8:
        errores["contrasena"] = "La contraseña debe tener al menos 8 caracteres."
    if not datos.confirmar_contrasena:
        errores["confirmar_contrasena"] = "Confirmá la contraseña."
    elif datos.contrasena != datos.confirmar_contrasena:
        errores["confirmar_contrasena"] = "Las contraseñas no coinciden."

    if es_medico:
        if not datos.matricula:
            errores["matricula"] = "Completá la matrícula."
        elif len(datos.matricula) > LARGO_MAXIMO["matricula"]:
            errores["matricula"] = f"Usá como máximo {LARGO_MAXIMO['matricula']} caracteres."
        elif _matricula_usada(datos.matricula):
            errores["matricula"] = "Ya hay un médico con esa matrícula."

        if not datos.especialidades:
            errores["especialidades"] = "Elegí al menos una especialidad."
        elif any(
            not codigo.strip() or not termino.strip() for codigo, termino in datos.especialidades
        ):
            errores["especialidades"] = "Volvé a elegir las especialidades desde SNOMED."
    return errores


def registrar_usuario(datos: DatosDeRegistro) -> Usuario:
    """Crea un usuario con su contraseña elegida y, para médicos, su perfil y especialidades.

    No hace commit: lo decide el controlador.
    """
    errores = validar_registro(datos)
    if errores:
        raise ErrorDeValidacion(errores)

    try:
        with db.session.begin_nested():
            usuario = crear_usuario(
                datos.email,
                datos.contrasena,
                datos.nombre,
                datos.apellido,
                datos.rol_codigo,
                telefono=datos.telefono,
            )
            if datos.rol_codigo in ROLES_MEDICOS:
                medico = crear_perfil_medico(usuario, datos.matricula)
                db.session.flush()
                guardar_especialidades(medico, datos.especialidades)
            db.session.flush()
    except IntegrityError as error:
        campo = CAMPO_DE_CADA_RESTRICCION.get(_restriccion(error))
        if campo is None:
            raise
        errores = validar_registro(datos) or {campo: "Ese dato ya está registrado."}
        raise ErrorDeValidacion(errores) from error
    return usuario


def guardar_especialidades(medico: Medico, especialidades: Iterable[tuple[str, str]]) -> None:
    """Guarda términos SNOMED y la relación del médico; no hace commit."""
    filas = []
    codigos = set()
    for codigo, termino in especialidades:
        codigo = codigo.strip()
        termino = termino.strip()
        if not codigo or not termino:
            raise ErrorDeValidacion(
                {"especialidades": "Volvé a elegir las especialidades desde SNOMED."}
            )
        if codigo in codigos:
            continue
        codigos.add(codigo)
        filas.append((codigo, termino))
    if not filas:
        raise ErrorDeValidacion({"especialidades": "Elegí al menos una especialidad."})

    for codigo, termino in filas:
        guardar_termino(codigo, termino, ESPECIALIDAD)
        db.session.add(MedicoEspecialidad(medico_id=medico.usuario_id, termino_codigo=codigo))
    db.session.flush()


def _matricula_usada(matricula: str) -> bool:
    consulta = sa.select(Medico.usuario_id).where(Medico.matricula == matricula)
    return db.session.scalar(consulta) is not None


def _restriccion(error: IntegrityError) -> str | None:
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)
