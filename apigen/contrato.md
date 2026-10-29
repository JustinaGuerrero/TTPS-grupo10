# Contrato: Apigen v1

Módulo 5 del TP integrador de TTPS 2026, desarrollado por el grupo 10. Es la "API de bioinformática": dice qué genes estudiar para cada patología, cuáles son los genes de hallazgos secundarios, qué variantes conocidas tiene cada gen (de ClinVar) y si un conjunto de variantes confirma un diagnóstico o indica que la persona es portadora.

Todos los endpoints son de lectura, salvo `alta_patologia`, que permite que el gerente médico de cada grupo cargue patologías propias.

## Qué cambió respecto de la v0

| Cambio | Antes (v0) | Ahora (v1) |
| --- | --- | --- |
| Identificador de variante | Número de ClinVar (`"4027"`) | Nombre HGVS codificante (`"GAA:c.-32-13T>G"` o `"c.-32-13T>G"`) |
| "Probablemente patogénica" | Contaba como patogénica | No diagnostica: es una clasificación aparte |
| Genes recesivos en hallazgos secundarios | Alcanzaba una variante | Hacen falta dos |
| Genes | 88 | Todos los genes con variantes en ClinVar (unos 20.000), con búsqueda |
| Patologías | Solo las 6 base | Las 6 base más las que cargue cada grupo |
| `hallazgos_secundarios` | `p_excluir_patologia` (texto) | `p_excluir_patologias` (lista) |
| Diagnóstico de patologías recesivas | Alcanzaba una variante | Con una sola es **portador**: hacen falta las dos copias del gen |
| Resultado del diagnóstico | Solo `true` o `false` | También `positivo`, `portador` o `negativo` (endpoint nuevo) |

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1` |
| Clave | `sb_publishable_Ogyld01ST0Gu8zlPBjLmow_9FYtNamo` |
| Header | `apikey: sb_publishable_Ogyld01ST0Gu8zlPBjLmow_9FYtNamo` en cada pedido |

La clave va en el header `apikey`, no como `Authorization: Bearer`. Alcanza con cualquier cliente HTTP (`fetch`, `requests`, `axios`).

Recomendaciones: centralicen las llamadas en un solo archivo, usen un timeout de 5 segundos y armen un mock con los ejemplos de este contrato para trabajar sin red.

## URLs completas de los endpoints

Cada pedido va a la URL base seguida del endpoint. Estas son las URLs completas, listas para usar:

| # | Endpoint | Método | URL completa |
| --- | --- | --- | --- |
| 1 | Buscar genes | GET | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/gen?simbolo=ilike.GA*&select=simbolo&order=simbolo&limit=20` |
| 2 | Listar patologías | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/listar_patologias` |
| 3 | Genes de una patología | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/genes_por_patologia` |
| 4 | Genes de hallazgos secundarios | GET | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/genes_hallazgos_secundarios?select=gen,condicion,herencia` |
| 5 | Variantes de un gen | GET | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/variantes?gen=eq.GAA&select=id,hgvs_c,proteina,clasificacion&order=hgvs_c&limit=50&offset=0` |
| 6 | Confirmar diagnóstico | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/confirma_diagnostico` |
| 7 | Resultado del diagnóstico | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/resultado_diagnostico` |
| 8 | Hallazgos secundarios | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/hallazgos_secundarios` |
| 9 | Alta de patología del grupo | POST | `https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/alta_patologia` |

En los GET, lo que va después del `?` son filtros: cambien `GA*` o `GAA` por lo que busquen. Los POST llevan el cuerpo en JSON que se explica en cada endpoint.

## Valores fijos

### Patologías base

| Código | Patología | Gen | Herencia | Para confirmar |
| --- | --- | --- | --- | --- |
| `FABRY` | Enfermedad de Fabry | GLA | Ligada al X | Una variante patogénica |
| `POMPE` | Enfermedad de Pompe | GAA | Recesiva | Las dos copias del gen |
| `GAUCHER` | Enfermedad de Gaucher | GBA1 | Recesiva | Las dos copias del gen |
| `MPS1` | Mucopolisacaridosis tipo 1 | IDUA | Recesiva | Las dos copias del gen |
| `MPS2` | Mucopolisacaridosis tipo 2 | IDS | Ligada al X | Una variante patogénica |
| `ASMD` | Déficit de esfingomielinasa ácida | SMPD1 | Recesiva | Las dos copias del gen |

**Portador.** En una patología recesiva, si hay una sola variante patogénica en el gen, la persona es portadora: no está enferma, pero puede transmitirla a su descendencia. Para confirmar hacen falta las dos copias afectadas: dos variantes patogénicas distintas en el gen, o la misma repetida (homocigota).

### Clasificaciones

| Valor | Incluye de ClinVar | ¿Confirma diagnóstico? |
| --- | --- | --- |
| `patogenica` | Pathogenic, Pathogenic/Likely pathogenic | Sí |
| `probablemente_patogenica` | Likely pathogenic | No |
| `vus` | Uncertain significance, Conflicting classifications | No |
| `benigna` | Benign, Likely benign, Benign/Likely benign | No |

Si un estudio no tiene variantes patogénicas pero sí alguna `vus` o `probablemente_patogenica`, no hay diagnóstico. Según el PO, el sistema le pone al estudio una fecha de reevaluación a un año. Eso lo resuelve el sistema de cada grupo, no Apigen.

### Identificador de variante

Cada variante se identifica por su nombre HGVS codificante. Se aceptan estos formatos:

| Formato | Ejemplo | Dónde se puede usar |
| --- | --- | --- |
| Gen y HGVS | `GAA:c.-32-13T>G` | En todos lados (recomendado) |
| Solo HGVS | `c.-32-13T>G` | Solo en `confirma_diagnostico` y `resultado_diagnostico`: se busca en los genes de la patología |
| Transcripto y HGVS | `NM_000152.5:c.-32-13T>G` | En todos lados |
| Como lo escribe ClinVar | `NM_000152.5(GAA):c.-32-13T>G` | En todos lados |

El endpoint `variantes` devuelve el campo `id` con el formato recomendado, listo para mandar.

Si el paciente tiene la misma variante en las dos copias del gen (homocigota), se manda dos veces: `["GAA:c.-32-13T>G", "GAA:c.-32-13T>G"]`. Esto importa en las patologías recesivas y en los genes ACMG recesivos, donde una sola copia no alcanza.

Si un mismo nombre corresponde a dos variantes con clasificaciones distintas, la API responde error 400 "Variante ambigua". En ese caso, manden el transcripto: `NM_…:c.…`.

### Grupo

Las patologías que carga un grupo solo las ve ese grupo. Para usarlas, manden `p_grupo_id` con un texto fijo que identifique a su grupo, por ejemplo `"grupo3"`. Es opcional: sin él, solo existen las 6 base.

## Endpoints

### 1. Buscar genes

`GET https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/gen?simbolo=ilike.GA*&select=simbolo&order=simbolo&limit=20`

Para la búsqueda mientras el médico escribe. `ilike` no distingue mayúsculas y `*` es el comodín. Respuesta 200:

```json
[{"simbolo": "GAA"}, {"simbolo": "GAB1"}, {"simbolo": "GABBR1"}]
```

### 2. Listar patologías

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/listar_patologias`

