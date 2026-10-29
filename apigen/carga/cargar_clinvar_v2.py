"""Carga en Supabase los genes y las variantes de ClinVar (Apigen v1).

Uso, desde apigen/carga:
  python cargar_clinvar_v2.py variant_summary.txt.gz --medir            # solo cuenta, no sube nada
  python cargar_clinvar_v2.py variant_summary.txt.gz --cargar           # carga recomendada
  python cargar_clinvar_v2.py variant_summary.txt.gz --cargar --con-vus # también las VUS del resto del genoma
  python cargar_clinvar_v2.py variant_summary.txt.gz --cargar --todas   # todas las clasificaciones de todos los genes

Qué carga:
  - En la tabla gen: todos los genes de ClinVar con variantes de un solo gen (unos 20.000).
  - En la tabla variante, para los genes de Apigen, todas las clasificaciones. Son los genes
    de las 6 patologías base, los 84 de la lista ACMG y los de las patologías que dieron de
    alta los grupos.
  - Para el resto del genoma, solo patogénicas y probablemente patogénicas, para no pasarse
    de los 500 MB del plan gratuito. Con --con-vus suma las VUS; con --todas carga todo.

Si un grupo da de alta una patología con genes nuevos, vuelvan a correr --cargar: suma
las VUS y benignas de esos genes sin duplicar nada.

La traducción de clasificaciones se lee de la tabla clasificacion de la base:
el script no tiene ninguna regla escrita adentro.
"""
import argparse
import csv
import gzip
import os
import re
import sys
import time
from collections import Counter

from dotenv import load_dotenv
from supabase import create_client

# NM_000152.5(GAA):c.-32-13T>G (p.Leu12fs)  ->  transcripto, gen, hgvs_c, proteína
NOMBRE = re.compile(r"^(NM_\d+\.\d+)\(([^)]+)\):(c\.\S+)(?:\s+\((p\.[^)]*)\))?")
CLASES_RESTO_DEL_GENOMA = {"patogenica", "probablemente_patogenica"}
BYTES_POR_FILA = 180    # estimado por variante, contando los índices
LIMITE_MB = 400         # margen dentro de los 500 MB del plan gratuito
LOTE_GENES = 1000
LOTE_VARIANTES = 2000


def abrir(ruta):
    if ruta.endswith(".gz"):
        return gzip.open(ruta, "rt", encoding="utf-8", newline="")
    return open(ruta, "rt", encoding="utf-8", newline="")


def leer_filas(ruta):
    """Devuelve (fila, gen, match del nombre) de las variantes GRCh38 de un solo gen."""
    csv.field_size_limit(2**31 - 1)
    with abrir(ruta) as archivo:
        for r in csv.DictReader(archivo, delimiter="\t"):
            if r["Assembly"] != "GRCh38":
                continue
            gen = r["GeneSymbol"]
            if not gen or gen == "-" or ";" in gen:
                continue
            m = NOMBRE.match(r["Name"])
            if not m:
                continue
            yield r, gen, m


