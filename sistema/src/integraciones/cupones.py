"""Cliente de la API de cupones (Exoma Care), según docs/apis/cupones.md (guía v2).

El módulo es compartido por todos los grupos: la clave de cada grupo (CUPONES_KEY, header
X-API-Key) lo identifica, así que nunca se manda p_grupo_id. Los ids de personas son texto y el
módulo no los verifica; acá se arman con el id de nuestras tablas: G-<usuario>, M-<médico> y
P-<paciente>.

- generar(gerente_id, 20, 3)                       → [CuponGenerado(codigo, porcentaje)]
- asignar_a_medico(gerente_id, medico_id, codigo)  → None
- asignar_a_paciente(medico_id, paciente_id, codigo) → None
- consultar(codigo, medico_id=7)                   → CuponEnModulo | None
- canjear(paciente_id, codigo)                     → None

Todas lanzan ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar; el
`status` conserva el código HTTP (403 gerente ajeno, 404 no corresponde, 409 ya usado o paciente
con cupón previo). Con USE_MOCKS=1 responden con los archivos de tests/fixtures/apis/cupones/.
Cada función acepta `cliente=` para los tests. Las escrituras no se reintentan: ante un timeout
hay que consultar el estado primero.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from flask import current_app

from src.integraciones.base import ClienteApi

NOMBRE = "Cupones"
URL_POR_DEFECTO = "https://vekuhonbpqtzakqbcoph.supabase.co/functions/v1/cupones-api"
LIMITE_POR_PAGINA = 100
MAXIMO_DE_PAGINAS = 50


@dataclass(frozen=True)
class CuponGenerado:
    codigo: str
    porcentaje: Decimal


@dataclass(frozen=True)
class CuponEnModulo:
    codigo: str
    # disponible, medico, paciente o usado: el módulo es el que manda.
    estado: str
    porcentaje: Decimal | None
    fecha_vencimiento: date | None
    paciente_id: str | None

    @property
    def vencido(self) -> bool:
        return self.fecha_vencimiento is not None and self.fecha_vencimiento < _hoy()


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    return ClienteApi(
        NOMBRE,
        config.get("CUPONES_URL") or URL_POR_DEFECTO,
        headers={"X-API-Key": config.get("CUPONES_KEY") or ""},
        usar_mocks=bool(config.get("USE_MOCKS")),
    )


def generar(
    gerente_id: int, descuento: int | Decimal, cantidad: int, *, cliente: ClienteApi | None = None
) -> list[CuponGenerado]:
    """Pide un lote de `cantidad` cupones con ese descuento porcentual (vencen a los 30 días)."""
    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.post(
        "generar_cupones_gerencia",
        json={
            "p_gerente_id": _id("G", gerente_id),
            "p_cantidad": cantidad,
            "p_porcentaje_descuento": float(descuento),
        },
        mock="generar",
    )
    datos = respuesta.datos
    if not isinstance(datos, list) or len(datos) < cantidad:
        raise cliente.formato_inesperado()
    try:
        return [
            CuponGenerado(_codigo(item["codigo_cupon"]), Decimal(str(item["porcentaje"])))
            for item in datos[:cantidad]
        ]
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise cliente.formato_inesperado() from None


def asignar_a_medico(
    gerente_id: int, medico_id: int, codigo: str, *, cliente: ClienteApi | None = None
) -> None:
    """El gerente asigna un cupón disponible a un médico (el cupón pasa a `medico`)."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    cliente.post(
        "asignar_cupon_a_medico",
        json={
            "p_gerente_id": _id("G", gerente_id),
            "p_medico_id": _id("M", medico_id),
            "p_codigo": codigo,
        },
        mock=[f"asignar_a_medico_{codigo}", "asignar_a_medico"],
    )


def asignar_a_paciente(
    medico_id: int, paciente_id: int, codigo: str, *, cliente: ClienteApi | None = None
) -> None:
    """El médico asigna un cupón suyo a un paciente (pasa a `paciente`; 409 si ya tuvo uno)."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    cliente.post(
        "asignar_cupon_a_paciente",
        json={
            "p_medico_id": _id("M", medico_id),
            "p_paciente_id": _id("P", paciente_id),
            "p_codigo": codigo,
        },
        mock=[f"asignar_a_paciente_{codigo}", "asignar_a_paciente"],
    )


def consultar(
    codigo: str, *, medico_id: int | None = None, cliente: ClienteApi | None = None
) -> CuponEnModulo | None:
    """El cupón con ese código según el módulo, o None si no está entre los del grupo.

    El módulo no consulta por código: se recorre el listado del grupo (filtrado por médico si se
    da) hasta encontrarlo.
    """
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    desde = 0
    for _ in range(MAXIMO_DE_PAGINAS):
        params = {"limit": LIMITE_POR_PAGINA, "offset": desde}
        if medico_id is not None:
            params["medico_id"] = _id("M", medico_id)
        datos = cliente.get("cupones", params=params, mock=[f"cupones_{codigo}", "cupones"]).datos
        try:
            items, total = datos["items"], int(datos["total"])
            for item in items:
                if item["codigo"] == codigo:
                    return _cupon(item)
        except (KeyError, TypeError, ValueError):
            raise cliente.formato_inesperado() from None
        desde += LIMITE_POR_PAGINA
        if not items or desde >= total:
            return None
    return None


def canjear(paciente_id: int, codigo: str, *, cliente: ClienteApi | None = None) -> None:
    """Informa el uso del cupón. El módulo valida grupo, paciente, estado y vencimiento (409 si ya
    se usó) y no cobra nada."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    cliente.post(
        "canjear_cupon",
        json={"p_paciente_id": _id("P", paciente_id), "p_codigo": codigo},
        mock=[f"canjear_{codigo}", "canjear"],
    )


def _cupon(item: dict) -> CuponEnModulo:
    porcentaje = item.get("porcentaje_descuento")
    vencimiento = item.get("fecha_vencimiento")
    return CuponEnModulo(
        codigo=item["codigo"],
        estado=item["estado"],
        porcentaje=Decimal(str(porcentaje)) if porcentaje is not None else None,
        fecha_vencimiento=date.fromisoformat(vencimiento[:10]) if vencimiento else None,
        paciente_id=item.get("paciente_id"),
    )


def _hoy() -> date:
    return datetime.now(UTC).date()


def _id(prefijo: str, numero: int) -> str:
    return f"{prefijo}-{int(numero)}"


def _codigo(codigo: str) -> str:
    codigo = str(codigo or "").strip()
    if not codigo or len(codigo) > 200 or any(c.isspace() for c in codigo):
        raise ValueError(f"Código de cupón inválido: {codigo!r}")
    return codigo
