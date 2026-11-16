"""E03 Dar de alta usuario: el administrador general crea un usuario y le manda sus credenciales.

Uso desde un controlador (el orden importa: el mail sale antes del commit):

    try:
        alta = dar_de_alta_usuario(DatosDeAlta.desde(request.form))
    except ErrorDeValidacion as error:
        ...  # mostrar error.errores junto a cada campo
    if not enviar_credenciales(alta.usuario, alta.contrasena, url_for("autenticacion.iniciar_sesion")):
        db.session.rollback()   # sin mail nadie conoce la contraseña: no se crea el usuario
    else:
        db.session.commit()

La contraseña provisoria solo viaja en el mail: en la base queda el hash y nunca se guarda en
notificaciones (por eso no se usa notificar(), que guarda el mensaje del aviso).
"""

import re
import secrets
import string
from collections.abc import Mapping
from dataclasses import dataclass, fields

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.database import db
from src.core.provincias.modelos import Provincia
from src.core.usuarios import roles
from src.core.usuarios.modelos import Medico, Rol, Transportista, Usuario
from src.core.usuarios.servicios import buscar_por_email, crear_perfil_medico, crear_usuario
from src.integraciones import mail

# Largos máximos de cada campo. La plantilla los usa como maxlength.
LARGO_MAXIMO = {
    "nombre": 100,
    "apellido": 100,
    "email": 254,
    "telefono": 30,
    "matricula": 30,
}

# Un mail con algo antes y después de la arroba y un punto en el dominio. La única prueba real
# de que existe es que llegue el mail con las credenciales.
PATRON_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")
# Dígitos, espacios, guiones, paréntesis y un + inicial: "+54 9 221 555-1234".
PATRON_TELEFONO = re.compile(r"\+?[0-9 ()-]+")
MINIMO_DE_DIGITOS_DEL_TELEFONO = 6

LARGO_DE_LA_CONTRASENA = 12
# Sin caracteres que se confunden al copiarlos del mail: 0/O, 1/l/I.
ALFABETO_DE_LA_CONTRASENA = "".join(
    c for c in string.ascii_letters + string.digits if c not in "0O1lI"
)

# Índices únicos de la base y el campo del formulario al que corresponde cada uno. Cubren el
# caso de dos altas simultáneas que pasan la validación a la vez.
CAMPO_DE_CADA_RESTRICCION = {
    "usuarios_email_unico": "email",
    "medicos_matricula_key": "matricula",
    "transportistas_provincia_id_key": "provincia_id",
}


class ErrorDeValidacion(Exception):
    """Datos del alta inválidos. `errores` va de campo del formulario a mensaje para mostrar."""

    def __init__(self, errores: dict[str, str]) -> None:
        super().__init__("; ".join(f"{campo}: {mensaje}" for campo, mensaje in errores.items()))
        self.errores = errores


@dataclass(frozen=True)
class DatosDeAlta:
    """Lo que completa el administrador general (episodios 1 y 2), como texto sin validar."""

    rol_codigo: str = ""
    nombre: str = ""
    apellido: str = ""
    email: str = ""
    telefono: str = ""
    # Solo médico tratante y gerente médico.
    matricula: str = ""
    # Solo transportista: el id de la provincia, como viene del formulario.
    provincia_id: str = ""

    @classmethod
    def desde(cls, valores: Mapping[str, str]) -> "DatosDeAlta":
        """Toma los campos de un formulario (request.form) y les saca los espacios de los bordes."""
        return cls(**{campo.name: (valores.get(campo.name) or "").strip() for campo in fields(cls)})


@dataclass(frozen=True)
class Alta:
    usuario: Usuario
    # En texto plano solo acá, para mandarla por mail. No se guarda.
    contrasena: str


def validar_alta(datos: DatosDeAlta) -> dict[str, str]:
    """Errores de los datos del alta por campo. Vacío si son válidos.

    Los campos que no corresponden al rol se ignoran: una matrícula escrita para un
    administrativo no da error ni se guarda.
    """
    errores: dict[str, str] = {}

    if datos.rol_codigo not in roles.DE_ALTA_POR_ADMINISTRADOR:
        errores["rol_codigo"] = "Elegí el rol del nuevo usuario."

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

    digitos = sum(c.isdigit() for c in datos.telefono)
    if not datos.telefono:
        errores["telefono"] = "Completá el teléfono."
    elif (
        len(datos.telefono) > LARGO_MAXIMO["telefono"]
        or not PATRON_TELEFONO.fullmatch(datos.telefono)
        or digitos < MINIMO_DE_DIGITOS_DEL_TELEFONO
    ):
        errores["telefono"] = "Ingresá un teléfono válido: solo números, espacios, guiones y +."

    if datos.rol_codigo in roles.CON_MATRICULA:
        if not datos.matricula:
            errores["matricula"] = "Completá la matrícula."
        elif len(datos.matricula) > LARGO_MAXIMO["matricula"]:
            errores["matricula"] = f"Usá como máximo {LARGO_MAXIMO['matricula']} caracteres."
        elif _matricula_usada(datos.matricula):
            errores["matricula"] = "Ya hay un médico con esa matrícula."

    if datos.rol_codigo == roles.TRANSPORTISTA:
        provincia = _provincia(datos.provincia_id)
        if provincia is None:
            errores["provincia_id"] = "Elegí la provincia del transportista."
        elif provincia.id in provincias_con_transportista():
            errores["provincia_id"] = (
                f"{provincia.nombre} ya tiene transportista: hay uno por provincia."
            )

    return errores


