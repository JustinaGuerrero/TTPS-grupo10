"""Reglas del área de bioinformática: datos crudos (E32), lista de pendientes y toma (E33).

El laboratorio de secuenciación manda los datos crudos fuera del sistema y el administrativo
los carga: el estudio pasa a En área de bioinformática y se avisa a todos los bioinformáticos.
Cada bioinformático toma un estudio de la lista; si dos lo toman a la vez, solo uno lo logra
(el UPDATE con `where bioinformatico_id is null`).

Ninguna función hace commit: lo decide el controlador. #20 (variantes y resultado) y #21
(reanálisis) agregan sus funciones en este módulo. `ahora` es para los tests.
"""

import re
from datetime import datetime

import sqlalchemy as sa

from src.core.auditoria import Accion, Entidad, registrar
from src.core.calendario import ahora as ahora_en_argentina
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, cambiar_estado
from src.core.estudios.modelos import Analisis
from src.core.notificaciones import notificar
from src.core.usuarios import listar_activos_por_rol, roles
from src.core.usuarios.modelos import Usuario
from src.integraciones import storage

# G12: los datos crudos son un .txt con solo A, C, T, G y saltos de línea, de hasta 20 MB.
TAMANO_MAXIMO_DE_LOS_DATOS_CRUDOS = 20 * 1024 * 1024
_SOLO_BASES = re.compile(rb"[ACGT\r\n]+")
LINK_DE_PENDIENTES = "/bioinformatica/pendientes"


class ErrorDeAnalisis(ValueError):
    """No se puede cargar o tomar el estudio; el mensaje se muestra al usuario."""


# --- E32 Cargar datos crudos ------------------------------------------------------------------


def estudios_en_viaje() -> list[Estudio]:
    """Estudios En viaje a Corea, esperando los datos crudos: los Pompe urgentes primero."""
    consulta = (
        sa.select(Estudio)
        .where(Estudio.estado == EstadoEstudio.EN_VIAJE_COREA)
        .order_by(Estudio.pompe_urgente.desc(), Estudio.id)
    )
    return list(db.session.scalars(consulta))


def validar_datos_crudos(contenido: bytes) -> None:
    """G12: lanza ErrorDeAnalisis si el archivo está vacío, pesa más de 20 MB o tiene otra cosa
    que A, C, T, G y saltos de línea."""
    if not contenido or not contenido.strip():
        raise ErrorDeAnalisis("El archivo de datos crudos está vacío.")
    if len(contenido) > TAMANO_MAXIMO_DE_LOS_DATOS_CRUDOS:
        raise ErrorDeAnalisis("El archivo de datos crudos no puede pesar más de 20 MB.")
    if not _SOLO_BASES.fullmatch(contenido):
        raise ErrorDeAnalisis(
            "El archivo de datos crudos tiene que ser un .txt con solo A, C, T, G y saltos de línea."
        )


def cargar_datos_crudos(
    estudio: Estudio, administrativo: Usuario, contenido: bytes, ahora: datetime | None = None
) -> Analisis:
    """E32.3 a E32.5: guarda el archivo, pasa el estudio a En área de bioinformática y avisa.

    El archivo va a Storage; el estudio guarda la ruta y el análisis abierto queda disponible
    para los bioinformáticos (disponible_en). Lanza ErrorDeAnalisis si quien carga no es
    administrativo, si el estudio no está En viaje a Corea o si el archivo no cumple G12.
    """
    ahora = ahora or ahora_en_argentina()
    if not administrativo.tiene_rol(roles.ADMINISTRATIVO):
        raise ErrorDeAnalisis("Solo un administrativo carga los datos crudos.")
    if estudio.estado != EstadoEstudio.EN_VIAJE_COREA:
        raise ErrorDeAnalisis(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: los datos crudos se "
            "cargan con el estudio En viaje a Corea."
        )
    validar_datos_crudos(contenido)
    analisis = estudio.analisis_actual

    ruta = storage.subir(
        f"estudios/{estudio.id}/datos-crudos-{ahora:%Y%m%d%H%M%S}.txt", contenido, "text/plain"
    )
    anterior = estudio.datos_crudos_path
    estudio.datos_crudos_path = ruta
    estudio.datos_crudos_cargados_en = ahora
    estudio.datos_crudos_cargados_por = administrativo.id
    analisis.disponible_en = ahora
    db.session.flush()
    registrar(
        Entidad.ESTUDIO,
        estudio.id,
        administrativo,
        Accion.MODIFICACION,
        {"datos_crudos_path": (anterior, ruta)},
    )
    cambiar_estado(estudio, EstadoEstudio.EN_AREA_BIOINFORMATICA, administrativo)

    urgente = "Pompe urgente: " if estudio.pompe_urgente else ""
    for bioinformatico in listar_activos_por_rol(roles.BIOINFORMATICO):
        notificar(
            bioinformatico,
            f"{urgente}Estudio para analizar",
            f"Llegaron los datos crudos del estudio {estudio.codigo}. Ya está en la lista de "
            "pendientes del área de bioinformática.",
            LINK_DE_PENDIENTES,
            estudio=estudio,
        )
    return analisis


