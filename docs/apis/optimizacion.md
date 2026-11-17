# Módulo de optimización de recorridos (módulo 9)

Contrato del módulo de optimización de recorridos, según su presentación y su documentación en
<https://optimizacionapi.vercel.app/>. El cliente es `sistema/src/integraciones/optimizacion.py`.

El módulo recibe las coordenadas de un recorrido y devuelve en qué orden visitarlas, buscando el
camino más corto por las calles (OSRM, con datos de OpenStreetMap). El sistema lo usa cada mañana
hábil para armar la orden del día de cada provincia (E23). El orden que devuelve es fijo: el
transportista no lo puede cambiar.

## Conexión

| Dato | Valor |
| --- | --- |
| URL base | `OPTIMIZACION_URL` = `https://optimizacionapi.vercel.app/api` |
| Clave | No pide. Si algún día la pide, va en `OPTIMIZACION_KEY` (header `apikey`) |

## Ordenar un recorrido (E23)

`POST /optimizacion`

```json
{
  "coordenadas": [
    {"lat": -34.9214, "lon": -57.9545},
    {"lat": -34.9212, "lon": -57.9545},
    {"lat": -34.7242, "lon": -58.2526},
    {"lat": -34.9214, "lon": -57.9545}
  ]
}
```

- La primera coordenada es el punto de partida y la última, el destino. El módulo **solo ordena
  las del medio**.
- El sistema manda como partida y como destino el laboratorio central (el transportista sale de
  ahí y vuelve con las muestras, E26) y en el medio la latitud y la longitud de cada centro con
  muestras listas. El enunciado no da la dirección del laboratorio central: se asume La Plata
  (`LABORATORIO_CENTRAL` en `core/logistica/servicios.py`).

Respuesta `200`: las mismas coordenadas, con las del medio en el orden del recorrido.

```json
{
  "coordenadas": [
    {"lat": -34.9214, "lon": -57.9545},
    {"lat": -34.7242, "lon": -58.2526},
    {"lat": -34.9212, "lon": -57.9545},
    {"lat": -34.9214, "lon": -57.9545}
  ]
}
```

- El módulo no devuelve ids: el sistema reconoce cada centro por sus coordenadas (con los 6
  decimales que guarda la base). Si dos centros están en el mismo lugar, da lo mismo cuál va
  primero.
- Si falta o sobra algún centro, si aparece una coordenada que no se mandó o si cambiaron la
  partida o el destino, el sistema lo toma como una respuesta inválida y no genera la orden.

| Código | Cuándo |
| --- | --- |
| `200` | El recorrido ordenado |
| `400` | JSON mal formado o error del motor OSRM |
| `422` | Faltan campos o hay menos de 2 coordenadas (`{"errores_validacion": {...}}`) |
| `500` | No se pudo conectar con el servidor de mapas |

Si el módulo no responde o responde con un error, el sistema no genera la orden del día de esa
provincia y avisa a los administrativos, que la regeneran a mano desde `/ordenes-del-dia` (G5).

## Mocks

Con `USE_MOCKS=1` el sistema no llama al módulo: ordena los centros por cercanía (en línea
recta), empezando por el más cercano al laboratorio central y siguiendo siempre por el más
cercano.
