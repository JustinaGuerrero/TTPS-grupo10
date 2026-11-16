# Módulo de cupones (borrador provisorio)

**Estado:** el módulo de cupones todavía no tiene contrato. Este borrador lo escribió el equipo con lo
que necesita E37, E15 y la observación O15 (el descuento es un porcentaje). Se ajusta cuando llegue
el contrato real. El cliente es `src/integraciones/cupones.py`; sus respuestas simuladas están en
`tests/fixtures/apis/cupones/`.

**Conexión (supuesta):** `CUPONES_URL` y `CUPONES_KEY` (header `apikey`). Timeout de 5 s.

## 1. Generar cupones (E37)

`POST /cupones` con `{"descuento": 20, "cantidad": 3}` (descuento de 1 a 100, en porcentaje).

Responde una lista con un elemento por cupón:

```json
[{"codigo": "73920001", "pdf_base64": "<PDF con el código QR y el código numérico>"}]
```

## 2. Consultar un cupón (E15)

`GET /cupones/<codigo>` responde `{"codigo": "73920001", "estado": "vigente", "descuento_porcentaje": 20}`.
`estado` es `vigente` o `utilizado`; el módulo es el que manda. Un código que no existe responde 404.

## 3. Vencer un cupón (E15.6)

`POST /cupones/<codigo>/vencer` informa el uso. Responde 200 y el cupón pasa a `utilizado`.

## Respuestas simuladas (USE_MOCKS=1)

| Función | Archivo | Detalle |
| --- | --- | --- |
| `generar` | `generar.json` | 10 cupones `CUP73920001` a `CUP73920010`, con PDF; no se pueden generar más de 10 ni repetir códigos |
| `consultar(codigo)` | `consultar_<codigo>.json`, si no `consultar.json` | `VENCIDO01` está utilizado; el resto, vigente |
| `vencer(codigo)` | `vencer_<codigo>.json`, si no `vencer.json` | `CAIDO001` responde 503 |
