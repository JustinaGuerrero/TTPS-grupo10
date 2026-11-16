# Respuestas simuladas de las APIs externas

Con `USE_MOCKS=1` (siempre en los tests) los clientes de `src/integraciones/` no llaman a las APIs:
leen la respuesta de `tests/fixtures/apis/<api>/<clave>.json`. Cada función del cliente elige la
clave; si existe `<clave>.error.json`, simula ese error.

```json
{"status": 400, "message": "Patología inexistente: MPS2"}
```

## Apigen (`apigen/`)

Respuestas armadas con los ejemplos de `apigen/contrato.md`. Son datos de prueba, no un extracto
completo de ClinVar ni de la lista ACMG.

| Función | Archivo | Si no hay archivo |
| --- | --- | --- |
| `genes_de_patologia("POMPE")` | `genes_por_patologia_POMPE.json` | Error: no hay respuesta simulada |
| `genes_hallazgos_secundarios()` | `genes_hallazgos_secundarios.json` (8 de los 84 genes) | — |
| `variantes_de_gen("GAA")` | `variantes_GAA.json` (sin filtros ni paginación) | `variantes.json`: `[]` |
| `resultado_diagnostico("POMPE", …)` | `resultado_diagnostico_POMPE.json` (no mira las variantes) | `resultado_diagnostico.json`: `"negativo"` |

`genes_por_patologia_MPS2.error.json` simula la patología que Apigen sacó en la v1.

## Módulo de cupones (`cupones/`)

Contrato provisorio en `docs/apis/cupones.md`.

| Función | Archivo | Si no hay archivo |
| --- | --- | --- |
| `generar(descuento, n)` | `generar.json` (10 cupones con PDF) | Error: no hay respuesta simulada |
| `consultar("X")` | `consultar_X.json` (`VENCIDO01` está utilizado) | `consultar.json`: vigente |
| `vencer("X")` | `vencer_X.json` (`CAIDO001` da error 503) | `vencer.json` |
