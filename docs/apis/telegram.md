# Bot de mensajería (Telegram) – borrador provisorio

> **Borrador.** El formato del mensaje de muestra tomada **no está acordado** con los centros de extracción. Lo que sigue es el supuesto con el que se implementó E22 (issue #8). Se ajusta cuando se acuerde.

## Para qué sirve

El centro de extracción no opera el sistema (E22). Cuando toma la muestra de sangre, le manda un mensaje al bot del laboratorio central. El sistema recibe el mensaje por un webhook, registra la muestra y pasa el estudio de Turno sacado a Listo para retirar. Así el centro entra en la próxima orden del día de su provincia.

## Mensaje del centro (supuesto)

Un mensaje de texto, desde el chat registrado del centro (`centros_extraccion.telegram_chat_id`), que contiene el **código del estudio** que figura en la orden de extracción:

```
Muestra tomada EX-2026-00042
```

- El código tiene la forma `EX-AAAA-NNNNN`, con 5 dígitos o más. No distingue mayúsculas y puede estar en cualquier parte del texto. Si hay más de uno, vale el primero.
- Un mensaje por muestra.
- El resto del texto se guarda pero no se interpreta.

## Webhook

`POST /bot/telegram`, sin sesión y exento de CSRF.

| Aspecto | Comportamiento |
|---|---|
| Autenticación | Header `X-Telegram-Bot-Api-Secret-Token` igual a `TELEGRAM_WEBHOOK_SECRET`. Si falta, es incorrecto o el secreto no está configurado, la respuesta es **403** y no se guarda nada |
| Cuerpo | El [Update](https://core.telegram.org/bots/api#update) de Telegram. Se leen `update_id`, `message.chat.id` y `message.text` (también `edited_message` y `channel_post`) |
| Registro | Cada update se guarda en `mensajes_bot`. `telegram_update_id` es único: un update repetido no hace nada |
| Respuesta | Siempre **200** con el secreto correcto, aunque el mensaje tenga un error, para que Telegram no lo reintente |

### Validaciones

Si falla alguna, el error se guarda en `mensajes_bot.error` y el estudio no cambia. El administrativo los ve en `/bot/mensajes`.

| Caso | Error guardado | ¿Se responde al centro? |
|---|---|---|
| El chat no es de un centro registrado | "El chat no es de un centro de extracción registrado." | No |
| Mensaje sin texto | "El mensaje no trae texto." | Sí |
| Sin código de estudio | "El mensaje no trae el código del estudio…" | Sí |
| El código no existe | "No existe el estudio EX-…" | Sí |
| El estudio no está en Turno sacado | "El estudio EX-… está <estado>, no en Turno sacado." | Sí |
| El turno reservado es de otro centro | "El turno del estudio EX-… es de otro centro de extracción." | Sí |

Con un mensaje válido se crea la muestra (`turno_id`, `tomada_en`), el turno pasa a `asistido` y el estudio a Listo para retirar.

### Respuesta al centro

La respuesta va en el cuerpo del 200, como permite la Bot API para los webhooks. Así no hace falta el token del bot ni una llamada saliente:

```json
{"method": "sendMessage", "chat_id": "1000001", "text": "Muestra registrada: el estudio EX-2026-00042 está Listo para retirar."}
```

Telegram no informa si ese envío falló. Si hace falta confirmarlo, se agrega un cliente `src/integraciones/telegram.py` con `TELEGRAM_BOT_TOKEN`.

## Inasistencia (supuesto O7)

Los días hábiles a las 18:30 corre la tarea programada `inasistencias` (`flask tarea inasistencias` para correrla a mano). Toma los turnos que siguen reservados y empezaron antes del fin del día, con el estudio en Turno sacado:

- El turno pasa a `ausente`.
- El estudio vuelve a Habilitado para turno.
- El paciente recibe un aviso para reservar otro turno.

Un mensaje que llega después se guarda con el error "no está en Turno sacado".

## Configuración (deploy)

1. Crear el bot con @BotFather y guardar el token fuera del repositorio.
2. Generar el secreto: `python -c "import secrets; print(secrets.token_urlsafe(32))"` y ponerlo en `TELEGRAM_WEBHOOK_SECRET`.
3. Registrar el webhook con `setWebhook`, pasando `url=<URL_BASE>/bot/telegram` y `secret_token=<secreto>`.
4. Cargar el chat de cada centro en `centros_extraccion.telegram_chat_id`.

## Probar sin Telegram

```bash
poetry run flask demo turno_sacado
poetry run flask bot simular 1000001 "Muestra tomada EX-2026-00042"
```

Los chats de los centros de prueba de `flask seeds` van de `1000001` a `1000010`. `flask demo turno_sacado` reserva el turno en el primer centro activo (`1000001`). Los updates simulados usan `update_id` negativos, para no chocar con los de Telegram.

## Pendiente de acordar

- El formato del mensaje: si trae solo el código o también la hora de la toma, el DNI, etc.
- Si el centro puede avisar más de una muestra por mensaje.
- Quién da de alta el chat de un centro nuevo.
