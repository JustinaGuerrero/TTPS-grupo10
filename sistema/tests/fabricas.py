"""Fábricas de datos para los tests. Las carga conftest.py con pytest_plugins.

Cada fábrica es un fixture que devuelve una función: el test la llama con lo que le importa y el
resto sale con valores de prueba. Con ellas cada issue prueba su escenario partiendo del estado
que necesita, sin esperar a los escenarios anteriores del circuito.

Cada issue que crea una tabla agrega acá su fábrica (#7 centro y turno, #8 muestra y mensaje del
bot, #14 sample set). Solo se agregan fábricas: no se cambian las que ya están.
"""

import itertools
from datetime import date

import pytest
from conftest import CONTRASENA_DE_TEST

from src.core.database import db
from src.core.demo import camino_desde_creado
from src.core.estudios import EstadoEstudio, Estudio, cambiar_estado
from src.core.estudios import crear_estudio as crear_estudio_en_core
from src.core.pacientes import Paciente, TipoSospecha
from src.core.usuarios import Usuario, crear_perfil_medico, roles
from src.core.usuarios import crear_usuario as crear_usuario_en_core


@pytest.fixture
def crear_usuario(app):
    """Fábrica: `crear_usuario(roles.PACIENTE)` guarda un usuario con ese rol y devuelve su mail.

    La contraseña es CONTRASENA_DE_TEST. Con `activo=False` queda desactivado.
    """
    numeros = itertools.count(1)

    def _crear(rol: str, email: str | None = None, activo: bool = True) -> str:
        email = email or f"{rol}.{next(numeros)}@exoma.test"
        with app.app_context():
            usuario = crear_usuario_en_core(email, CONTRASENA_DE_TEST, "Nombre", "De Test", rol)
            usuario.activo = activo
            db.session.commit()
        return email

    return _crear


@pytest.fixture
def usuario_rapido():
    """Fábrica: `usuario_rapido(roles.ADMINISTRATIVO)` agrega a db.session un usuario y lo devuelve.

    Usa un hash ficticio para no calcular scrypt: el usuario no puede iniciar sesión. Para los
    tests que necesitan usuarios como datos y no como login. Llamarla dentro de un app_context.
    """
    numeros = itertools.count(1)

    def _crear(rol: str) -> Usuario:
        numero = next(numeros)
        usuario = Usuario(
            email=f"rapido.{rol}.{numero}@exoma.test",
            hash_contrasena="hash-ficticio",
            nombre="Nombre",
            apellido=f"De Test {numero}",
            rol_codigo=rol,
        )
        db.session.add(usuario)
        return usuario

    return _crear


@pytest.fixture
def crear_paciente(usuario_rapido):
    """Fábrica: `crear_paciente()` agrega un paciente, con su usuario y su médico tratante.

    `fecha_nacimiento` sirve para los casos que dependen de la edad (Pompe urgente, menores).
    Llamarla dentro de un app_context; no hace commit.
    """
    numeros = itertools.count(1)

    def _crear(fecha_nacimiento: date = date(2000, 1, 1)) -> Paciente:
        numero = next(numeros)
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        paciente = Paciente(
            usuario=usuario_rapido(roles.PACIENTE),
            dni=f"9{numero:07d}",
            fecha_nacimiento=fecha_nacimiento,
            tipo_sospecha=TipoSospecha.CLINICA,
            resumen_historia_clinica="Resumen de historia clínica de prueba.",
            medico_tratante=crear_perfil_medico(medico, f"MP-TEST-{numero:04d}"),
        )
        db.session.add(paciente)
        db.session.flush()
        return paciente

    return _crear


@pytest.fixture
def crear_estudio(crear_paciente):
    """Fábrica: `crear_estudio(estado=...)` guarda un estudio y lo devuelve en ese estado.

    Lo da de alta en Creado con crear_estudio() de core y lo lleva al estado pedido por el
    camino más corto (camino_desde_creado de src/core/demo.py), siempre con cambiar_estado() y
    usuario None. No crea las filas de DATOS_POR_ESTADO: el test que las necesita usa la fábrica
    de esa tabla. Hace commit. Llamarla dentro de un app_context.
    """

    def _crear(
        estado: EstadoEstudio | str = EstadoEstudio.CREADO,
        genes: tuple[str, ...] = ("GAA",),
        genes_agregados_a_mano: tuple[str, ...] = (),
        evalua_hallazgos_secundarios: bool = False,
        fecha_nacimiento: date = date(2000, 1, 1),
    ) -> Estudio:
        paciente = crear_paciente(fecha_nacimiento=fecha_nacimiento)
        estudio = crear_estudio_en_core(
            paciente,
            paciente.medico_tratante.usuario,
            genes=genes,
            evalua_hallazgos_secundarios=evalua_hallazgos_secundarios,
            genes_agregados_a_mano=genes_agregados_a_mano,
        )
        for siguiente in camino_desde_creado(estado)[1:]:
            cambiar_estado(estudio, siguiente, None)
        db.session.commit()
        return estudio

    return _crear
