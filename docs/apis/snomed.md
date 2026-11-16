# Módulo SNOMED (borrador provisorio)

> **Provisorio:** todavía no hay contrato del módulo SNOMED. Este documento
> describe la interfaz que asume `src/integraciones/snomed.py`. Cuando llegue
> el contrato real, cambia solo el cliente.

## Interfaz que asume el sistema

`buscar_terminos(texto, tipo)`

- `texto`: lo que escribió el usuario. El buscador consulta desde 3 letras.
- `tipo`: `sintoma` o `especialidad`.
- Devuelve una lista de términos. Cada uno trae `codigo` (código SNOMED) y `termino` (descripción):

```json
[
  {"codigo": "386661006", "termino": "Fiebre"},
  {"codigo": "49727002", "termino": "Tos"}
]
```

## Quién la usa

- `GET /snomed/terminos?q=&tipo=sintoma` (médico tratante y gerente médico), que alimenta el macro `snomed/_buscador.html`.
- Los issues #9 (especialidades) y #10 (síntomas del paciente y de los familiares).

## Errores

Si el módulo no responde, el cliente levanta `IntegracionError` con un mensaje legible y el endpoint devuelve un JSON de error sin romper la pantalla.

## Mocks

`tests/fixtures/apis/snomed/` (síntomas y especialidades), activos con `USE_MOCKS=1`.