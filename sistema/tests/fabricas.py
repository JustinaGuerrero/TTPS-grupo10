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
from src.core.pacientes import Familiar, Paciente, TipoSospecha
from src.core.patologias import Patologia
from src.core.patologias import crear_patologia as crear_patologia_en_core
from src.core.snomed import SINTOMA, guardar_termino
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
def crear_medico(app):
    """Fábrica de médico tratante con perfil válido para las rutas de alta clínica."""
    numeros = itertools.count(1)

    def _crear() -> str:
        numero = next(numeros)
        email = f"medico.alta.{numero}@exoma.test"
        with app.app_context():
            usuario = crear_usuario_en_core(
                email,
                CONTRASENA_DE_TEST,
                "Médico",
                f"De Prueba {numero}",
                roles.MEDICO_TRATANTE,
                telefono="2215551234",
            )
            crear_perfil_medico(usuario, f"MP-ALTA-{numero:04d}")
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
def crear_familiar():
    """Fábrica de familiar asociado a un paciente. No hace commit."""
    numeros = itertools.count(1)

    def _crear(paciente: Paciente, *, dni: str | None = None) -> Familiar:
        familiar = Familiar(
            paciente=paciente,
            parentesco="hermano",
            nombre=f"Familiar {next(numeros)}",
            dni=dni,
        )
        db.session.add(familiar)
        db.session.flush()
        return familiar

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


@pytest.fixture
def crear_patologia(usuario_rapido):
    """Fábrica: `crear_patologia()` guarda una patología con su cardinal y la devuelve.

    `cardinal` y cada secundario son (código SNOMED, texto). Los términos se guardan antes con
    guardar_termino. No llama a Apigen (alta_en_apigen=False). Hace commit. Llamarla dentro de
    un app_context.
    """
    numeros = itertools.count(1)

    def _crear(
        nombre: str | None = None,
        cardinal: tuple[str, str] = ("S-CARDINAL", "Síntoma cardinal de prueba"),
        secundarios: tuple[tuple[str, str], ...] = (),
        activa: bool = True,
    ) -> Patologia:
        numero = next(numeros)
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        db.session.flush()
        for codigo, termino in (cardinal, *secundarios):
            guardar_termino(codigo, termino, SINTOMA)
        patologia = crear_patologia_en_core(
            nombre or f"Patología de prueba {numero}",
            f"PAT_{numero}",
            [cardinal[0]],
            [codigo for codigo, _ in secundarios],
            gerente,
            alta_en_apigen=False,
        )
        patologia.activa = activa
        db.session.commit()
        return patologia

    return _crear


@pytest.fixture
def crear_presupuesto(usuario_rapido):
    """Fábrica: `crear_presupuesto(estudio)` emite el presupuesto de un estudio en Creado.

    Usa emitir_presupuesto() de core con un administrativo: deja al estudio Presupuestado, con su
    asiento y su aviso. Hace commit. Llamarla dentro de un app_context.
    """
    from src.core.pagos import emitir_presupuesto

    def _crear(estudio: Estudio):
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()
        presupuesto = emitir_presupuesto(estudio, administrativo)
        db.session.commit()
        return presupuesto

    return _crear


@pytest.fixture
def crear_obra_social():
    """Fábrica: `crear_obra_social()` guarda una obra social y la devuelve. No hace commit."""
    from src.core.obras_sociales import ObraSocial

    numeros = itertools.count(1)

    def _crear(nombre: str | None = None) -> ObraSocial:
        numero = next(numeros)
        obra_social = ObraSocial(codigo=f"OS-{numero}", nombre=nombre or f"Obra social {numero}")
        db.session.add(obra_social)
        db.session.flush()
        return obra_social

    return _crear


@pytest.fixture
def crear_registro_de_cambio():
    """Fábrica: `crear_registro_de_cambio(Entidad.PACIENTE, 7, "dni", "1", "2")` agrega una fila
    al registro de cambios y la devuelve (E43).

    `creado_en` fija la fecha para los casos de orden y de filtros por fecha (por defecto, la de
    la transacción). `usuario` None es un cambio del sistema. Inserta la fila a mano, sin pasar
    por registrar(), y no hace commit. Llamarla dentro de un app_context.
    """
    from src.core.auditoria import Accion, RegistroDeCambio

    def _crear(
        entidad,
        entidad_id: int,
        campo: str = "campo",
        valor_anterior: str | None = "antes",
        valor_nuevo: str | None = "después",
        usuario: Usuario | None = None,
        accion: Accion = Accion.MODIFICACION,
        creado_en=None,
        detalle: str | None = None,
    ) -> RegistroDeCambio:
        registro = RegistroDeCambio(
            entidad=entidad,
            entidad_id=entidad_id,
            accion=accion,
            campo=campo,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            usuario_id=usuario.id if usuario is not None else None,
            detalle=detalle,
        )
        if creado_en is not None:
            registro.creado_en = creado_en
        db.session.add(registro)
        db.session.flush()
        return registro

    return _crear