```json
{"p_grupo_id": "grupo3"}
```

Respuesta 200: las 6 base y las del grupo.

```json
[{"codigo": "ASMD", "nombre": "Déficit de esfingomielinasa ácida (ASMD)", "herencia": "autosomica_recesiva", "genes": ["SMPD1"], "de_grupo": false}, ...]
```

### 3. Genes de una patología

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/genes_por_patologia`

```json
{"p_patologia": "POMPE"}
```

Respuesta 200:

```json
["GAA"]
```

Para una patología del grupo, agreguen `"p_grupo_id"`.

### 4. Genes de hallazgos secundarios

`GET https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/genes_hallazgos_secundarios?select=gen,condicion,herencia`

Los 84 genes de la lista ACMG SF v3.3. `herencia` es `dominante`, `recesiva` o `ligada_x`. Respuesta 200:

```json
[{"gen": "BRCA1", "condicion": "Cáncer de mama y ovario hereditario", "herencia": "dominante"}, ...]
```

### 5. Variantes de un gen

`GET https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/variantes?gen=eq.GAA&select=id,hgvs_c,proteina,clasificacion&order=hgvs_c&limit=50&offset=0`

| Filtro opcional | Ejemplo | Para qué |
| --- | --- | --- |
| `hgvs_c=ilike.*<texto>*` | `hgvs_c=ilike.*32-13*` | Buscar mientras se escribe |
| `clasificacion=eq.<valor>` | `clasificacion=eq.patogenica` | Solo una clasificación |

Con el header `Prefer: count=exact`, el total viene en `Content-Range` (por ejemplo `0-49/3672`). Respuesta 200:

```json
[{"id": "GAA:c.-32-13T>G", "hgvs_c": "c.-32-13T>G", "proteina": null, "clasificacion": "patogenica"}, ...]
```

Otros campos disponibles: `gen`, `transcripto`, `clasificacion_clinvar` (el valor original) y `clinvar_id`.

**Qué variantes hay:** de los genes de Apigen (las 6 patologías base, los 84 ACMG y los de las patologías que cargó cada grupo) están todas las clasificaciones. Del resto del genoma, solo las `patogenica` y `probablemente_patogenica`, porque con todas no entra en los 500 MB del plan gratuito. Si un grupo da de alta una patología con genes nuevos, volvemos a cargar y esos genes pasan a tener todas sus variantes.

**Paginen siempre:** hay genes con miles de variantes y Supabase devuelve como máximo 1000 filas por pedido. Filtren siempre por `gen`.

### 6. Confirmar diagnóstico

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/confirma_diagnostico`

