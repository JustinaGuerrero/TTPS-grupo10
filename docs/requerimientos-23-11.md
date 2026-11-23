# Requerimientos del 23/11

Tres pedidos nuevos del profesor. Los hace Integrante 4 (milestone Entrega, 8/12). Los escenarios
están en `docs/escenarios.md` (E46 a E49) y las issues en `docs/issues-por-escenario.md`.

| Pedido | Escenarios | Rama |
|---|---|---|
| 1 y 2. Pago en cuotas con una billetera virtual real (Mercado Pago, ambiente de prueba); el administrativo ve, por ejemplo, «6 cuotas: 3 pagas, 2 vencidas, 1 pendiente» | E46 Pagar en cuotas con Mercado Pago, E47 Consultar cuotas | `<número de E46>-cuotas-mercado-pago` |
| 3. Historia clínica del paciente: el paciente da acceso a otros médicos, elegidos de una lista, y ve quiénes la pueden ver | E48 Dar acceso a la historia clínica, E49 Consultar historia clínica | `<número de E48>-historia-clinica` |
| Opcional: factura electrónica con ARCA (homologación) | — | Fuera de alcance (ver abajo) |

## Supuestos

| # | Supuesto | Escenario |
|---|---|---|
| G24 | El plan de cuotas es del laboratorio, no de la tarjeta: 1, 3 o 6 cuotas mensuales iguales en USD (la última ajusta los centavos), sin interés ni recargo por mora. La primera vence el día en que se arma el plan y las demás el mismo día de los meses siguientes (si el mes no tiene ese día, el último del mes). Una cuota está **vencida** si no está pagada y su vencimiento ya pasó; si no, **pendiente**. No se guarda: se calcula | E46, E47 |
| G25 | El estudio pasa a Habilitado para turno cuando se paga la primera cuota: el laboratorio financia el resto. Las cuotas impagas son deuda del paciente (E41.4). Un plan por estudio | E46 |
| G26 | Mercado Pago (Checkout Pro) en su ambiente de prueba, con las credenciales de un usuario vendedor de prueba. Cada cuota es un pago aparte, en pesos: el importe en USD por la cotización del día en que se arma el plan (`MERCADOPAGO_COTIZACION_USD`), que queda fija. Cada pago se hace en una sola cuota de tarjeta: las cuotas las maneja el plan | E46 |
| G27 | El sistema confirma cada pago consultándolo a Mercado Pago: al volver del checkout y con una tarea cada 30 minutos. No usa webhook, porque en desarrollo no hay una URL pública. Una cuota queda pagada solo si el pago está aprobado, es de esa cuota y es por su importe | E46 |
| G28 | El cupón se aplica al total al armar el plan (no a la diferencia de una cobertura parcial, G6) y se vence en el módulo de cupones cuando se paga la primera cuota | E46 |
| G29 | La historia clínica la ven, solo para leer, el médico tratante del paciente y los médicos tratantes a los que el paciente les dio acceso. El paciente los elige de la lista de médicos tratantes activos, varios a la vez, y no puede quitar un acceso. Cada acceso queda en el registro de cambios del paciente (E43) | E48, E49 |

## E46 y E47 · Cuotas con Mercado Pago

**Migración:** tablas `planes_de_pago` (estudio, cantidad de cuotas, total en USD, cupón y descuento,
cotización) y `cuotas` (plan, número, importe en USD y en pesos, vencimiento, pago, preferencia y
pago de Mercado Pago). `pagos` deja de tener un solo pago particular por estudio: cada cuota pagada
es un pago (sigue habiendo uno solo de obra social).

**Core:** `core/cuotas`: `armar_plan(estudio, paciente, cantidad, cupon)`, `iniciar_pago(cuota)` (crea
la preferencia de Mercado Pago), `confirmar_pago(cuota, id_de_pago)`, `consultar_pagos()` (la tarea),
`estado(cuota)` (pagada, vencida o pendiente) y `resumen(plan)`.

**Integración:** `integraciones/mercadopago.py` con `crear_preferencia(...)`, `buscar_pago(id)` y
`pagos_de(referencia)`. Con `USE_MOCKS=1`, el checkout es una página del sistema que aprueba o
rechaza el pago, para probar sin Mercado Pago.

**Pantallas:** el paciente elige la cantidad de cuotas en su presupuesto y ve su plan con un botón
«Pagar con Mercado Pago» por cuota. El administrativo tiene «Cuotas»: la lista de planes con
pagadas, vencidas, pendientes y adeudado (filtro «con vencidas») y el detalle de cada plan.

**Demo:** `flask cuotas demo` crea un paciente con un plan de 6 cuotas: 3 pagas, 2 vencidas y 1
pendiente.

**Configuración** (`.env`): `MERCADOPAGO_ACCESS_TOKEN` (de prueba, nunca a Git) y
`MERCADOPAGO_COTIZACION_USD`.

**Tests mínimos:** plan de 1, 3 y 6 cuotas con sus importes y vencimientos (fin de mes); cupón;
diferencia de cobertura; primera cuota pagada → Habilitado para turno y aviso; pago rechazado,
de otra cuota o por otro importe → no se marca; pagar dos veces la misma cuota; la tarea encuentra
un pago aprobado; estados pagada, vencida y pendiente; lista y filtro del administrativo; permisos.

## E48 y E49 · Historia clínica

**Migración:** tabla `accesos_historia_clinica` (paciente, médico, fecha), un acceso por paciente y
médico.

**Core:** `core/historia_clinica`: `medicos_disponibles(paciente, busqueda)`, `dar_acceso(paciente,
medicos, usuario)`, `medicos_habilitados(paciente)`, `puede_ver(usuario, paciente)`,
`pacientes_visibles(medico)` e `historia_de(paciente)`.

**Pantallas:** el paciente tiene «Mi historia clínica»: quiénes la pueden ver y la lista de médicos
para dar acceso. El médico tratante tiene «Historias clínicas»: sus pacientes y los que le dieron
acceso, y la historia clínica de cada uno (datos, resumen, síntomas, diagnóstico presuntivo,
familiares, familiograma, estudio, análisis y resultados) con la lista de médicos habilitados.

**Tests mínimos:** dar acceso a uno y a varios médicos; no repetir un acceso; no dar acceso al propio
médico tratante ni a alguien que no es médico tratante; registro de cambios y aviso al médico; el
médico habilitado ve la historia clínica y descarga el familiograma y el resultado; un médico sin
acceso → 404; el paciente no ve historias clínicas ajenas; otros roles → 403.

## Factura con ARCA (opcional, fuera de alcance)

ARCA tiene un ambiente de homologación para la factura electrónica (WSAA y WSFEv1 en
`wsaahomo.afip.gov.ar` y `wswhomo.afip.gov.ar`), con comprobantes sin validez fiscal. Para usarlo hace
falta un certificado de homologación que se genera en el WSASS con la clave fiscal de una persona
física. Como el grupo no lo va a tramitar, queda fuera de alcance.

## Consultas para el ayudante

- G24 y G25: ¿el estudio se habilita con la primera cuota o recién con todas pagas? ¿Hay recargo por
  cuota vencida?
- G26: Mercado Pago cobra en pesos: ¿alcanza con una cotización fija en la configuración?
- G29: ¿el paciente tiene que poder quitar un acceso? (el pedido dice que no hace falta)
