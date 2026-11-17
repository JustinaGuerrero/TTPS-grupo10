# API de obras sociales (borrador)

**Provisorio:** el contrato del módulo 6 todavía no está publicado. Este borrador es la interfaz
que asume `sistema/src/integraciones/obras_sociales.py`; cuando llegue el contrato real, cambia
solo ese cliente.

Según el enunciado del módulo, la lista sale del Registro Nacional de Obras Sociales de la
Superintendencia de Servicios de Salud y cada obra social tiene su porcentaje de cobertura. El
módulo también tiene un alta de estudio y una web donde la obra social autoriza o rechaza: el
sistema da de alta cada pedido de cobertura y consulta la respuesta cada 30 minutos (G22). Si el
módulo no responde, el administrativo registra la respuesta a mano.

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `OBRAS_SOCIALES_URL` |
| Clave | `OBRAS_SOCIALES_KEY`, en el header `apikey` (opcional) |

## Listar obras sociales (E16)

`GET /obras_sociales`

```json
[
  {"codigo": "OS-100", "nombre": "Obra Social de Prueba Total", "porcentaje_cobertura": 100},
  {"codigo": "OS-070", "nombre": "Obra Social de Prueba Parcial", "porcentaje_cobertura": 70}
]
```

- `codigo`: identificador de la obra social en el módulo. El sistema lo guarda en
  `obras_sociales.codigo`.
- `porcentaje_cobertura`: de 0 a 100. El sistema lo copia en `coberturas.porcentaje` al elegirla;
  si después cambia en el módulo, el pedido ya hecho no cambia.

Con `USE_MOCKS=1` responde desde `sistema/tests/fixtures/apis/obras_sociales/listar.json`: tres
obras sociales inventadas, al 100 %, al 70 % y al 40 %.

## Dar de alta un estudio (E16, G22)

`POST /estudios`

```json
{"obra_social": "OS-070", "paciente": "Ana Pérez", "fecha": "2026-11-17"}
```

- `obra_social`: el `codigo` de la lista.
- `paciente`: nombre y apellido. Al módulo no van el DNI ni datos clínicos.
- `fecha`: la del pedido (o la de la demanda de reautorización, que da de alta el estudio otra vez).

Respuesta `201`:

```json
{"id": "MOD-OS-0001"}
```

El sistema guarda el `id` en `coberturas.id_estudio_modulo`. Si el módulo no responde, el pedido
queda sin `id` y la próxima consulta lo vuelve a dar de alta.

## Consultar la respuesta de la obra social (E17, G22)

`GET /estudios/<id>`

```json
{"id": "MOD-OS-0001", "estado": "rechazado", "motivo": "El plan no cubre estudios genéticos"}
```

- `estado`: `pendiente`, `autorizado` o `rechazado`.
- `motivo`: opcional; el sistema lo guarda en el historial del estudio cuando la obra social rechaza.

Con `autorizado` el sistema aplica la autorización (pago de la obra social, asiento y, con
cobertura parcial, la diferencia para el paciente); con `rechazado`, el rechazo. Con `pendiente`
no cambia nada.

Con `USE_MOCKS=1`, el alta responde `alta_estudio.json` (`MOD-OS-0001`) y la consulta,
`estado_estudio_<id>.json` o, si no existe, `estado_estudio.json` (`autorizado`).

