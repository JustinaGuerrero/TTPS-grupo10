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

## Chatbot de pacientes (`chatbot/`)

Contrato en `docs/apis/chatbot.md`. Respuesta fija: no depende de la pregunta.

| Función | Archivo | Si no hay archivo |
| --- | --- | --- |
| `preguntar(texto)` | `respuesta.json` (tipo `respuesta`) | Error: "el chatbot no está disponible" |

Para simular el chatbot apagado, crear `respuesta.error.json` con `{"status": 503, "message": "..."}`.
Los tests de los demás errores (401, 429, 500, timeout) usan un `httpx.MockTransport`.

## Transcripción y familiograma

No tienen contrato publicado; se usan los borradores de `docs/apis/`.

| Función | Archivo | Resultado |
| --- | --- | --- |
| `transcribir(audio)` | `transcripcion/transcribir.json` | Texto transcripto |
| `generar(familiares)` | `familiograma/generar.json` | PDF de ejemplo en Base64 |

Para simular una falla, usar `transcribir.error.json` o `generar.error.json` con un status y un
mensaje, según el formato de arriba.

## API de cupones (`cupones/`)

Contrato en `docs/apis/cupones.md`.

| Función | Archivo | Si no hay archivo |
| --- | --- | --- |
| `generar(g, descuento, n)` | `generar.json` (10 cupones) | Error: no hay respuesta simulada |
| `asignar_a_medico(g, m, "X")` | `asignar_a_medico_X.json` | `asignar_a_medico.json`: `true` |
| `asignar_a_paciente(m, p, "X")` | `asignar_a_paciente_X.json` (`YACANJE1`: 409) | `asignar_a_paciente.json`: `true` |
| `consultar("X")` | `cupones_X.json` | `cupones.json`: listado con los códigos de prueba (`VENCIDO01` usado, `EXPIRADO1` vencido) |
| `canjear(p, "X")` | `canjear_X.json` (`CAIDO001`: 503) | `canjear.json`: `true` |

## Obras sociales (`obras_sociales/`)

Borrador en `docs/apis/obras_sociales.md`.

| Función | Archivo | Si no hay archivo |
| --- | --- | --- |
| `listar()` | `listar.json` (al 100 %, al 70 % y al 40 %) | Error: no hay respuesta simulada |
| `alta_estudio(...)` | `alta_estudio.json` (`MOD-OS-0001`) | Error: no hay respuesta simulada |
| `estado_estudio("X")` | `estado_estudio_X.json` | `estado_estudio.json`: `autorizado` |

