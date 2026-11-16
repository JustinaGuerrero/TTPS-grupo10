"""Cliente de Apigen, la API de bioinformática (módulo 5), según apigen/contrato.md (v1).

Funciones que usa el sistema:

- genes_de_patologia("POMPE")                 → ["GAA"]                     (endpoint 3)
- genes_hallazgos_secundarios()               → [GenAcmg(...), ...]         (endpoint 4)
- variantes_de_gen("GAA", texto="32-13")      → PaginaDeVariantes(...)       (endpoint 5)
- resultado_diagnostico("POMPE", ["GAA:c…"])  → ResultadoDiagnostico.PORTADOR (endpoint 7)

Todas lanzan ErrorDeIntegracion (src/integraciones/base.py) con un mensaje para mostrar si
Apigen no responde, rechaza el pedido o devuelve algo fuera del contrato. Con USE_MOCKS=1
responden con los archivos de tests/fixtures/apis/apigen/.

Cada función acepta `cliente=` para los tests; si no se pasa, se arma con APIGEN_URL,
APIGEN_KEY y USE_MOCKS de la configuración de la app. Los endpoints que lo piden reciben
APIGEN_GRUPO_ID como p_grupo_id.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from flask import current_app, has_app_context

from src.integraciones.base import ClienteApi

NOMBRE = "Apigen"
# Identificador de nuestro grupo (APIGEN_GRUPO_ID): Apigen solo nos muestra las patologías que
# cargamos nosotros (E36) si lo mandamos. Sin él, solo existen las 5 base.
GRUPO_ID_POR_DEFECTO = "grupo10"
# Supabase devuelve como máximo 1000 filas por pedido.
LIMITE_MAXIMO_DE_VARIANTES = 1000


class Clasificacion(StrEnum):
    PATOGENICA = "patogenica"
    PROBABLEMENTE_PATOGENICA = "probablemente_patogenica"
    VUS = "vus"
    BENIGNA = "benigna"


class ResultadoDiagnostico(StrEnum):
    POSITIVO = "positivo"
    PORTADOR = "portador"
    NEGATIVO = "negativo"


class Herencia(StrEnum):
    AUTOSOMICA_RECESIVA = "autosomica_recesiva"
    AUTOSOMICA_DOMINANTE = "autosomica_dominante"
    LIGADA_AL_X = "ligada_al_x"


@dataclass(frozen=True)
class PatologiaApigen:
    """Patología tal como la devuelve el alta (endpoint 9)."""

    codigo: str
    nombre: str
    herencia: Herencia
    genes: list[str]


@dataclass(frozen=True)
class GenAcmg:
    """Gen de la lista ACMG de hallazgos secundarios."""

    gen: str
    condicion: str
    # dominante, recesiva o ligada_x
    herencia: str


@dataclass(frozen=True)
class Variante:
    # Identificador listo para mandar a resultado_diagnostico, por ejemplo "GAA:c.-32-13T>G".
    id: str
    hgvs_c: str
    proteina: str | None
    clasificacion: Clasificacion


@dataclass(frozen=True)
class PaginaDeVariantes:
    variantes: list[Variante]
    # Total de variantes que cumplen el filtro, no solo las de esta página.
    total: int
    limite: int
    desde: int

    @property
    def hay_siguiente(self) -> bool:
        return self.desde + len(self.variantes) < self.total


def cliente_por_defecto() -> ClienteApi:
    config = current_app.config
    clave = config.get("APIGEN_KEY") or ""
    return ClienteApi(
        NOMBRE,
        config.get("APIGEN_URL"),
        # La clave va en el header apikey, no como Authorization: Bearer (contrato, Conexión).
        headers={"apikey": clave},
        usar_mocks=bool(config.get("USE_MOCKS")),
    )


def genes_de_patologia(patologia: str, *, cliente: ClienteApi | None = None) -> list[str]:
    """Genes que hay que estudiar para la patología (código como "POMPE", base o del grupo)."""
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(patologia)
    respuesta = cliente.post(
        "rpc/genes_por_patologia",
        json={"p_patologia": codigo, "p_grupo_id": grupo_id()},
        mock=f"genes_por_patologia_{codigo}",
    )
    genes = respuesta.datos
    if not isinstance(genes, list) or not all(isinstance(gen, str) for gen in genes):
        raise cliente.formato_inesperado()
    return genes


def genes_hallazgos_secundarios(*, cliente: ClienteApi | None = None) -> list[GenAcmg]:
    """Los genes de la lista ACMG SF que se informan como hallazgos secundarios."""
    cliente = cliente or cliente_por_defecto()
    respuesta = cliente.get(
        "genes_hallazgos_secundarios",
        params={"select": "gen,condicion,herencia", "order": "gen"},
        mock="genes_hallazgos_secundarios",
    )
    try:
        return [
            GenAcmg(gen=fila["gen"], condicion=fila["condicion"], herencia=fila["herencia"])
            for fila in respuesta.datos
        ]
    except (KeyError, TypeError):
        raise cliente.formato_inesperado() from None


def variantes_de_gen(
    gen: str,
    *,
    texto: str | None = None,
    clasificacion: Clasificacion | str | None = None,
    limite: int = 50,
    desde: int = 0,
    cliente: ClienteApi | None = None,
) -> PaginaDeVariantes:
    """Variantes conocidas (ClinVar) de un gen, ordenadas por nombre HGVS y paginadas.

    `texto` busca dentro del nombre HGVS mientras el usuario escribe ("32-13").
    `limite` va de 1 a 1000. Con USE_MOCKS=1 no se aplican los filtros ni la paginación: se
    devuelve el archivo variantes_<GEN>.json entero.
    """
    cliente = cliente or cliente_por_defecto()
    simbolo = (gen or "").strip().upper()
    if not simbolo:
        raise ValueError("Falta el gen.")
    if not 1 <= limite <= LIMITE_MAXIMO_DE_VARIANTES:
        raise ValueError(f"El límite va de 1 a {LIMITE_MAXIMO_DE_VARIANTES}.")
    if desde < 0:
        raise ValueError("`desde` no puede ser negativo.")

    params = {
        "gen": f"eq.{simbolo}",
        "select": "id,hgvs_c,proteina,clasificacion",
        "order": "hgvs_c",
        "limit": limite,
        "offset": desde,
    }
    # * es el comodín de PostgREST: se saca del texto para que no cambie la búsqueda.
    texto = (texto or "").replace("*", "").strip()
    if texto:
        params["hgvs_c"] = f"ilike.*{texto}*"
    if clasificacion:
        params["clasificacion"] = f"eq.{Clasificacion(clasificacion)}"

    respuesta = cliente.get(
        "variantes",
        params=params,
        # El total viene en Content-Range, por ejemplo 0-49/3672.
        headers={"Prefer": "count=exact"},
        mock=[f"variantes_{simbolo}", "variantes"],
    )
    try:
        variantes = [
            Variante(
                id=fila["id"],
                hgvs_c=fila["hgvs_c"],
                proteina=fila.get("proteina"),
                clasificacion=Clasificacion(fila["clasificacion"]),
            )
            for fila in respuesta.datos
        ]
    except (KeyError, TypeError, ValueError, AttributeError):
        raise cliente.formato_inesperado() from None
    total = _total_de(respuesta.headers.get("content-range"))
    if total is None:
        total = desde + len(variantes)
    return PaginaDeVariantes(variantes, total, limite, desde)


def resultado_diagnostico(
    patologia: str,
    variantes: Iterable[str],
    *,
    cliente: ClienteApi | None = None,
) -> ResultadoDiagnostico:
    """Positivo, portador o negativo para la patología según las variantes encontradas.

    Las variantes van como "GEN:c.…" (recomendado) o "c.…"; una homocigota se manda dos veces.
    Con USE_MOCKS=1 el resultado depende solo de la patología (resultado_diagnostico_<COD>.json)
    y es negativo si no hay archivo para ella.
    """
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(patologia)
    lista = [variante.strip() for variante in variantes if variante and variante.strip()]
    respuesta = cliente.post(
        "rpc/resultado_diagnostico",
        json={"p_patologia": codigo, "p_variantes": lista, "p_grupo_id": grupo_id()},
        mock=[f"resultado_diagnostico_{codigo}", "resultado_diagnostico"],
    )
    try:
        return ResultadoDiagnostico(respuesta.datos)
    except (ValueError, TypeError):
        raise cliente.formato_inesperado() from None


def buscar_genes(texto: str, *, limite: int = 15, cliente: ClienteApi | None = None) -> list[str]:
    """Símbolos de genes que empiezan con `texto`, para elegirlos al dar de alta una patología.

    Con USE_MOCKS=1 se devuelve buscar_genes.json entero, sin filtrar por `texto`.
    """
    cliente = cliente or cliente_por_defecto()
    if not 1 <= limite <= LIMITE_MAXIMO_DE_VARIANTES:
        raise ValueError(f"El límite va de 1 a {LIMITE_MAXIMO_DE_VARIANTES}.")
    # Solo caracteres de un símbolo de gen: evita que el texto cambie el filtro de PostgREST.
    simbolo = re.sub(r"[^A-Za-z0-9._-]", "", texto or "")
    if not simbolo:
        return []
    respuesta = cliente.get(
        "gen",
        params={
            "simbolo": f"ilike.{simbolo}*",
            "select": "simbolo",
            "order": "simbolo",
            "limit": limite,
        },
        mock="buscar_genes",
    )
    try:
        return [fila["simbolo"] for fila in respuesta.datos]
    except (KeyError, TypeError):
        raise cliente.formato_inesperado() from None


def alta_patologia(
    codigo: str,
    nombre: str,
    genes: Iterable[str],
    herencia: Herencia | str = Herencia.AUTOSOMICA_RECESIVA,
    *,
    cliente: ClienteApi | None = None,
) -> PatologiaApigen:
    """Da de alta (o actualiza) una patología propia del grupo en Apigen (E36).

    Si el código ya existe en el grupo, Apigen actualiza nombre, genes y herencia.
    Con USE_MOCKS=1 se devuelve siempre alta_patologia.json.
    """
    cliente = cliente or cliente_por_defecto()
    codigo = _codigo(codigo)
    if not re.fullmatch(r"[A-Z0-9_]{2,30}", codigo):
        raise ValueError("El código va en mayúsculas, números o _, de 2 a 30 caracteres.")
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre de la patología.")
    lista_de_genes = [gen.strip().upper() for gen in genes if gen and gen.strip()]
    if not lista_de_genes:
        raise ValueError("Falta al menos un gen.")
    herencia = Herencia(herencia)

    respuesta = cliente.post(
        "rpc/alta_patologia",
        json={
            "p_grupo_id": grupo_id(),
            "p_codigo": codigo,
            "p_nombre": nombre,
            "p_genes": lista_de_genes,
            "p_herencia": herencia.value,
        },
        mock="alta_patologia",
    )
    try:
        fila = respuesta.datos[0]
        return PatologiaApigen(
            codigo=fila["codigo"],
            nombre=fila["nombre"],
            herencia=Herencia(fila["herencia"]),
            genes=list(fila["genes"]),
        )
    except (KeyError, IndexError, TypeError, ValueError):
        raise cliente.formato_inesperado() from None


def grupo_id() -> str:
    """El p_grupo_id que se manda a Apigen: APIGEN_GRUPO_ID, o grupo10 fuera de una app."""
    if has_app_context():
        return current_app.config.get("APIGEN_GRUPO_ID") or GRUPO_ID_POR_DEFECTO
    return GRUPO_ID_POR_DEFECTO


def _codigo(patologia: str) -> str:
    codigo = (patologia or "").strip().upper()
    if not codigo:
        raise ValueError("Falta el código de la patología.")
    return codigo


def _total_de(content_range: str | None) -> int | None:
    """El total de un Content-Range de PostgREST: "0-49/3672" → 3672; "*/0" → 0."""
    if not content_range or "/" not in content_range:
        return None
    total = content_range.rsplit("/", 1)[1]
    return int(total) if total.isdigit() else None
