# Módulo de optimización de recorridos (borrador)

**Provisorio:** el contrato del módulo 9 todavía no está publicado. Este borrador es la interfaz
que asume `sistema/src/integraciones/optimizacion.py`; cuando llegue el contrato real, cambia
solo ese cliente.

Según el enunciado, el módulo recibe las direcciones que tiene que visitar un transportista y
devuelve en qué orden hacer el recorrido. El sistema lo usa cada mañana hábil para armar la
orden del día de cada provincia (E23). El orden que devuelve es fijo: el transportista no lo
puede cambiar.

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `OPTIMIZACION_URL` |
| Clave | `OPTIMIZACION_KEY`, en el header `apikey` (opcional) |

## Ordenar un recorrido (E23)

`POST /recorridos`

```json
{
  "puntos": [
    {"id": 1, "direccion": "Calle 7 1234, La Plata, Buenos Aires", "latitud": -34.9212, "longitud": -57.9545},
    {"id": 2, "direccion": "Av. Calchaquí 2500, Quilmes, Buenos Aires", "latitud": -34.7242, "longitud": -58.2526}
  ]
}
```

- `id`: el del centro de extracción en el sistema. El módulo lo devuelve tal cual.
- `direccion`, `latitud` y `longitud`: el módulo puede usar la dirección, las coordenadas o las
  dos.

Respuesta `200`:

```json
{"orden": [2, 1]}
```

- `orden`: los mismos `id` que se mandaron, cada uno una vez, en el orden del recorrido. Si
  falta o sobra alguno, el sistema lo toma como una respuesta inválida y no genera la orden.

Si el módulo no responde o responde con un error, el sistema no genera la orden del día de esa
provincia y avisa a los administrativos, que la regeneran a mano (G5).

Con `USE_MOCKS=1` el sistema no llama al módulo: ordena los centros por cercanía, empezando por
el de menor id y siguiendo siempre por el más cercano.