@pytest.fixture
def crear_cupon(usuario_rapido):
    """Fábrica: `crear_cupon(medico)` agrega un cupón vigente del médico, sin paciente.

    `codigo` fija el código (en los mocks, VENCIDO01 está utilizado en el módulo y CAIDO001 falla
    al vencerse); `paciente` lo deja asignado a ese paciente. Inserta la fila sin pasar por el
    módulo de cupones y no hace commit. Llamarla dentro de un app_context.
    """
    from src.core.cupones import Cupon, EstadoCupon

    numeros = itertools.count(1)

    def _crear(
        medico: Usuario,
        codigo: str | None = None,
        porcentaje: int = 20,
        paciente: Paciente | None = None,
        estado: EstadoCupon = EstadoCupon.VIGENTE,
    ) -> Cupon:
        numero = next(numeros)
        gerente = usuario_rapido(roles.GERENTE_MEDICO)
        db.session.flush()
        cupon = Cupon(
            codigo=codigo or f"TEST{numero:04d}",
            descuento_porcentaje=porcentaje,
            pdf_path=f"cupones/test{numero}.pdf",
            estado=estado,
            generado_por=gerente.id,
            medico_tratante_id=medico.id,
            paciente_id=paciente.id if paciente is not None else None,
        )
        db.session.add(cupon)
        db.session.flush()
        return cupon

    return _crear


@pytest.fixture
def crear_centro():
    """Fábrica: `crear_centro()` agrega un centro de extracción activo y lo devuelve (E19).

    `provincia` es el nombre de una de las 24 de la migración. No hace commit. Llamarla dentro
    de un app_context.
    """
    from decimal import Decimal

    import sqlalchemy as sa

    from src.core.centros import CentroExtraccion
    from src.core.provincias import Provincia

    numeros = itertools.count(1)

    def _crear(provincia: str = "Buenos Aires", activo: bool = True) -> CentroExtraccion:
        numero = next(numeros)
        centro = CentroExtraccion(
            nombre=f"Centro de test {numero}",
            direccion=f"Calle de test {numero}",
            localidad="La Plata",
            provincia=db.session.scalars(
                sa.select(Provincia).where(Provincia.nombre == provincia)
            ).one(),
            latitud=Decimal("-34.921200"),
            longitud=Decimal("-57.954500"),
            telefono="0221 555-0000",
            telegram_chat_id=f"test-{numero}",
            activo=activo,
        )
        db.session.add(centro)
        db.session.flush()
        return centro

    return _crear


@pytest.fixture
def crear_turno(crear_centro):
    """Fábrica: `crear_turno(estudio)` agrega un turno reservado del estudio y lo devuelve (E19).

    Sin `inicio`, toma una franja libre del próximo día hábil; sin `centro`, crea uno. No cambia
    el estado del estudio (para eso, crear_estudio(estado="turno_sacado")). No hace commit.
    Llamarla dentro de un app_context.
    """
    from datetime import datetime

    from src.core.calendario import hoy, proximo_dia_habil
    from src.core.turnos import EstadoTurno, TurnoExtraccion
    from src.core.turnos.franjas import franjas_del_dia

    def _crear(
        estudio: Estudio,
        centro=None,
        inicio: datetime | None = None,
        estado: EstadoTurno = EstadoTurno.RESERVADO,
    ) -> TurnoExtraccion:
        centro = centro or crear_centro()
        if inicio is None:
            inicio = franjas_del_dia(proximo_dia_habil(hoy()))[0]
        turno = TurnoExtraccion(estudio_id=estudio.id, centro_id=centro.id, inicio=inicio)
        turno.estado = estado
        if estado == EstadoTurno.CANCELADO:
            turno.cancelado_en = inicio
        db.session.add(turno)
        db.session.flush()
        return turno

    return _crear


@pytest.fixture
def crear_cobertura(crear_obra_social):
    """Fábrica: `crear_cobertura(estudio)` agrega la cobertura pendiente del estudio y la devuelve.

    No cambia el estado del estudio (para eso, crear_estudio(estado="pendiente_autorizacion")).
    No hace commit. Llamarla dentro de un app_context.
    """
    from decimal import Decimal

    from src.core.coberturas import Cobertura

    def _crear(estudio: Estudio, porcentaje: int | str = 70) -> Cobertura:
        cobertura = Cobertura(
            estudio_id=estudio.id,
            obra_social_codigo=crear_obra_social().codigo,
            porcentaje=Decimal(str(porcentaje)),
        )
        db.session.add(cobertura)
        db.session.flush()
        return cobertura

    return _crear