```json
{"p_patologia": "POMPE", "p_variantes": ["c.-32-13T>G", "c.525del"]}
```

Devuelve `true` si las variantes `patogenica` en un gen de esa patología alcanzan según su herencia:

- **Recesiva** (Pompe, Gaucher, MPS 1, ASMD): hacen falta las dos copias del gen. Dos variantes patogénicas distintas en el mismo gen, o la misma repetida (homocigota). Con una sola es **portador**, y devuelve `false`.
- **Ligada al X** (Fabry, MPS 2) o **dominante**: alcanza con una.

Respuesta 200:

```json
true
```

Si el diagnóstico presuntivo tiene varias patologías, llamen una vez por cada una. Para saber si un `false` es negativo o portador, usen el endpoint 7.

### 7. Resultado del diagnóstico

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/resultado_diagnostico`

```json
{"p_patologia": "POMPE", "p_variantes": ["GAA:c.-32-13T>G"]}
```

Igual que el 6, con las mismas reglas, pero devuelve uno de estos tres textos:

| Resultado | Cuándo |
| --- | --- |
| `positivo` | Se confirma el diagnóstico (es cuando el 6 da `true`) |
| `portador` | Patología recesiva con una sola variante patogénica en el gen. La persona no está enferma, pero puede transmitirla a su descendencia |
| `negativo` | Ninguna variante patogénica en los genes de la patología |

Respuesta 200:

```json
"portador"
```

### 8. Hallazgos secundarios

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/hallazgos_secundarios`

```json
{"p_variantes": ["BRCA2:c.5946del", "GAA:c.-32-13T>G"], "p_excluir_patologias": ["POMPE"]}
```

Devuelve las variantes `patogenica` en genes ACMG, con estas reglas:

- No se informan los genes de las patologías sospechadas: manden siempre `p_excluir_patologias`. Una variante en el gen sospechado es diagnóstico, no hallazgo.
- En los genes `recesiva`, solo se informa si hay dos variantes: distintas, o la misma repetida.
- Las variantes tienen que llevar el gen adelante.

