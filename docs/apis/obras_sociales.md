# API de obras sociales (módulo 6, grupo 9)

Contrato del módulo de obras sociales que desarrolla el grupo 9. La especificación completa está
en `<OBRAS_SOCIALES_URL>/openapi.json` (se puede abrir en editor.swagger.io). El cliente es
`sistema/src/integraciones/obras_sociales.py`.

El módulo tiene la lista de obras sociales de la Superintendencia de Servicios de Salud con su
porcentaje de cobertura, el alta de la solicitud de autorización de un estudio y la respuesta de
la obra social. El sistema da de alta cada pedido de cobertura y consulta la respuesta cada 30
minutos (G22). Si el módulo no responde, el administrativo registra la respuesta a mano.

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `OBRAS_SOCIALES_URL` = `https://bxsvmfesrtjrqubblgws.supabase.co/functions/v1/api` |
| Clave | `OBRAS_SOCIALES_KEY`, en el header `x-api-key`. Es la del grupo 10: va solo en el `.env` |

Sin la clave, el módulo responde `401`. Los errores tienen la forma
`{"error": {"codigo", "mensaje", "detalle"}}`.

## Listar obras sociales (E16)

`GET /obras-sociales?pagina=1&por_pagina=100` (`por_pagina` de 1 a 100; también acepta `buscar`
por nombre, sigla o código RNOS)

```json
{
  "datos": [
    {"id": "3f6c1d52-…", "rnos_codigo": "9-0010-0", "nombre": "Instituto de Obra Médico Asistencial", "sigla": "IOMA", "porcentaje_cobertura": 100}
  ],
  "pagina": 1, "por_pagina": 100, "total": 37, "total_paginas": 1
}
```

- `rnos_codigo`: el código del Registro Nacional de Obras Sociales. El sistema lo guarda en
  `obras_sociales.codigo`.
- `id`: el id de la obra social en el módulo; lo pide el alta de la solicitud. El sistema lo
  guarda en `obras_sociales.id_modulo`.
- `porcentaje_cobertura`: de 0 a 100. El sistema lo copia en `coberturas.porcentaje` al elegirla.

## Dar de alta la solicitud (E16, G22)

`POST /solicitudes`

```json
{"obra_social_id": "3f6c1d52-…", "paciente_nombre": "Ana Pérez", "fecha": "2026-11-17", "referencia_externa": "EX-2026-00042"}
```

- `paciente_nombre` y `fecha` (AAAA-MM-DD) son obligatorios. Al módulo no van el DNI ni datos
  clínicos.
- `referencia_externa`: el código del estudio.

Respuesta `201`: la solicitud en estado `pendiente`, con su `id` y las `urls_simulacion`. El
sistema guarda el `id` en `coberturas.id_estudio_modulo`. Si el módulo no responde, el pedido
queda sin `id` y la próxima consulta lo vuelve a dar de alta.

## Consultar la respuesta (E17, G22)

`GET /solicitudes/<id>`

```json
{
  "id": "b1f0c0aa-…", "estado": "autorizada", "porcentaje_cobertura": 70, "motivo_rechazo": null,
  "referencia_externa": "EX-2026-00042",
  "urls_simulacion": {"autorizar": "…/simulacion/<token>/autorizar", "rechazar": "…/simulacion/<token>/rechazar"}
}
```

| `estado` | Qué hace el sistema |
| --- | --- |
| `pendiente` | Nada: sigue esperando |
| `autorizada` | Autoriza con el `porcentaje_cobertura` que devuelve el módulo (puede no ser el de la lista): pago de la obra social, asiento y, con cobertura parcial, la diferencia para el paciente |
| `rechazada` | Rechaza, con el `motivo_rechazo` en el historial del estudio |
| `demanda_en_curso` | Nada: espera la respuesta a la demanda |

## Presentar la demanda (E18)

`POST /solicitudes/<id>/demanda`, `multipart/form-data` con el PDF de la resolución judicial en
el campo `archivo` (hasta 5 MB). Solo sobre una solicitud `rechazada`: la misma solicitud pasa a
`demanda_en_curso`. Si no está rechazada, el módulo responde `409`.

Si el módulo no responde al cargar la demanda, la tarea la vuelve a subir antes de leer la
respuesta, para no tomar el rechazo anterior como respuesta a la demanda.

## Simular la respuesta de la obra social

Las `urls_simulacion` hacen de la obra social y no llevan la clave:

- `POST <autorizar>` con `{"porcentaje": 70}` opcional (sin cuerpo, el de la lista).
- `POST <rechazar>` con `{"motivo": "…"}` obligatorio.

Desde el sistema: `flask obra-social simular EX-2026-00042 autorizar --porcentaje 70` (o
`rechazar --motivo "…"`), y después `flask tarea respuestas_obras_sociales` para que el sistema
tome la respuesta sin esperar la media hora.

## Mocks

Con `USE_MOCKS=1` el cliente lee `sistema/tests/fixtures/apis/obras_sociales/`: tres obras
sociales inventadas (al 100 %, al 70 % y al 40 %), el alta, la consulta (`autorizada` con el
porcentaje de la lista), la demanda y las dos simulaciones.
