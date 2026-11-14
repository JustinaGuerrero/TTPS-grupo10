"""Los 16 estados del estudio y sus transiciones, sacadas de "Estados del estudio" del LEL.

Es la fuente de la máquina de estados: cambiar_estado() (servicios.py) solo permite los pasos de
TRANSICIONES. Este archivo no usa la base ni Flask.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class TransicionInvalida(Exception):
    """El LEL no permite que el estudio pase del estado en que está al estado pedido."""


class EstadoEstudio(StrEnum):
    """Estado del estudio. El valor es el código que se guarda en la base (ver modelo-datos.md)."""

    CREADO = "creado"
    PRESUPUESTADO = "presupuestado"
    PENDIENTE_AUTORIZACION = "pendiente_autorizacion"
    RECHAZADO_OBRA_SOCIAL = "rechazado_obra_social"
    HABILITADO_TURNO = "habilitado_turno"
    TURNO_SACADO = "turno_sacado"
    LISTO_PARA_RETIRAR = "listo_para_retirar"
    EN_CAMINO_LABORATORIO = "en_camino_laboratorio"
    EN_LABORATORIO_CENTRAL = "en_laboratorio_central"
    PENDIENTE_AUTORIZACION_MINISTERIAL = "pendiente_autorizacion_ministerial"
    PENDIENTE_ENVIO = "pendiente_envio"
    EN_VIAJE_COREA = "en_viaje_corea"
    EN_AREA_BIOINFORMATICA = "en_area_bioinformatica"
    EN_ANALISIS = "en_analisis"
    FINALIZADO = "finalizado"
    REQUIERE_NUEVA_EXTRACCION = "requiere_nueva_extraccion"

    @property
    def nombre(self) -> str:
        """Nombre del estado en el LEL, para mostrar: "Pendiente de autorización"."""
        return _NOMBRES[self]


_E = EstadoEstudio

_NOMBRES = {
    _E.CREADO: "Creado",
    _E.PRESUPUESTADO: "Presupuestado",
    _E.PENDIENTE_AUTORIZACION: "Pendiente de autorización",
    _E.RECHAZADO_OBRA_SOCIAL: "Rechazado por obra social",
    _E.HABILITADO_TURNO: "Habilitado para turno",
    _E.TURNO_SACADO: "Turno sacado",
    _E.LISTO_PARA_RETIRAR: "Listo para retirar",
    _E.EN_CAMINO_LABORATORIO: "En camino al laboratorio central",
    _E.EN_LABORATORIO_CENTRAL: "En laboratorio central",
    _E.PENDIENTE_AUTORIZACION_MINISTERIAL: "Pendiente de autorización ministerial",
    _E.PENDIENTE_ENVIO: "Pendiente de envío",
    _E.EN_VIAJE_COREA: "En viaje a Corea",
    _E.EN_AREA_BIOINFORMATICA: "En área de bioinformática",
    _E.EN_ANALISIS: "En análisis",
    _E.FINALIZADO: "Finalizado",
    _E.REQUIERE_NUEVA_EXTRACCION: "Requiere nueva extracción",
}

# Estado de origen → {estado de destino: impacto del LEL que provoca el paso}. Son las 21
# transiciones de los impactos de cada estado del estudio. Ninguna vuelve a Creado.
_TRANSICIONES = {
    _E.CREADO: {
        _E.PRESUPUESTADO: "El administrativo emite el presupuesto",
    },
    _E.PRESUPUESTADO: {
        _E.HABILITADO_TURNO: "El paciente paga el estudio de forma particular",
        _E.PENDIENTE_AUTORIZACION: "El paciente elige la cobertura de su obra social",
    },
    _E.PENDIENTE_AUTORIZACION: {
        _E.HABILITADO_TURNO: "El administrativo registra la autorización",
        _E.RECHAZADO_OBRA_SOCIAL: "El administrativo registra el rechazo",
    },
    _E.RECHAZADO_OBRA_SOCIAL: {
        _E.PENDIENTE_AUTORIZACION: "El paciente carga la demanda de reautorización",
    },
    _E.HABILITADO_TURNO: {
        _E.TURNO_SACADO: "El paciente reserva un turno de extracción",
    },
    _E.TURNO_SACADO: {
        _E.LISTO_PARA_RETIRAR: "El centro de extracción envía el mensaje de muestra tomada",
        # También el sistema, si el paciente no asiste (supuesto O7 de decisiones.md).
        _E.HABILITADO_TURNO: "El paciente cancela el turno",
    },
    _E.LISTO_PARA_RETIRAR: {
        _E.EN_CAMINO_LABORATORIO: "El transportista registra el retiro de las muestras del centro",
    },
    _E.EN_CAMINO_LABORATORIO: {
        _E.EN_LABORATORIO_CENTRAL: "El transportista registra la llegada al laboratorio central",
    },
    _E.EN_LABORATORIO_CENTRAL: {
        _E.PENDIENTE_AUTORIZACION_MINISTERIAL: "El sistema cierra el sample set de la muestra",
        _E.REQUIERE_NUEVA_EXTRACCION: "El administrativo registra un volumen menor a 2 ml",
    },
    _E.PENDIENTE_AUTORIZACION_MINISTERIAL: {
        _E.PENDIENTE_ENVIO: "El Ministerio de Salud devuelve el PDF de autorización",
    },
    _E.PENDIENTE_ENVIO: {
        _E.EN_VIAJE_COREA: "FedEx retira el sample set",
    },
    _E.EN_VIAJE_COREA: {
        _E.EN_AREA_BIOINFORMATICA: "El administrativo carga los datos crudos",
        _E.REQUIERE_NUEVA_EXTRACCION: "El administrativo registra que el ADN es insuficiente",
    },
    _E.EN_AREA_BIOINFORMATICA: {
        _E.EN_ANALISIS: "El bioinformático toma el estudio",
    },
    _E.EN_ANALISIS: {
        _E.FINALIZADO: "El bioinformático registra las variantes y finaliza el análisis",
    },
    _E.FINALIZADO: {
        _E.EN_AREA_BIOINFORMATICA: "El médico tratante solicita un reanálisis",
    },
    _E.REQUIERE_NUEVA_EXTRACCION: {
        _E.TURNO_SACADO: "El paciente reserva un nuevo turno",
    },
}

# De solo lectura, para que ningún módulo agregue una transición por fuera del LEL.
TRANSICIONES: Mapping[EstadoEstudio, Mapping[EstadoEstudio, str]] = MappingProxyType(
    {origen: MappingProxyType(destinos) for origen, destinos in _TRANSICIONES.items()}
)


def puede_pasar(origen: EstadoEstudio, destino: EstadoEstudio) -> bool:
    """True si el LEL permite que un estudio en `origen` pase a `destino`."""
    return destino in TRANSICIONES.get(origen, {})