def con_reintentos(funcion, intentos=4):
    for i in range(intentos):
        try:
            return funcion()
        except Exception as error:  # red o Supabase momentáneamente caídos
            if i == intentos - 1:
                raise
            espera = 2 ** (i + 1)
            print(f"  Falló un lote ({error}). Reintento en {espera} s…")
            time.sleep(espera)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archivo")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--medir", action="store_true", help="cuenta y estima el tamaño, sin subir nada")
    modo.add_argument("--cargar", action="store_true", help="sube genes y variantes")
    alcance = parser.add_mutually_exclusive_group()
    alcance.add_argument("--con-vus", action="store_true", help="también las VUS del resto del genoma")
    alcance.add_argument("--todas", action="store_true", help="todas las clasificaciones de todos los genes")
    args = parser.parse_args()

    load_dotenv()
    cliente = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    clasificaciones = {
        c["valor_clinvar"]: (c["id"], c["clasificacion"])
        for c in cliente.table("clasificacion").select("*").execute().data
    }
    genes_apigen = {g["simbolo"] for g in cliente.table("gen").select("simbolo")
                    .eq("es_hallazgo_secundario", True).execute().data}
    genes_apigen |= {g["gen_simbolo"] for g in cliente.table("patologia_gen").select("gen_simbolo").execute().data}
    genes_apigen |= {g["gen_simbolo"] for g in cliente.table("patologia_grupo_gen").select("gen_simbolo").execute().data}
    print(f"Genes de Apigen (con todas las clasificaciones): {len(genes_apigen)}")

    def recomendada(gen, clase):
        return gen in genes_apigen or clase in CLASES_RESTO_DEL_GENOMA

    def se_carga(gen, clase):
        if args.todas:
            return True
        if args.con_vus and clase == "vus":
            return True
        return recomendada(gen, clase)

    # Pasada 1: genes y conteos
    print("Leyendo el archivo (pasada 1 de 2)…" if args.cargar else "Leyendo el archivo…")
    genes = set()
    vistos = set()
    por_clase = Counter()
    recomendadas = 0
    con_vus = 0
    todas = 0
    descartadas = Counter()
    for r, gen, m in leer_filas(args.archivo):
        genes.add(gen)
        clase = clasificaciones.get(r["ClinicalSignificance"])
        if clase is None:
            descartadas[r["ClinicalSignificance"]] += 1
            continue
        vid = int(r["VariationID"])
        if vid in vistos:
            continue
        vistos.add(vid)
        todas += 1
        por_clase[clase[1]] += 1
        if recomendada(gen, clase[1]):
            recomendadas += 1
        if recomendada(gen, clase[1]) or clase[1] == "vus":
            con_vus += 1

    mb_rec = recomendadas * BYTES_POR_FILA / 1e6
    mb_vus = con_vus * BYTES_POR_FILA / 1e6
    mb_todas = todas * BYTES_POR_FILA / 1e6
    print(f"\nGenes: {len(genes):,}")
    print("Variantes por clasificación:", dict(por_clase))
    print(f"Carga recomendada:   {recomendadas:,} variantes, unos {mb_rec:,.0f} MB")
    print(f"Carga con --con-vus: {con_vus:,} variantes, unos {mb_vus:,.0f} MB")
    print(f"Carga con --todas:   {todas:,} variantes, unos {mb_todas:,.0f} MB")
    print("Valores de ClinVar que no están en la tabla clasificacion (no se cargan):")
    for valor, cantidad in descartadas.most_common(12):
        print(f"  {cantidad:>9,}  {valor}")

    if args.medir:
        if mb_todas <= LIMITE_MB:
            print("\nEntra todo: pueden cargar con --cargar --todas.")
        elif mb_vus <= LIMITE_MB:
            print("\nCon --todas no entra. Carguen con --cargar --con-vus.")
        elif mb_rec <= LIMITE_MB:
            print("\nSolo entra la recomendada. Carguen con --cargar (sin nada más).")
        else:
            print("\nNi la carga recomendada entra cómoda. Avisen antes de cargar.")
        return

    # Genes primero, porque las variantes los referencian
    print(f"\nSubiendo {len(genes):,} genes…")
    lista_genes = sorted(genes)
    for i in range(0, len(lista_genes), LOTE_GENES):
        lote = [{"simbolo": g} for g in lista_genes[i:i + LOTE_GENES]]
        con_reintentos(lambda: cliente.table("gen")
                       .upsert(lote, on_conflict="simbolo", ignore_duplicates=True).execute())

    # Pasada 2: variantes, en lotes
    total = todas if args.todas else con_vus if args.con_vus else recomendadas
    print(f"Subiendo {total:,} variantes (pasada 2 de 2)…")
    inicio = time.time()
    lote = {}
    subidas = 0

    def subir(filas):
        con_reintentos(lambda: cliente.table("variante")
                       .upsert(filas, on_conflict="clinvar_id").execute())

    for r, gen, m in leer_filas(args.archivo):
        clase = clasificaciones.get(r["ClinicalSignificance"])
        if clase is None or not se_carga(gen, clase[1]):
            continue
        vid = int(r["VariationID"])
        lote[vid] = {
            "clinvar_id": vid,
            "gen_simbolo": gen,
            "transcripto": m.group(1),
            "hgvs_c": m.group(3),
            "proteina": m.group(4),
            "clasificacion_id": clase[0],
        }
        if len(lote) >= LOTE_VARIANTES:
            subir(list(lote.values()))
            subidas += len(lote)
            lote = {}
            if subidas % 50_000 < LOTE_VARIANTES:
                minutos = (time.time() - inicio) / 60
                print(f"  {subidas:,} de {total:,} ({minutos:.1f} min)")
    if lote:
        subir(list(lote.values()))
        subidas += len(lote)

    print(f"Listo: {subidas:,} variantes en {(time.time() - inicio) / 60:.1f} min.")


if __name__ == "__main__":
    sys.exit(main())
