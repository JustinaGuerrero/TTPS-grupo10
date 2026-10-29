"""Demo de Apigen: un cliente en FastAPI que consume la API como lo haría el sistema de un grupo.

Uso, desde apigen/demo:
  pip install -r requirements.txt
  uvicorn main:app --reload
Después abran http://127.0.0.1:8000 (interfaz) o http://127.0.0.1:8000/docs (Swagger).

Usa la clave pública del archivo apigen/.env. Nunca necesita la secreta.
"""
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
URL = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
CLAVE = os.environ["SUPABASE_PUBLISHABLE_KEY"]
ESTATICOS = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Demo de Apigen",
    description="Cliente de ejemplo de Apigen (módulo 5, grupo 10). Cada endpoint llama a la API en Supabase.",
    version="1.0",
)
cliente = httpx.AsyncClient(base_url=URL, headers={"apikey": CLAVE}, timeout=5)


async def apigen(metodo, ruta, *, json=None, params=None, headers=None):
    """Único punto que habla con Apigen. Convierte sus errores en errores de esta API."""
    try:
        r = await cliente.request(metodo, ruta, json=json, params=params, headers=headers)
    except httpx.HTTPError:
        raise HTTPException(503, "Apigen no responde")
    if r.status_code >= 400:
        try:
            mensaje = r.json().get("message", r.text)
        except ValueError:
            mensaje = r.text
        raise HTTPException(r.status_code, mensaje)
    return r


# ---------------------------------------------------------------- patologías
@app.get("/api/patologias", tags=["Patologías"], summary="Las 6 base y las del grupo")
async def patologias(grupo: str | None = None):
    r = await apigen("POST", "/rpc/listar_patologias", json={"p_grupo_id": grupo})
    return r.json()


@app.get("/api/patologias/{codigo}/genes", tags=["Patologías"], summary="Genes de una patología")
async def genes_de_patologia(codigo: str, grupo: str | None = None):
    r = await apigen("POST", "/rpc/genes_por_patologia", json={"p_patologia": codigo, "p_grupo_id": grupo})
    return r.json()


class AltaPatologia(BaseModel):
    grupo: str = Field(examples=["grupo10"])
    codigo: str = Field(examples=["MPS3A"])
    nombre: str = Field(examples=["Mucopolisacaridosis tipo 3A"])
    genes: list[str] = Field(examples=[["NAGLU"]])
    herencia: str = Field("autosomica_recesiva",
                          examples=["autosomica_recesiva", "autosomica_dominante", "ligada_al_x"])


@app.post("/api/patologias", tags=["Patologías"], summary="Alta de una patología del grupo (gerente médico)")
async def alta_patologia(datos: AltaPatologia):
    r = await apigen("POST", "/rpc/alta_patologia", json={
        "p_grupo_id": datos.grupo, "p_codigo": datos.codigo, "p_nombre": datos.nombre,
        "p_genes": datos.genes, "p_herencia": datos.herencia})
    return r.json()[0]


# --------------------------------------------------------------------- genes
@app.get("/api/genes", tags=["Genes"], summary="Buscar genes mientras se escribe")
async def buscar_genes(q: str = Query(min_length=1, examples=["GA"]), limite: int = 15):
    q = re.sub(r"[^A-Za-z0-9._-]", "", q)
    if not q:
        return []
    r = await apigen("GET", "/gen", params={
        "simbolo": f"ilike.{q}*", "select": "simbolo", "order": "simbolo", "limit": limite})
    return [g["simbolo"] for g in r.json()]


@app.get("/api/genes-hallazgos", tags=["Genes"], summary="Los 84 genes ACMG")
async def genes_hallazgos():
    r = await apigen("GET", "/genes_hallazgos_secundarios", params={"select": "gen,condicion,herencia"})
    return r.json()


# ----------------------------------------------------------------- variantes
@app.get("/api/variantes", tags=["Variantes"], summary="Variantes de un gen, paginadas")
async def variantes(gen: str = Query(examples=["GAA"]), q: str = "", pagina: int = 0, tamano: int = 25):
    params = {"gen": f"eq.{gen}", "select": "id,hgvs_c,proteina,clasificacion",
              "order": "hgvs_c", "limit": tamano, "offset": pagina * tamano}
    q = q.strip().replace("*", "")
    if q:
        params["hgvs_c"] = f"ilike.*{q}*"
    r = await apigen("GET", "/variantes", params=params, headers={"Prefer": "count=exact"})
    rango = r.headers.get("content-range", "*/0")
    total = rango.split("/")[-1]
    return {"total": int(total) if total.isdigit() else None, "pagina": pagina, "variantes": r.json()}


class PedidoDiagnostico(BaseModel):
    patologia: str = Field(examples=["POMPE"])
    variantes: list[str] = Field(examples=[["c.-32-13T>G", "BRCA2:c.5946del"]])
    grupo: str | None = None


async def clasificacion_de(variante, genes_patologia):
    """Clasificación de una variante, para decidir si hay que reevaluar (regla del sistema, no de Apigen)."""
    gen, _, hgvs = variante.rpartition(":")
    params = {"hgvs_c": f"eq.{hgvs}", "select": "clasificacion", "limit": 1}
    if gen and not gen.startswith("NM_"):
        params["gen"] = f"eq.{gen}"
    elif not gen:
        params["gen"] = "in.(" + ",".join(genes_patologia) + ")"
    else:
        return None
    r = await apigen("GET", "/variantes", params=params)
    datos = r.json()
    return datos[0]["clasificacion"] if datos else None


@app.post("/api/diagnostico", tags=["Diagnóstico"],
          summary="Confirma el diagnóstico y busca hallazgos secundarios, como al finalizar un estudio")
async def diagnostico(pedido: PedidoDiagnostico):
    variantes = [v.strip() for v in pedido.variantes if v.strip()]
    genes = (await apigen("POST", "/rpc/genes_por_patologia",
                          json={"p_patologia": pedido.patologia, "p_grupo_id": pedido.grupo})).json()
    # positivo, portador o negativo. confirma_diagnostico es true solo si es positivo.
    resultado = (await apigen("POST", "/rpc/resultado_diagnostico", json={
        "p_patologia": pedido.patologia, "p_variantes": variantes, "p_grupo_id": pedido.grupo})).json()
    confirmado = resultado == "positivo"

    # Para hallazgos secundarios cada variante necesita el gen adelante
    con_gen = [v if ":" in v else f"{genes[0]}:{v}" for v in variantes] if len(genes) == 1 else \
              [v for v in variantes if ":" in v]
    hallazgos = (await apigen("POST", "/rpc/hallazgos_secundarios", json={
        "p_variantes": con_gen, "p_excluir_patologias": [pedido.patologia],
        "p_grupo_id": pedido.grupo})).json() if con_gen else []

    reevaluar = False
    if not confirmado:
        for v in variantes:
            if await clasificacion_de(v, genes) in ("vus", "probablemente_patogenica"):
                reevaluar = True
                break

    return {
        "patologia": pedido.patologia,
        "genes": genes,
        "resultado": resultado.capitalize(),
        "confirma_diagnostico": confirmado,
        "reevaluar_en_un_anio": reevaluar,
        "hallazgos_secundarios": hallazgos,
    }


# ------------------------------------------------------------------ interfaz
@app.get("/", include_in_schema=False)
async def inicio():
    return FileResponse(ESTATICOS / "index.html")
