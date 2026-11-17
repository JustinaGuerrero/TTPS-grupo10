"""Datos de prueba que carga `flask seeds`. Son todos inventados: nunca datos reales de pacientes.

Se puede correr más de una vez: crea lo que falta y no toca lo que ya existe.
"""

from datetime import date
from decimal import Decimal

import sqlalchemy as sa

from src.core.centros import CentroExtraccion
from src.core.database import db
from src.core.estudios import Estudio, crear_estudio
from src.core.pacientes import Paciente, TipoSospecha
from src.core.patologias import buscar_por_codigo, crear_patologia
from src.core.provincias import Provincia
from src.core.snomed import SINTOMA, guardar_termino
from src.core.usuarios import (
    Medico,
    Transportista,
    buscar_por_email,
    crear_perfil_medico,
    crear_usuario,
    roles,
)

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

# Perfil de transportista (provincia) de los usuarios de prueba que lo necesitan (E03).
PROVINCIAS_DE_PRUEBA = {
    "transportista@exoma.test": "Buenos Aires",
}

# Ficha del paciente de prueba (E06), dada de alta por medico@exoma.test, con su estudio.
PACIENTE_DE_PRUEBA = {
    "email": "paciente@exoma.test",
    "medico_tratante": "medico@exoma.test",
    "dni": "00000001",
    "fecha_nacimiento": date(1990, 5, 17),
    "tipo_sospecha": TipoSospecha.CLINICA,
    "resumen_historia_clinica": "Paciente inventado para probar el sistema.",
}

# Centros de extracción de prueba (E19), inventados: 10 centros en 3 provincias, con coordenadas
# para el mapa y el chat de Telegram desde el que escriben al bot (E22, `flask bot simular`).
# fmt: off
CENTROS_DE_PRUEBA = (
    # (nombre, dirección, localidad, provincia, latitud, longitud, teléfono, chat de Telegram)
    ("Centro La Plata", "Calle 7 1234", "La Plata", "Buenos Aires",
     "-34.921200", "-57.954500", "0221 555-0101", "1000001"),
    ("Centro Quilmes", "Av. Calchaquí 2500", "Quilmes", "Buenos Aires",
     "-34.724700", "-58.254300", "011 555-0102", "1000002"),
    ("Centro Mar del Plata", "Av. Colón 3100", "Mar del Plata", "Buenos Aires",
     "-38.005500", "-57.552600", "0223 555-0103", "1000003"),
    ("Centro Bahía Blanca", "Av. Alem 1200", "Bahía Blanca", "Buenos Aires",
     "-38.718300", "-62.266300", "0291 555-0104", "1000004"),
    ("Centro Palermo", "Av. Santa Fe 3800", "Palermo", "Ciudad Autónoma de Buenos Aires",
     "-34.588000", "-58.420000", "011 555-0105", "1000005"),
    ("Centro Caballito", "Av. Rivadavia 5200", "Caballito", "Ciudad Autónoma de Buenos Aires",
     "-34.618500", "-58.441000", "011 555-0106", "1000006"),
    ("Centro Belgrano", "Av. Cabildo 2100", "Belgrano", "Ciudad Autónoma de Buenos Aires",
     "-34.562000", "-58.456000", "011 555-0107", "1000007"),
    ("Centro Córdoba", "Av. Colón 800", "Córdoba", "Córdoba",
     "-31.413500", "-64.191900", "0351 555-0108", "1000008"),
    ("Centro Villa Carlos Paz", "Av. San Martín 600", "Villa Carlos Paz", "Córdoba",
     "-31.424100", "-64.497800", "03541 555-0109", "1000009"),
    ("Centro Río Cuarto", "Constitución 900", "Río Cuarto", "Córdoba",
     "-33.123300", "-64.349900", "0358 555-0110", "1000010"),
)
# fmt: on

# Genes del estudio del paciente de prueba, que queda en Creado. Para otros estados: `flask demo`.
GENES_DEL_ESTUDIO_DE_PRUEBA = ("GAA",)

# Síntomas SNOMED de los seeds (E36/E07). Son los mismos de tests/fixtures/apis/snomed/, así el
# buscador en modo mock encuentra lo que usan las patologías. Los códigos son de ejemplo.
SINTOMAS_DE_PRUEBA = {
    "Dolor abdominal": "21522001",
    "Fatiga": "84229001",
    "Diarrea": "62315008",
    "Cardiomegalia": "8186001",
    "Debilidad muscular": "68962001",
    "Disnea": "267036007",
    "Esplenomegalia": "16294009",
    "Hepatomegalia": "80515008",
    "Fiebre": "386661006",
}

