"""Carga en Supabase las variantes de ClinVar de los genes de Apigen.

Uso: python cargar_clinvar.py variant_summary.txt.gz
"""
import csv
import gzip
import os
import sys
from collections import Counter

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
cliente = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# Decisión 3 de la guía: si solo cuenta "Pathogenic", sacar las otras dos.
PATOGENICAS = {"Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"}
BENIGNAS = {"Benign", "Likely benign", "Benign/Likely benign"}
VUS = {
    "Uncertain significance",
    "Conflicting classifications of pathogenicity",
    "Conflicting interpretations of pathogenicity",
}


def clasificar(valor):
    if valor in PATOGENICAS:
        return "patogenica"
    if valor in BENIGNAS:
        return "benigna"
    if valor in VUS:
        return "vus"
    return None  # "not provided", "drug response", etc.: no se carga


genes = {g["simbolo"] for g in cliente.table("gen").select("simbolo").execute().data}
filas = {}
descartadas = Counter()

csv.field_size_limit(2**31 - 1)
abrir = gzip.open if sys.argv[1].endswith(".gz") else open
with abrir(sys.argv[1], "rt", encoding="utf-8", newline="") as archivo:
    for r in csv.DictReader(archivo, delimiter="\t"):
        if r["Assembly"] != "GRCh38" or r["GeneSymbol"] not in genes:
            continue
        clase = clasificar(r["ClinicalSignificance"])
        if clase is None:
            descartadas[r["ClinicalSignificance"]] += 1
            continue
        filas[r["VariationID"]] = {
            "clinvar_id": r["VariationID"],
            "gen_simbolo": r["GeneSymbol"],
            "nombre": r["Name"],
            "clasificacion_clinvar": r["ClinicalSignificance"],
            "clasificacion": clase,
            "es_patogenica": clase == "patogenica",
        }

print(f"{len(filas)} variantes para cargar")
print("Clasificaciones descartadas:", descartadas.most_common(10))

lista = list(filas.values())
for i in range(0, len(lista), 1000):
    cliente.table("variante").upsert(lista[i : i + 1000]).execute()
    print(f"{min(i + 1000, len(lista))} de {len(lista)}")