def dar_de_alta_usuario(datos: DatosDeAlta) -> Alta:
    """Episodios 1 a 3: crea el usuario con el rol y sus datos, y una contraseña provisoria.

    Crea también el perfil del rol: médico (matrícula) o transportista (provincia). No hace
    commit ni manda el mail: ver enviar_credenciales() y el ejemplo del módulo.

    Lanza ErrorDeValidacion si los datos no son válidos.
    """
    errores = validar_alta(datos)
    if errores:
        raise ErrorDeValidacion(errores)

    contrasena = generar_contrasena_provisoria()
    try:
        # Savepoint: si choca un índice único, se deshace solo el alta y la sesión sigue usable.
        with db.session.begin_nested():
            usuario = crear_usuario(
                datos.email,
                contrasena,
                datos.nombre,
                datos.apellido,
                datos.rol_codigo,
                telefono=datos.telefono,
            )
            if datos.rol_codigo in roles.CON_MATRICULA:
                crear_perfil_medico(usuario, datos.matricula)
            elif datos.rol_codigo == roles.TRANSPORTISTA:
                db.session.add(Transportista(usuario=usuario, provincia_id=int(datos.provincia_id)))
            db.session.flush()
    except IntegrityError as error:
        campo = CAMPO_DE_CADA_RESTRICCION.get(_restriccion(error))
        if campo is None:
            raise
        # Otra alta con el mismo dato se guardó entre la validación y el flush.
        errores = validar_alta(datos) or {campo: "Ese dato ya está registrado."}
        raise ErrorDeValidacion(errores) from error

    return Alta(usuario, contrasena)


def enviar_credenciales(usuario: Usuario, contrasena: str, link_de_ingreso: str) -> bool:
    """Episodio 4: manda al nuevo usuario un mail con su mail de ingreso y su contraseña.

    `link_de_ingreso` es la ruta del login (url_for), que el mail lleva como link absoluto.
    Devuelve False si el mail no salió; quien llama decide qué hacer (ver el ejemplo del módulo).
    """
    cuerpo = (
        f"Hola, {usuario.nombre}:\n\n"
        "El laboratorio central te dio de alta en el sistema de exoma clínico con el rol "
        f"{usuario.rol.nombre}.\n\n"
        "Tus credenciales de acceso son:\n"
        f"  Usuario: {usuario.email}\n"
        f"  Contraseña: {contrasena}\n\n"
        f"Ingresá en: {mail.url_absoluta(link_de_ingreso)}\n\n"
        "No compartas esta contraseña con nadie. Si no esperabas este mail, avisale al "
        "laboratorio central.\n\n"
        "--\n"
        "Laboratorio central · Sistema de exoma clínico\n"
        "Este mail se envió automáticamente: no lo respondas.\n"
    )
    return mail.enviar(usuario.email, "Tus credenciales de acceso al sistema de exoma", cuerpo)


def generar_contrasena_provisoria() -> str:
    """Contraseña aleatoria de LARGO_DE_LA_CONTRASENA caracteres, con letras y números."""
    while True:
        contrasena = "".join(
            secrets.choice(ALFABETO_DE_LA_CONTRASENA) for _ in range(LARGO_DE_LA_CONTRASENA)
        )
        if any(c.isdigit() for c in contrasena) and any(c.isalpha() for c in contrasena):
            return contrasena


def roles_de_alta() -> list[Rol]:
    """Los roles del episodio 1, en el orden de roles.DE_ALTA_POR_ADMINISTRADOR."""
    por_codigo = {
        rol.codigo: rol
        for rol in db.session.scalars(
            sa.select(Rol).where(Rol.codigo.in_(roles.DE_ALTA_POR_ADMINISTRADOR))
        )
    }
    return [por_codigo[codigo] for codigo in roles.DE_ALTA_POR_ADMINISTRADOR]


def provincias_con_transportista() -> set[int]:
    """Ids de las provincias que ya tienen transportista: el formulario no las ofrece."""
    return set(db.session.scalars(sa.select(Transportista.provincia_id)))


def _matricula_usada(matricula: str) -> bool:
    consulta = sa.select(Medico.usuario_id).where(Medico.matricula == matricula)
    return db.session.scalar(consulta) is not None


def _provincia(provincia_id: str) -> Provincia | None:
    # Solo dígitos ASCII y que entre en un bigint: cualquier otra cosa es "no eligió provincia".
    if not (provincia_id.isascii() and provincia_id.isdigit() and len(provincia_id) <= 18):
        return None
    return db.session.get(Provincia, int(provincia_id))


def _restriccion(error: IntegrityError) -> str | None:
    """Nombre del índice o restricción que falló, según psycopg."""
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None)
