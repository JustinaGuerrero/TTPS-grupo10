# API de cupones (Exoma Care)

Resumen de la «Guía de integración API de cupones v2» y de su Swagger público
(https://juanmasisti.github.io/exoma-care-cupones-docs/). El módulo es compartido por todos los
grupos. El cliente es `src/integraciones/cupones.py`; las respuestas simuladas, `tests/fixtures/apis/cupones/`.

**Conexión:** URL base `https://vekuhonbpqtzakqbcoph.supabase.co/functions/v1/cupones-api` (`CUPONES_URL`).
La clave del grupo va en el header `X-API-Key` (`CUPONES_KEY`, solo en `.env`, nunca en el repositorio).
La clave identifica al grupo: no se envía `p_grupo_id` ni `Authorization: Bearer`. JSON en los POST, cuerpo
de hasta 16 KiB y timeout de 5 s.

**Ids:** son texto y el módulo no los verifica. El sistema usa `G-<id de usuario>`, `M-<id de médico>`
(su `usuario_id`) y `P-<id de paciente>`.

**Recorrido del cupón:** `disponible` → `medico` → `paciente` → `usado`. Asignar al paciente no lo consume.
Vence solo a los 30 días de generado.

## Operaciones

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| `POST /generar_cupones_gerencia` | `p_gerente_id`, `p_cantidad` (1 a 1000), `p_porcentaje_descuento` (mayor a 0) | `[{"codigo_cupon", "porcentaje"}]`. No trae PDF: lo arma el sistema |
| `POST /asignar_cupon_a_medico` | `p_gerente_id`, `p_medico_id`, `p_codigo` | `true` |
| `POST /asignar_cupon_a_paciente` | `p_medico_id`, `p_paciente_id`, `p_codigo` | `true` |
| `POST /canjear_cupon` | `p_paciente_id`, `p_codigo` | `true`. Valida grupo, paciente, estado y vencimiento; no cobra |
| `GET /cupones` | `?estado=&medico_id=&gerente_id=&limit=&offset=` (`limit` hasta 100) | `{"items": [...], "total", "limit", "offset"}` |

Cada ítem: `id`, `codigo`, `estado`, `gerente_id`, `medico_id`, `paciente_id`, `porcentaje_descuento`,
`fecha_vencimiento` (fecha), `fecha_uso`. No hay consulta por código: el sistema recorre el listado.

## Errores (JSON `code` y `message`)

- 400: datos inválidos, cupón vencido o estado no habilitado. 401: clave ausente o inválida.
- 403: el grupo ya tiene otro gerente (solo se puede generar con un gerente por grupo).
- 404: código inexistente o que no corresponde al grupo o al actor.
- 409: cupón ya usado, o paciente con un cupón previo en el grupo (aunque esté usado).
- 405, 413, 415 y 503 (error interno). **Las escrituras no se reintentan** ante un timeout: se consulta el estado primero.

## Respuestas simuladas (USE_MOCKS=1)

| Función | Archivo | Detalle |
| --- | --- | --- |
| `generar` | `generar.json` | 10 cupones `CUP73920001` a `CUP73920010` al 20 %; no se pueden generar más de 10 ni repetir códigos |
| `asignar_a_medico` | `asignar_a_medico_<codigo>.json`, si no `asignar_a_medico.json` | `true` |
| `asignar_a_paciente` | `asignar_a_paciente_<codigo>.json`, si no `asignar_a_paciente.json` | `YACANJE1` responde 409 |
| `consultar` | `cupones_<codigo>.json`, si no `cupones.json` | listado con los códigos de prueba; `VENCIDO01` está usado, `EXPIRADO1` venció y `SINPACIE1` no está asignado |
| `canjear` | `canjear_<codigo>.json`, si no `canjear.json` | `CAIDO001` responde 503 |
