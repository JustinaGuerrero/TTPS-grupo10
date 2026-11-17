"""Alta transaccional del paciente y de sus familiares (E06, E09)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from src.core.auditoria import Accion, Entidad, registrar
from src.core.database import db
from src.core.pacientes.familiares import vincular_familiares
from src.core.pacientes.modelos import (
    DiagnosticoPresuntivo,
    Familiar,
    FamiliarPatologia,
    FamiliarSintoma,
    Paciente,
    PacienteSintoma,
    TipoSospecha,
)
from src.core.patologias.modelos import Patologia
from src.core.patologias.validacion import validar_diagnostico_presuntivo
from src.core.snomed import SINTOMA, guardar_termino
from src.core.snomed.modelos import TerminoSnomed
from src.core.usuarios import roles
from src.core.usuarios.alta import (
    LARGO_MAXIMO,
    MINIMO_DE_DIGITOS_DEL_TELEFONO,
    PATRON_EMAIL,
    PATRON_TELEFONO,
    ErrorDeValidacion,
    generar_contrasena_provisoria,
)
from src.core.usuarios.modelos import Usuario
from src.core.usuarios.servicios import buscar_por_email, crear_usuario

DNI_VALIDO = re.compile(r"[0-9]{7,8}")
PARENTESCOS = (
    "madre",
    "padre",
    "hermano",
    "hermana",
    "hijo",
    "hija",
    "abuelo",
    "abuela",
    "nieto",
    "nieta",
    "tio",
    "tia",
    "primo",
    "prima",
    "otro",
)


@dataclass(frozen=True)
class DatosDeFamiliar:
    parentesco: str = ""
    nombre: str = ""
    dni: str = ""
    sintomas: tuple[tuple[str, str], ...] = ()
    patologias: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatosDeAlta:
    dni: str = ""
    nombre: str = ""
    apellido: str = ""
    fecha_nacimiento: str = ""
    telefono: str = ""
    email: str = ""
    tipo_sospecha: str = ""
    resumen_historia_clinica: str = ""
    sintomas: tuple[tuple[str, str], ...] = ()
    patologias: tuple[str, ...] = ()
    familiares: tuple[DatosDeFamiliar, ...] = ()

    @classmethod
    def desde(cls, valores: Mapping[str, str]) -> "DatosDeAlta":
        lista = getattr(valores, "getlist", None)

        def varios(nombre: str) -> list[str]:
            if lista:
                return lista(nombre)
            valor = valores.get(nombre, "")
            return valor if isinstance(valor, list) else ([valor] if valor else [])

        campos = {
            campo.name: (valores.get(campo.name) or "").strip()
            for campo in fields(cls)
            if campo.name not in {"sintomas", "patologias", "familiares"}
        }
        sintomas, error = _leer_terminos(varios("sintoma"))
        if error:
            raise ErrorDeValidacion({"sintomas": error})

        familiares = []
        parentescos = varios("familiares_parentesco")
        nombres = varios("familiares_nombre")
        dnis = varios("familiares_dni")
        for indice, parentesco in enumerate(parentescos):
            nombre = nombres[indice].strip() if indice < len(nombres) else ""
            dni = dnis[indice].strip() if indice < len(dnis) else ""
            sintomas_familiar, error = _leer_terminos(varios(f"familiares_sintomas_{indice}"))
            if error:
                raise ErrorDeValidacion({f"familiar_{indice}_sintomas": error})
            patologias_familiar = tuple(varios(f"familiares_patologias_{indice}"))
            if not any((parentesco.strip(), nombre, dni, sintomas_familiar, patologias_familiar)):
                continue
            familiares.append(
                DatosDeFamiliar(
                    parentesco.strip(),
                    nombre,
                    dni,
                    tuple(sintomas_familiar),
                    patologias_familiar,
                )
            )
        return cls(
            **campos,
            sintomas=tuple(sintomas),
            patologias=tuple(varios("patologia")),
            familiares=tuple(familiares),
        )


@dataclass(frozen=True)
class AltaDePaciente:
    paciente: Paciente
    # Solo se conserva en memoria para el envío del mail posterior al commit.
    contrasena: str


def dar_de_alta(datos: DatosDeAlta, medico: Usuario) -> AltaDePaciente:
    """Valida E08 y guarda usuario, paciente, síntomas, diagnóstico y familiares sin commit."""
    errores, fecha, patologias, patologias_familiares = _validar(datos, medico)
    if errores:
        raise ErrorDeValidacion(errores)

    contrasena = generar_contrasena_provisoria()
    try:
        with db.session.begin_nested():
            usuario = crear_usuario(
                datos.email,
                contrasena,
                datos.nombre,
                datos.apellido,
                roles.PACIENTE,
                telefono=datos.telefono,
            )
            usuario.debe_cambiar_contrasena = True
            paciente = Paciente(
                usuario=usuario,
                dni=datos.dni,
                fecha_nacimiento=fecha,
                tipo_sospecha=TipoSospecha(datos.tipo_sospecha),
                resumen_historia_clinica=datos.resumen_historia_clinica,
                medico_tratante_id=medico.id,
            )
            db.session.add(paciente)
            db.session.flush()

            for codigo, termino in datos.sintomas:
                guardar_termino(codigo, termino, SINTOMA)
                paciente.sintomas.append(PacienteSintoma(termino_codigo=codigo))
            for patologia in patologias:
                paciente.diagnosticos_presuntivos.append(DiagnosticoPresuntivo(patologia=patologia))
            for familiar_datos, diagnosticos in zip(
                datos.familiares, patologias_familiares, strict=True
            ):
                familiar = Familiar(
                    paciente=paciente,
                    parentesco=familiar_datos.parentesco,
                    nombre=familiar_datos.nombre,
                    dni=familiar_datos.dni or None,
                )
                db.session.add(familiar)
                for codigo, termino in familiar_datos.sintomas:
                    guardar_termino(codigo, termino, SINTOMA)
                    familiar.sintomas.append(FamiliarSintoma(termino_codigo=codigo))
                for patologia in diagnosticos:
                    familiar.patologias.append(FamiliarPatologia(patologia=patologia))

            db.session.flush()
            vincular_familiares(paciente, medico)
            registrar(
                Entidad.PACIENTE,
                paciente.id,
                medico,
                Accion.ALTA,
                {
                    "usuario_id": (None, usuario.id),
                    "dni": (None, paciente.dni),
                    "nombre": (None, usuario.nombre),
                    "apellido": (None, usuario.apellido),
                    "email": (None, usuario.email),
                    "telefono": (None, usuario.telefono),
                    "fecha_nacimiento": (None, paciente.fecha_nacimiento),
                    "tipo_sospecha": (None, paciente.tipo_sospecha),
                    "resumen_historia_clinica": (None, paciente.resumen_historia_clinica),
                    "medico_tratante_id": (None, paciente.medico_tratante_id),
                    "sintomas": (
                        None,
                        ", ".join(termino for _, termino in datos.sintomas),
                    ),
                    "diagnosticos_presuntivos": (
                        None,
                        ", ".join(patologia.nombre for patologia in patologias),
                    ),
                },
            )
            for familiar in paciente.familiares:
                registrar(
                    Entidad.PACIENTE,
                    paciente.id,
                    medico,
                    Accion.ALTA,
                    _cambios_de_familiar(familiar),
                )
            db.session.flush()
    except IntegrityError as error:
        campo = _campo_de_restriccion(error)
        if campo is None:
            raise
        mensaje = (
            "Ya hay un paciente con ese DNI."
            if campo == "dni"
            else "Ya hay un usuario con ese mail."
        )
        raise ErrorDeValidacion({campo: mensaje}) from error

    return AltaDePaciente(paciente, contrasena)


def _validar(
    datos: DatosDeAlta, medico: Usuario
) -> tuple[dict[str, str], date | None, list[Patologia], list[list[Patologia]]]:
    errores: dict[str, str] = {}
    fecha = _fecha(datos.fecha_nacimiento)
    patologias = _buscar_patologias_activas(datos.patologias)
    patologias_familiares: list[list[Patologia]] = []

    if not medico.tiene_rol(roles.MEDICO_TRATANTE):
        errores["medico"] = "Solo el médico tratante puede dar de alta a un paciente."
    if not DNI_VALIDO.fullmatch(datos.dni):
        errores["dni"] = "Ingresá un DNI de 7 u 8 números, sin puntos."
    elif db.session.scalar(sa.select(Paciente.id).where(Paciente.dni == datos.dni)):
        errores["dni"] = "Ya hay un paciente con ese DNI."
    for campo, valor in (("nombre", datos.nombre), ("apellido", datos.apellido)):
        if not valor:
            errores[campo] = "Completá este campo."
        elif len(valor) > LARGO_MAXIMO[campo]:
            errores[campo] = f"Usá como máximo {LARGO_MAXIMO[campo]} caracteres."
    if fecha is None:
        errores["fecha_nacimiento"] = "Ingresá una fecha válida."
    elif fecha > date.today():
        errores["fecha_nacimiento"] = "La fecha de nacimiento no puede ser futura."
    digitos = sum(caracter.isdigit() for caracter in datos.telefono)
    if (
        not datos.telefono
        or len(datos.telefono) > LARGO_MAXIMO["telefono"]
        or not PATRON_TELEFONO.fullmatch(datos.telefono)
        or digitos < MINIMO_DE_DIGITOS_DEL_TELEFONO
    ):
        errores["telefono"] = "Ingresá un teléfono válido."
    if (
        not datos.email
        or len(datos.email) > LARGO_MAXIMO["email"]
        or not PATRON_EMAIL.fullmatch(datos.email)
    ):
        errores["email"] = "Ingresá un mail válido."
    elif buscar_por_email(datos.email) is not None:
        errores["email"] = "Ya hay un usuario con ese mail."
    if datos.tipo_sospecha not in ("clinica", "familiar"):
        errores["tipo_sospecha"] = "Elegí el tipo de sospecha."
    if not datos.resumen_historia_clinica.strip():
        errores["resumen_historia_clinica"] = "Completá el resumen de historia clínica."
    if not datos.patologias:
        errores["patologia"] = "Elegí al menos una patología activa."
    elif len(patologias) != len(datos.patologias):
        errores["patologia"] = "Elegí patologías activas válidas."
    sintomas = _validar_terminos(datos.sintomas, "sintomas", errores)

    for indice, familiar in enumerate(datos.familiares):
        diagnosticos = _buscar_patologias(familiar.patologias)
        patologias_familiares.append(diagnosticos)
        if familiar.parentesco not in PARENTESCOS:
            errores[f"familiar_{indice}_parentesco"] = "Elegí un parentesco válido."
        if not familiar.nombre:
            errores[f"familiar_{indice}_nombre"] = "Completá el nombre del familiar."
        if familiar.dni and not DNI_VALIDO.fullmatch(familiar.dni):
            errores[f"familiar_{indice}_dni"] = "El DNI debe tener 7 u 8 números, sin puntos."
        if len(diagnosticos) != len(familiar.patologias):
            errores[f"familiar_{indice}_patologias"] = "Elegí patologías válidas."
        _validar_terminos(familiar.sintomas, f"familiar_{indice}_sintomas", errores)

    patologias_de_familiares = {
        patologia.codigo_apigen for lista in patologias_familiares for patologia in lista
    }
    if not errores and datos.tipo_sospecha in ("clinica", "familiar"):
        resultado = validar_diagnostico_presuntivo(
            (codigo for codigo, _ in sintomas),
            [patologia.como_sospechada() for patologia in patologias],
            datos.tipo_sospecha,
            patologias_de_familiares,
        )
        if not resultado.acepta:
            errores["diagnostico_presuntivo"] = " ".join(
                f"{i.patologia}: {i.falta}." for i in resultado.inconsistencias
            )
    return errores, fecha, patologias, patologias_familiares


def _buscar_patologias(codigos: tuple[str, ...]) -> list[Patologia]:
    ids = {int(codigo) for codigo in codigos if codigo.isascii() and codigo.isdigit()}
    if not ids:
        return []
    return list(db.session.scalars(sa.select(Patologia).where(Patologia.id.in_(ids))).unique())


def _buscar_patologias_activas(codigos: tuple[str, ...]) -> list[Patologia]:
    ids = {int(codigo) for codigo in codigos if codigo.isascii() and codigo.isdigit()}
    if not ids:
        return []
    return list(
        db.session.scalars(
            sa.select(Patologia).where(Patologia.id.in_(ids), Patologia.activa.is_(True))
        ).unique()
    )


def _validar_terminos(
    terminos: tuple[tuple[str, str], ...], campo: str, errores: dict[str, str]
) -> list[tuple[str, str]]:
    codigos = [codigo for codigo, _ in terminos]
    if len(codigos) != len(set(codigos)):
        errores[campo] = "No repitas un síntoma."
    for codigo, _ in terminos:
        termino = db.session.get(TerminoSnomed, codigo)
        if termino is not None and termino.tipo != SINTOMA:
            errores[campo] = "Elegí síntomas de la lista de SNOMED."
    return list(terminos)


def _leer_terminos(valores: list[str]) -> tuple[list[tuple[str, str]], str | None]:
    terminos = []
    for valor in valores:
        if not valor.strip():
            continue
        codigo, separador, texto = valor.partition("|")
        codigo, texto = codigo.strip(), texto.strip()
        if not separador or not codigo or not texto:
            return [], "Volvé a elegir los síntomas desde SNOMED."
        terminos.append((codigo, texto))
    return terminos, None


def _fecha(valor: str) -> date | None:
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _cambios_de_familiar(familiar: Familiar) -> dict[str, tuple[object, object]]:
    prefijo = f"familiar[{familiar.id}]"
    return {
        f"{prefijo}.parentesco": (None, familiar.parentesco),
        f"{prefijo}.nombre": (None, familiar.nombre),
        f"{prefijo}.dni": (None, familiar.dni),
        f"{prefijo}.paciente_vinculado_id": (None, familiar.paciente_vinculado_id),
        f"{prefijo}.sintomas": (
            None,
            ", ".join(sintoma.termino.termino for sintoma in familiar.sintomas),
        ),
        f"{prefijo}.patologias": (
            None,
            ", ".join(fila.patologia.nombre for fila in familiar.patologias),
        ),
    }


def _campo_de_restriccion(error: IntegrityError) -> str | None:
    diagnostico = getattr(error.orig, "diag", None)
    restriccion = getattr(diagnostico, "constraint_name", None)
    return {
        "pacientes_dni_key": "dni",
        "usuarios_email_unico": "email",
    }.get(restriccion)
