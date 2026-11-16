# Apigen (API de bioinformática, módulo 5)

El contrato completo y vigente es [apigen/contrato.md](../../apigen/contrato.md) (v1). Este archivo
solo lo enlaza, para que `/implementar-escenario` lo encuentre en `docs/apis/` sin tener dos copias
que se desactualicen.

Cliente del sistema: `sistema/src/integraciones/apigen.py`. Mocks: `sistema/tests/fixtures/apis/apigen/`.

| Endpoint del contrato | Función del cliente | Issue |
|---|---|---|
| 3. Genes por patología | `genes_de_patologia(patologia)` | #3 |
| 4. Genes de hallazgos secundarios (ACMG) | `genes_hallazgos_secundarios()` | #3 |
| 5. Variantes de un gen | `variantes_de_gen(gen, ...)` | #3 |
| 7. Resultado del diagnóstico | `resultado_diagnostico(patologia, variantes)` | #3 |
| 1 y 9. Patologías y alta de patología del grupo | Pendientes | #4 |
| 8 | Pendiente | #20 |

Configuración: `APIGEN_URL`, `APIGEN_KEY` (header `apikey`) y `APIGEN_GRUPO_ID` (por defecto
`grupo10`), que va como `p_grupo_id` en los endpoints que lo aceptan.
