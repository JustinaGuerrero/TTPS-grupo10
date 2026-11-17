# API de transcripción (borrador)

No hay contrato publicado. El adaptador provisorio envía `POST /transcribir` con JSON
`{"audio_base64": "<audio codificado en Base64>"}` y espera `{"texto": "..."}`.

Con `USE_MOCKS=1` responde desde
`sistema/tests/fixtures/apis/transcripcion/transcribir.json`. La URL se configura en
`TRANSCRIPCION_URL`. Si falla, el médico puede completar o corregir el texto manualmente.
