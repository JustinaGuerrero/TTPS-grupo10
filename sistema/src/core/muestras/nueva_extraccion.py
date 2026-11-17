"""E27 Solicitar nueva extracción: el laboratorio de Corea avisa que la muestra no sirve.

El aviso llega por mail, fuera del sistema (G14): el administrativo lo registra con el motivo
(ADN insuficiente, volumen insuficiente u otro) y un detalle opcional. Solo se puede mientras el
estudio está En viaje a Corea. El estudio pasa a Requiere nueva extracción y el paciente reserva
otro turno sin volver a pagar (ESTADOS_QUE_RESERVAN de core/turnos).

No se exporta en core/muestras/__init__: se importa de src.core.muestras.nueva_extraccion.
Ninguna función hace commit: lo decide el controlador.
"""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa

from src.core.auditoria import Accion, Entidad, registrar
from src.core.calendario import ahora as ahora_en_argentina
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, cambiar_estado
from src.core.muestras.modelos import MotivoInsuficiente, Muestra
from src.core.notificaciones import notificar
from src.core.turnos.servicios import LINK_DE_MI_TURNO
from src.core.usuarios import roles
from src.core.usuarios.modelos import Usuario


class MotivoNuevaExtraccion(StrEnum):
    """Por qué el laboratorio de Corea dice que la muestra no sirve."""

    ADN = "adn"
    VOLUMEN = "volumen"
    OTRO = "otro"

    @property
    def nombre(self) -> str:
        return {
            "adn": "ADN insuficiente",
            "volumen": "Volumen insuficiente (menos de 2 ml)",
            "otro": "Otro motivo",
        }[self.value]


class ErrorDeNuevaExtraccion(ValueError):
    """No se puede pedir la nueva extracción; el mensaje se muestra al administrativo."""


def muestra_vigente(estudio: Estudio) -> Muestra | None:
    """La última muestra del estudio: la de la extracción más reciente."""
    consulta = (
        sa.select(Muestra).where(Muestra.estudio_id == estudio.id).order_by(Muestra.id.desc())
    )
    return db.session.scalars(consulta).first()


def solicitar_nueva_extraccion(
    muestra: Muestra,
    motivo: MotivoNuevaExtraccion | str,
    administrativo: Usuario,
    detalle: str | None = None,
    ahora: datetime | None = None,
) -> Estudio:
    """E27.1 a E27.3: marca la muestra, pasa el estudio a Requiere nueva extracción y avisa.

    Con ADN o volumen la muestra queda marcada como insuficiente (insuficiente_motivo). Con
    "otro" no, porque la columna solo acepta esos dos motivos: el motivo y el detalle quedan
    igual en el historial de estados y en el registro de cambios. Avisa por mail al paciente y
    al médico tratante. Lanza ErrorDeNuevaExtraccion si quien la pide no es administrativo, si
    el motivo no es válido, si el estudio no está En viaje a Corea o si la muestra no es la
    vigente.
    """
    ahora = ahora or ahora_en_argentina()
    if not administrativo.tiene_rol(roles.ADMINISTRATIVO):
        raise ErrorDeNuevaExtraccion("Solo un administrativo pide una nueva extracción.")
    try:
        motivo = MotivoNuevaExtraccion(motivo)
    except ValueError:
        raise ErrorDeNuevaExtraccion("Elegí el motivo que informó el laboratorio.") from None
    estudio = muestra.estudio
    if estudio.estado != EstadoEstudio.EN_VIAJE_COREA:
        raise ErrorDeNuevaExtraccion(
            f"El estudio {estudio.codigo} está {estudio.estado.nombre}: la nueva extracción se "
            "pide cuando el laboratorio de Corea avisa que la muestra no sirve (En viaje a Corea)."
        )
    vigente = muestra_vigente(estudio)
    if vigente is None or vigente.id != muestra.id:
        raise ErrorDeNuevaExtraccion("Esa no es la última muestra del estudio.")

    detalle = (detalle or "").strip() or None
    texto = f"{motivo.nombre}: {detalle}" if detalle else motivo.nombre
    if motivo != MotivoNuevaExtraccion.OTRO:
        muestra.insuficiente_motivo = MotivoInsuficiente(motivo.value)
        muestra.insuficiente_en = ahora
    db.session.flush()
    registrar(
        Entidad.ESTUDIO,
        estudio.id,
        administrativo,
        Accion.MODIFICACION,
        {"muestra_insuficiente": (None, motivo.value)},
        detalle=texto,
    )
    cambiar_estado(estudio, EstadoEstudio.REQUIERE_NUEVA_EXTRACCION, administrativo, motivo=texto)

    paciente = estudio.paciente.usuario
    notificar(
        paciente,
        "Hace falta una nueva extracción",
        f"El laboratorio informó que tu muestra no sirve para el análisis ({texto}). Reservá un "
        "nuevo turno de extracción: no tenés que volver a pagar.",
        LINK_DE_MI_TURNO,
        estudio=estudio,
    )
    notificar(
        estudio.medico_tratante.usuario,
        "Nueva extracción de un paciente",
        f"El laboratorio informó que la muestra del estudio {estudio.codigo} de "
        f"{paciente.nombre_completo} no sirve ({texto}). El paciente tiene que volver a "
        "extraerse sangre.",
        f"/historial/estudios/{estudio.id}",
        estudio=estudio,
    )
    return estudio