Respuesta 200:

```json
[{"variante": "BRCA2:c.5946del", "gen": "BRCA2", "hgvs_c": "c.5946del", "clasificacion": "patogenica",
  "condicion": "Cáncer de mama y ovario hereditario", "herencia": "dominante", "copias": 1}]
```

### 9. Alta de una patología del grupo

`POST https://edmrjmfjklwgazzztjcl.supabase.co/rest/v1/rpc/alta_patologia`

```json
{"p_grupo_id": "grupo3", "p_codigo": "MPS3A", "p_nombre": "Mucopolisacaridosis tipo 3A", "p_genes": ["NAGLU"],
 "p_herencia": "autosomica_recesiva"}
```

La usa el gerente médico. Si el código ya existe en el grupo, actualiza el nombre, los genes y la herencia. Reglas:
- El código va en mayúsculas, números o `_`, de 2 a 30 caracteres.
- No se puede usar el código de una patología base.
- Los genes tienen que existir: búsquenlos con el endpoint 1.
- `p_herencia` es opcional: `autosomica_recesiva` (si no la mandan), `autosomica_dominante` o `ligada_al_x`. Decide cuántas variantes hacen falta para confirmar.

Respuesta 200:

```json
[{"codigo": "MPS3A", "nombre": "Mucopolisacaridosis tipo 3A", "herencia": "autosomica_recesiva", "genes": ["NAGLU"]}]
```

## Errores

| Caso | HTTP | `message` |
| --- | --- | --- |
| Patología inexistente | 400 | `Patología inexistente: XYZ` |
| Variante inexistente | 400 | `Variante inexistente: GAA:c.99999A>G` |
| Formato de variante inválido | 400 | `Formato de variante inválido: 4027 (usá GEN:c.… o c.…)` |
| Variante sin gen en hallazgos secundarios | 400 | `Indicá el gen de la variante, por ejemplo GEN:c.…` |
| Variante ambigua | 400 | `Variante ambigua: … Indicá el transcripto…` |
| Código de patología inválido o de una patología base | 400 | `Código inválido: …` / `El código … es de una patología base…` |
| Gen inexistente en el alta | 400 | `Gen inexistente: …` |
| Herencia inválida en el alta | 400 | `Herencia inválida: …` |
| Gen sin variantes en `variantes` | 200 | `[]` |
| Lista de variantes vacía | 200 | `false`, `"negativo"` o `[]` |
| Falta la clave o la clave es inválida | 401 | Error de Supabase |
| Intento de escribir directo en una tabla | 401 o 403 | Sin permiso |

Los errores 400 tienen siempre esta forma, y el texto para mostrar está en `message`:

```json
{"code": "P0001", "details": null, "hint": null, "message": "Patología inexistente: XYZ"}
```

## Simplificaciones conocidas

- En HFE, ACMG solo informa los homocigotos de `c.845G>A`, y en TTN solo las variantes truncantes. Apigen aplica la regla general de cada gen.
- En los genes `ligada_x` (GLA, OTC y ABCD1) alcanza con una variante. En mujeres, ACMG pide dos, pero Apigen no conoce el sexo del paciente.
- Lo mismo en Fabry y MPS 2: una variante confirma, sin importar el sexo.
- Del resto del genoma (genes que no son de ninguna patología ni ACMG) no se cargan las VUS ni las benignas. Una VUS de esos genes da `Variante inexistente`.
- Con dos variantes distintas en un gen recesivo, Apigen asume que están en copias distintas del gen. Confirmarlo requiere estudiar a los padres, y eso queda fuera de Apigen.

## Versionado

Un cambio que rompe (renombrar un campo, cambiar un parámetro obligatorio) sale como una función nueva con sufijo `_v2`. Esta versión sigue funcionando hasta que todos los grupos migren.

## Pruebas

En el repo están `pruebas/apigen.http` (REST Client de VS Code o IntelliJ) y `pruebas/apigen.postman_collection.json` (Postman), con un caso por endpoint y los casos de error.