# --- E33 Tomar el estudio ---------------------------------------------------------------------


def pendientes() -> list[Analisis]:
    """E33.1 y E33.2: análisis disponibles y sin tomar, Pompe urgente primero y después por
    orden de llegada (disponible_en)."""
    consulta = (
        sa.select(Analisis)
        .join(Estudio, Estudio.id == Analisis.estudio_id)
        .where(
            Estudio.estado == EstadoEstudio.EN_AREA_BIOINFORMATICA,
            Analisis.disponible_en.is_not(None),
            Analisis.bioinformatico_id.is_(None),
            Analisis.finalizado_en.is_(None),
        )
        .order_by(Estudio.pompe_urgente.desc(), Analisis.disponible_en, Analisis.id)
    )
    return list(db.session.scalars(consulta))


def buscar_analisis(analisis_id: int) -> Analisis | None:
    return db.session.get(Analisis, analisis_id)


def mis_analisis(bioinformatico: Usuario) -> list[Analisis]:
    """Los análisis que tomó el bioinformático y todavía no finalizó."""
    consulta = (
        sa.select(Analisis)
        .where(
            Analisis.bioinformatico_id == bioinformatico.id,
            Analisis.finalizado_en.is_(None),
        )
        .order_by(Analisis.tomado_en, Analisis.id)
    )
    return list(db.session.scalars(consulta))


def tomar(analisis: Analisis, bioinformatico: Usuario, ahora: datetime | None = None) -> Analisis:
    """E33.3 y E33.4: el bioinformático toma el estudio, que pasa a En análisis.

    El UPDATE solo cambia la fila si nadie la tomó (`where bioinformatico_id is null`): si dos
    bioinformáticos lo toman a la vez, el segundo no actualiza nada y recibe el error. Lanza
    ErrorDeAnalisis si quien toma no es bioinformático, si el estudio no está En área de
    bioinformática o si ya lo tomó otro.
    """
    ahora = ahora or ahora_en_argentina()
    if not bioinformatico.tiene_rol(roles.BIOINFORMATICO):
        raise ErrorDeAnalisis("Solo un bioinformático toma un estudio.")
    estudio = analisis.estudio
    if estudio.estado != EstadoEstudio.EN_AREA_BIOINFORMATICA:
        raise ErrorDeAnalisis(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: no está en la lista de "
            "pendientes."
        )
    tomado = db.session.execute(
        sa.update(Analisis)
        .where(
            Analisis.id == analisis.id,
            Analisis.bioinformatico_id.is_(None),
            Analisis.disponible_en.is_not(None),
        )
        .values(bioinformatico_id=bioinformatico.id, tomado_en=ahora)
        .execution_options(synchronize_session=False)
    )
    if tomado.rowcount == 0:
        raise ErrorDeAnalisis(f"El estudio {estudio.codigo} ya lo tomó otro bioinformático.")
    db.session.refresh(analisis)
    registrar(
        Entidad.ESTUDIO,
        estudio.id,
        bioinformatico,
        Accion.MODIFICACION,
        {"bioinformatico": (None, bioinformatico.nombre_completo)},
    )
    cambiar_estado(estudio, EstadoEstudio.EN_ANALISIS, bioinformatico)
    return analisis
