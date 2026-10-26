# Contrato: Apigen v0

Todos los endpoints son de **solo lectura**. Ningún grupo puede escribir ni borrar datos.

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1` |
| Clave | `sb_publishable_Ogyld01ST0Gu8zlPBjLmow_9FYtNamo` |
| Header | `apikey: <clave>` en cada request |

La clave va en el header `apikey`, **no** como `Authorization: Bearer`. No hace falta instalar ninguna librería: alcanza con cualquier cliente HTTP (`fetch`, `requests`, `axios`).

Recomendaciones para consumirlo:

- Centralicen todas las llamadas a Apigen en un solo archivo de su proyecto.
- Usen siempre un timeout (5 segundos alcanza), para que su sistema no se cuelgue si el nuestro no responde.
- Para trabajar sin red, armen un mock con las respuestas de ejemplo de este contrato.

## Valores fijos

### Códigos de patología

| Código | Patología | Gen |
| --- | --- | --- |
| `FABRY` | Enfermedad de Fabry | GLA |
| `POMPE` | Enfermedad de Pompe | GAA |
| `GAUCHER` | Enfermedad de Gaucher | GBA1 |
| `MPS1` | Mucopolisacaridosis tipo 1 | IDUA |
| `MPS2` | Mucopolisacaridosis tipo 2 | IDS |
| `ASMD` | Déficit de esfingomielinasa ácida | SMPD1 |

### Clasificaciones de variante

| Valor | Qué incluye de ClinVar |
| --- | --- |
| `patogenica` | Pathogenic, Likely pathogenic |
| `benigna` | Benign, Likely benign |
| `vus` | Uncertain significance, Conflicting classifications |

La clasificación original de ClinVar viene en el campo `clasificacion_clinvar`.

### Identificador de variante

Cada variante se identifica por su **id de ClinVar** (VariationID), como string. Ejemplo: `"4027"` es `NM_000152.5(GAA):c.-32-13T>G`. El campo `nombre` es solo para mostrar.

## Endpoints

### 1. Genes de una patología

`POST /rpc/genes_por_patologia`

```json
{"p_patologia": "POMPE"}
```

Respuesta 200:

```json
["GAA"]
```

### 2. Genes de hallazgos secundarios

`GET /genes_hallazgos_secundarios?select=gen,condicion`

Devuelve los 84 genes de la lista ACMG SF v3.3. Respuesta 200:

```json
[{"gen": "BRCA1", "condicion": "Cáncer de mama y ovario hereditario"}, ...]
```

### 3. Variantes de un gen

`GET /variantes?gen=eq.GAA&select=clinvar_id,nombre,clasificacion&order=nombre&limit=50&offset=0`

Filtros opcionales:

| Filtro | Ejemplo | Para qué |
| --- | --- | --- |
| `nombre=ilike.*<texto>*` | `nombre=ilike.*32-13T*` | Buscar mientras se escribe |
| `clasificacion=eq.<valor>` | `clasificacion=eq.patogenica` | Solo una clasificación |

Con el header `Prefer: count=exact`, la respuesta trae el total en `Content-Range` (por ejemplo `0-49/3672`).

Respuesta 200:

```json
[{"clinvar_id": "4027", "nombre": "NM_000152.5(GAA):c.-32-13T>G", "clasificacion": "patogenica"}, ...]
```

**La paginación es obligatoria:** hay genes con miles de variantes y Supabase devuelve como máximo 1000 filas por request.

### 4. Confirmar diagnóstico

`POST /rpc/confirma_diagnostico`

```json
{"p_patologia": "POMPE", "p_variantes": ["4027"]}
```

Devuelve `true` si alguna de las variantes es patogénica en un gen de esa patología. Respuesta 200:

```json
true
```

### 5. Hallazgos secundarios

`POST /rpc/hallazgos_secundarios`

```json
{"p_variantes": ["<id>", "<id>"], "p_excluir_patologia": "POMPE"}
```

Devuelve las variantes que son patogénicas en genes ACMG. `p_excluir_patologia` es opcional: deja afuera los genes de esa patología, porque GLA (Fabry) y GAA (Pompe) también están en la lista ACMG. Respuesta 200:

```json
[{"clinvar_id": "...", "gen": "BRCA2", "nombre": "...", "clasificacion": "patogenica", "condicion": "Cáncer de mama y ovario hereditario"}]
```

## Errores

| Caso | HTTP | Respuesta |
| --- | --- | --- |
| Patología que no existe | 400 | `{"message": "Patología inexistente: XYZ", ...}` |
| Variante que no existe en `confirma_diagnostico` o `hallazgos_secundarios` | 400 | `{"message": "Variante inexistente: <id>", ...}` |
| Gen que no existe en `variantes` | 200 | `[]` |
| Lista de variantes vacía | 200 | `false` o `[]` |
| Falta la clave | 401 | Error de Supabase |
| Clave enviada como Bearer | 401 | Error de Supabase |
| Intento de escritura | 401 o 403 | Sin permiso |

## Versionado

Un cambio que rompe (renombrar un campo, cambiar un parámetro obligatorio) sale como una función nueva con sufijo `_v2`. La versión 1 sigue funcionando hasta que todos los grupos migren.

## Decisiones abiertas

Estas pueden cambiar el comportamiento de los endpoints 4 y 5 después de la clase del 27/10:

- Si "Likely pathogenic" cuenta como positivo. Hoy cuenta.
- Si en las patologías recesivas hacen falta dos variantes. Hoy alcanza con una.
- En HFE y TTN, ACMG solo reporta ciertos tipos de variante. Hoy se informa cualquier variante patogénica.

## Pruebas

En el repo hay un archivo `pruebas/apigen.http` con un caso por endpoint y los casos de error. Se corre con la extensión REST Client de VS Code o con el cliente HTTP de IntelliJ y PyCharm.