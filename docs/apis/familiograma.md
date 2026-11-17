# API de familiograma (borrador)

No hay contrato publicado. El adaptador provisorio envía `POST /generar` con JSON
`{"familiares": [...]}`; cada familiar incluye parentesco, nombre, síntomas y diagnósticos.
Espera `{"pdf_base64": "<PDF codificado en Base64>"}`.

Con `USE_MOCKS=1` responde desde
`sistema/tests/fixtures/apis/familiograma/generar.json`. La URL se configura en
`FAMILIOGRAMA_URL`. Si falla, el alta se conserva y el médico puede reintentar desde el detalle.
