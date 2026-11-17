# API de obras sociales (borrador)

**Provisorio:** el contrato del módulo 6 todavía no está publicado. Este borrador es la interfaz
que asume `sistema/src/integraciones/obras_sociales.py`; cuando llegue el contrato real, cambia
solo ese cliente.

Según el enunciado del módulo, la lista sale del Registro Nacional de Obras Sociales de la
Superintendencia de Servicios de Salud y cada obra social tiene su porcentaje de cobertura. El
módulo también tiene un alta de estudio y una web para que la obra social autorice o rechace:
por ahora no se usan, porque en E17 el administrativo registra la respuesta que le dio la obra
social por teléfono.

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