# Las 5 patologías base de Apigen (apigen/contrato.md), con síntomas inventados.
# (código de Apigen, nombre, síntoma cardinal, síntomas secundarios)
PATOLOGIAS_BASE = (
    ("FABRY", "Enfermedad de Fabry", "Dolor abdominal", ("Fatiga", "Diarrea", "Cardiomegalia")),
    (
        "POMPE",
        "Enfermedad de Pompe",
        "Debilidad muscular",
        ("Disnea", "Cardiomegalia", "Fatiga"),
    ),
    (
        "GAUCHER",
        "Enfermedad de Gaucher",
        "Esplenomegalia",
        ("Hepatomegalia", "Fatiga", "Dolor abdominal"),
    ),
    (
        "MPS1",
        "Mucopolisacaridosis tipo 1",
        "Cardiomegalia",
        ("Hepatomegalia", "Disnea", "Debilidad muscular"),
    ),
    (
        "ASMD",
        "Déficit de esfingomielinasa ácida (ASMD)",
        "Hepatomegalia",
        ("Esplenomegalia", "Disnea", "Fiebre"),
    ),
)


def cargar_usuarios_de_prueba(contrasena: str) -> list[tuple[str, str, bool]]:
    """Crea los usuarios de prueba que falten, con sus perfiles de médico, transportista y paciente.

    También carga las patologías base (necesita al gerente médico como creador).
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
    for email, provincia in PROVINCIAS_DE_PRUEBA.items():
        _cargar_transportista_de_prueba(email, provincia)
    _cargar_paciente_de_prueba()
    cargar_patologias_base()
    cargar_centros_de_prueba()

    db.session.commit()
    return resultado


def cargar_patologias_base() -> int:
    """Crea las 5 patologías base que falten, con sus síntomas. No hace commit.

    Ya existen en Apigen, así que no se dan de alta allá (alta_en_apigen=False). Devuelve
    cuántas creó.
    """
    gerente = buscar_por_email("gerente@exoma.test")
    for nombre, codigo in SINTOMAS_DE_PRUEBA.items():
        guardar_termino(codigo, nombre, SINTOMA)

    creadas = 0
    for codigo, nombre, cardinal, secundarios in PATOLOGIAS_BASE:
        if buscar_por_codigo(codigo) is not None:
            continue
        crear_patologia(
            nombre,
            codigo,
            [SINTOMAS_DE_PRUEBA[cardinal]],
            [SINTOMAS_DE_PRUEBA[s] for s in secundarios],
            gerente,
            alta_en_apigen=False,
        )
        creadas += 1
    return creadas


def cargar_centros_de_prueba() -> int:
    """Crea los centros de extracción de prueba que falten (por su chat). No hace commit.

    Devuelve cuántos creó.
    """
    creados = 0
    for nombre, direccion, localidad, provincia, lat, lon, telefono, chat in CENTROS_DE_PRUEBA:
        existe = db.session.scalar(
            sa.select(CentroExtraccion.id).where(CentroExtraccion.telegram_chat_id == chat)
        )
        if existe is not None:
            continue
        db.session.add(
            CentroExtraccion(
                nombre=nombre,
                direccion=direccion,
                localidad=localidad,
                provincia=db.session.scalars(
                    sa.select(Provincia).where(Provincia.nombre == provincia)
                ).one(),
                latitud=Decimal(lat),
                longitud=Decimal(lon),
                telefono=telefono,
                telegram_chat_id=chat,
            )
        )
        creados += 1
    db.session.flush()
    return creados


def _cargar_paciente_de_prueba() -> None:
    datos = dict(PACIENTE_DE_PRUEBA)
    usuario = buscar_por_email(datos.pop("email"))
    medico = buscar_por_email(datos.pop("medico_tratante"))
    paciente = db.session.scalars(
        sa.select(Paciente).where(Paciente.usuario_id == usuario.id)
    ).one_or_none()
    if paciente is None:
        paciente = Paciente(usuario=usuario, medico_tratante_id=medico.id, **datos)
        db.session.add(paciente)
        db.session.flush()
    tiene_estudio = db.session.scalar(
        sa.select(Estudio.id).where(Estudio.paciente_id == paciente.id)
    )
    if tiene_estudio is None:
        crear_estudio(
            paciente,
            medico,
            genes=GENES_DEL_ESTUDIO_DE_PRUEBA,
            evalua_hallazgos_secundarios=False,
        )


def _cargar_transportista_de_prueba(email: str, nombre_de_provincia: str) -> None:
    usuario = buscar_por_email(email)
    if db.session.get(Transportista, usuario.id) is not None:
        return
    provincia = db.session.scalars(
        sa.select(Provincia).where(Provincia.nombre == nombre_de_provincia)
    ).one()
    db.session.add(Transportista(usuario=usuario, provincia=provincia))
