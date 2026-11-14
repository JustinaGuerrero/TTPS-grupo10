# Guía de issues – Sistema de exoma clínico

Nov 13, 2026 · TTPS 2026, grupo 10

Es la "Guía completa" de Proyecto de Software adaptada a trabajar con agentes: qué issues hay, quién hace cada uno, en qué orden y con qué prompt arranca el agente. Las fuentes son [escenarios.md](escenarios.md) (E01–E41), [lel.md](lel.md), [modelo-datos.md](modelo-datos.md), [decisiones.md](decisiones.md), [guia-agentes.md](guia-agentes.md), `CLAUDE.md`, `apigen/contrato.md` y el estado del repo al 13/11.

**Cómo leerla.** Las secciones 1 y 2 se leen una vez. La 3 y la 4 son el tablero: qué issue sigue y de quién es. La 5 es lo que cada uno abre antes de empezar su issue: criterios, capas, tests y el prompt para el agente. Las 6 a 8 sirven para cada control y para el coloquio. El script de la sección 9 carga todo en GitHub.

# 1. Diagnóstico y supuestos

## Qué está hecho

Rama `base`, último commit `0200281`. Corresponde a las sesiones 2 a 5 de [guia-agentes.md](guia-agentes.md).

| Pieza | Estado | Dónde |
|---|---|---|
| Estructura MVC, Poetry, `create_app()`, configuración por entorno, páginas 403/404/500 y de CSRF | Hecho (sesión 2) | `sistema/src/web/__init__.py`, `config.py`, `errores.py` |
| Flask-SQLAlchemy-Lite, migración inicial (`roles`, `usuarios`, RLS sin políticas), base de test local que aplica las migraciones y revierte cada test | Hecho (sesión 3) | `src/core/database.py`, `supabase/migrations/20261112041337_inicial.sql`, `tests/conftest.py` |
| Login y logout con Flask-Session y scrypt, `login_required` y `rol_requerido`, CSRF, `Cache-Control: no-store`, layout con menú por rol, `flask seeds` con un usuario por rol | Hecho (sesión 4) | `src/web/helpers/` (`auth.py`, `csrf.py`, `menu.py`), `controllers/autenticacion.py`, `templates/layout.html`, `src/core/seeds.py` |
| Sesión 5: modelos de pacientes y estudios, enum de 16 estados con sus 21 transiciones, `crear_estudio()` (código, análisis inicial y primera fila del historial), `cambiar_estado()` y las fixtures `crear_paciente` y `crear_estudio(estado=...)` | Hecho (commit `0200281`) | `src/core/estudios/`, `src/core/pacientes/`, migración `20261114004133_estudios.sql`, `tests/conftest.py` |
| Tests de app, login, base de datos, CSRF, seeds, estados, estudios y pacientes | Hecho | `sistema/tests/` |

## Qué falta

| Pieza | Estado al 13/11 | Issue |
|---|---|---|
| Sesión 6: `notificar()`, "Mis avisos", cliente base de APIs y cliente de Apigen | No empezada (`src/integraciones/` está vacía) | #3 |
| Sesión 7: módulo de referencia E03 y cierre de la base | No empezada (no hay controlador ni vistas de usuarios) | #3 |
| GitHub Action de tests | Falta: `.github/workflows/` solo tiene `mantener-activo.yml` | #3 |
| Rama `develop` | Falta: hay `main`, `base` y `chore/actualizacion-apigen` | #3 |
| Contratos de APIs en `docs/apis/` | La carpeta está vacía. Solo existe el contrato de Apigen, en `apigen/contrato.md` | Ver abajo |

El pedido daba la base como hecha. Como faltan las sesiones 6 y 7, la base se cargó como **dos issues de Integrante 1**: #2 (sesiones 2 a 4, hecho) y #3 (sesiones 5 a 7: la 5 ya está, faltan la 6 y la 7; bloquea a todos). Los dos cuentan en su carga.

### Lo que la base (#3) tiene que dejar para que nadie se bloquee

Además de lo que piden las sesiones 5 a 7 de la guía de agentes, la base deja estas piezas. Sin ellas, dos issues en paralelo terminarían escribiendo lo mismo.

1. **Ningún otro issue modifica `core/estudios/estados.py` ni `core/estudios/servicios.py`.** La tabla ya tiene las 21 transiciones de los 16 estados del LEL; `crear_estudio()` registra el alta y `cambiar_estado(estudio, nuevo_estado, usuario, motivo)` el resto. Si un issue cree que le falta una transición, es una consulta al grupo, no un cambio.
2. `crear_usuario()` acepta `telefono`, y hay una función `listar_activos_por_rol(rol)`, que usan #9 (E02 ep. 4), #11, #13, #15, #17 y #21 para avisar a todos los usuarios de un rol.
3. Las tablas de E03: `provincias` (24 jurisdicciones como datos fijos) y `transportistas`.
4. `src/integraciones/storage.py`: subir y bajar archivos de un bucket privado de Supabase Storage, con mock en disco (`instance/storage/`). La usan #5, #10, #12, #14, #15, #17 y #20.
5. Las fábricas de test (hoy fixtures en `conftest.py`) pasan a `tests/fabricas.py`, cargado con `pytest_plugins`, con `crear_paciente(fecha_nacimiento=...)` y `crear_estudio(estado=...)`. Cada issue que crea una tabla agrega ahí su fábrica: #7 centro y turno, #8 muestra y mensaje del bot, #14 sample set. Con ellas cada issue prueba su escenario sin esperar a los anteriores del circuito.
6. Seeds: `paciente@exoma.test` con un estudio en Creado. Como hay un solo estudio por paciente (O20), las demás pruebas manuales usan `flask demo <estado>`: crea un paciente de demo nuevo (médico tratante: `medico@exoma.test`), lo lleva al estado pedido con `crear_estudio()` y `cambiar_estado()` e imprime su mail. Las filas que necesita un estado (turno, muestra, sample set…) las agrega el issue que crea esa tabla, con una entrada en `DATOS_POR_ESTADO` de `src/core/demo.py`.
7. Un comando `flask migrar-local` que aplica `supabase/migrations` a una base local de desarrollo nombrada en `DATABASE_URL_LOCAL`. Como borra el esquema `public`, tiene la misma protección que `_url_de_test` de `conftest.py`: se niega si la URL es de Supabase o es igual a `DATABASE_URL`. Con `DATABASE_URL_LOCAL` definida, `flask run` en desarrollo usa esa base. Así cada uno prueba en el navegador con sus migraciones nuevas sin tocar el Supabase compartido.
8. `layout.html` con los bloques `head` y `scripts`, para que ninguna pantalla tenga que editar el layout.
9. `.github/workflows/tests.yml` en los PR a `develop` y a `main`, la rama `develop` creada desde `main`, y `.claude/agents/revisor-escenario.md` comparando contra `develop` (hoy dice `main`). El PR de la rama `base` va a `develop`; después, `develop` pasa a `main` antes del 17/11.
10. En `CLAUDE.md` y en `revisor-escenario.md`, la lista de rutas sin sesión y cómo se autentica cada una: login y registro (#9) son públicas; `POST /bot/telegram` (#8) valida un secreto en un header; `POST /fedex/retiros/<token>` (#19) se autentica con el token. También la convención de ramas y commits de la sección 2, que reemplaza la de S16, y la firma `notificar(..., estudio=None)` en S11.
11. `APIGEN_GRUPO_ID` en `.env.example` y en el cliente de Apigen, que lo manda en los endpoints que lo piden, para las patologías propias del grupo.

## Contratos de APIs

| API | Contrato | Issue que crea el cliente | Qué hacer mientras falte |
|---|---|---|---|
| Apigen (bioinformática, módulo 5) | `apigen/contrato.md` v1 | #3 (endpoints 3, 4, 5 y 7); #4 agrega 1 y 9; #20 agrega 8 | Copiar o enlazar el contrato en `docs/apis/apigen.md`, porque `/implementar-escenario` busca ahí |
| Módulo SNOMED | **Contrato pendiente** | #4 | Mock y borrador en `docs/apis/snomed.md` |
| Transcripción del audio del resumen | **Contrato pendiente** (ni el LEL dice quién la provee) | #10 | Mock; el médico puede corregir o escribir el texto |
| API de familiograma | **Contrato pendiente** | #10 | Mock que devuelve un PDF de ejemplo |
| API de obras sociales | **Contrato pendiente** | #17 | Mock con tres obras sociales y su porcentaje |
| Módulo de cupones | **Contrato pendiente** | #12 | Mock: generar, consultar vigencia y vencer |
| Módulo de optimización de recorridos | **Contrato pendiente** (su contratación está en evaluación) | #13 | Mock que ordena por cercanía |
| Bot de mensajería (Telegram) | La Bot API de Telegram es pública; **falta acordar el formato del mensaje** del centro | #8 | Webhook más un comando `flask bot simular` |
| API del Ministerio de Salud | **Contrato pendiente** | #14 | Mock que devuelve un PDF de autorización |
| Módulo de FedEx | **Contrato pendiente** | #19 | Mock; la URL de retiro se prueba con el cliente de test |
| Chatbot de pacientes | **Contrato pendiente** | #5 | Mock con respuestas fijas |
| Mapa | No es una API de compañeros: Leaflet servido localmente y teselas de OpenStreetMap | #7 | Lista de centros como alternativa sin conexión |

Regla para todo contrato pendiente: el issue que crea el cliente escribe en `docs/apis/<api>.md` un borrador con la interfaz que asume, marcado **provisorio**, y los mocks en `tests/fixtures/apis/<api>/`. Cuando llegue el contrato real, cambia solo el cliente.

## Observaciones abiertas que se asumen

Los supuestos son los de [decisiones.md](decisiones.md). La columna Issue dice dónde se aplica cada uno.

| # | Tema | Supuesto adoptado | Issue |
|---|---|---|---|
| O1 | Cinco o seis patologías | Seis en el LEL; se cargan las cinco base de Apigen (ver O11) | #4 |
| O2 | Sospecha familiar sin síntomas | La regla de síntomas se aplica solo con sospecha clínica. Con sospecha familiar se acepta si algún familiar tiene diagnóstico confirmado de la patología | #4, #10 |
| O3 | Cobertura parcial | El paciente paga la diferencia antes del turno, con el flujo de E14 | #17 |
| O4 | Quién registra el volumen | El administrativo, al recibir la muestra | #18 |
| O5 | Quién carga los datos crudos | El administrativo | #15 |
| O6 | Cómo se genera el resultado | El sistema arma el PDF con la plantilla a partir de las variantes | #20 |
| O7 | Inasistencia | Al cierre del día del turno, sin mensaje de muestra tomada: el turno queda `ausente` y el estudio vuelve a Habilitado para turno, con aviso al paciente | #8 |
| O8 | Costo del reanálisis | Sin costo y en el mismo estudio | #21 |
| O9 | Nombres de estados | Los 16 del LEL | #3 |
| O10 | Mail único y hermanos menores | Cada paciente tiene su propio mail | #10 |
| O11 | MPS 2 no está en Apigen | Se cargan las cinco patologías base | #4 |
| O12 | Clasificaciones y resultados | Los valores de Apigen (incluye probablemente patogénica y portador) | #20 |
| O13 | Genes ACMG en el presupuesto | No cuentan | #6 |
| O14 | Edad del Pompe urgente | Se mide al dar de alta el estudio y no cambia | #11 |
| O15 | Tipo de descuento del cupón | Porcentaje | #12 |
| O16 | Cobro a la obra social | El asiento `cobro_obra_social` queda previsto y no se registra | #6, #17 |
| O17 | Diagnóstico de un segundo estudio | Va por reanálisis | #21 |
| O18 | Estado con cobertura parcial | Sigue en Pendiente de autorización, con la cobertura `autorizada`, hasta pagar la diferencia | #17 |
| O19 | Resultado de genes agregados a mano | Positivo si hay una variante patogénica; si no, negativo | #20 |
| O20 | Un solo estudio por paciente | Sí; el historial muestra sus análisis | #3, #5, #11 |

### Supuestos nuevos de esta guía

No están en el LEL ni en decisiones.md. Se proponen para que el agente no tenga que inventarlos, y van a la lista de consultas (sección 7).

| # | Supuesto | Issue |
|---|---|---|
| G1 | En el auto registro (E01, E02) la persona elige su contraseña. En el alta por el administrador (E03) la contraseña la genera el sistema y va por mail | #9 |
| G2 | Si el diagnóstico presuntivo tiene varias patologías, cada una tiene que cumplir la regla de E08 | #4 |
| G3 | Si la API de familiograma falla, el paciente se da de alta igual y el familiograma se reintenta desde su ficha, porque el paciente "puede que no vuelva" | #10 |
| G4 | El recordatorio de turno (E21) sale el día hábil anterior al turno | #7 |
| G5 | Si el módulo de optimización falla, no se genera la orden del día: se avisa al administrativo, que la regenera a mano | #13 |
| G6 | El cupón se aplica solo al pago particular del total (E14), no a la diferencia de una cobertura parcial | #12 |
| G7 | Si el paciente sube el PDF del cupón, el sistema lee el código del texto del PDF; si no puede, pide escribirlo | #12 |
| G8 | Si la API del Ministerio falla, el sample set queda Cerrado y el administrativo reintenta la autorización | #14 |
| G9 | El transportista informa su ubicación desde el navegador del celular cada 2 minutos mientras su orden del día está en curso | #18 |
| G10 | Al registrar el retiro en un centro, el transportista se lleva todas las muestras Listo para retirar de ese centro | #13 |
| G11 | FedEx puede invocar la URL más de una vez: la segunda llamada responde 200 y no cambia nada | #19 |
| G12 | Los datos crudos se aceptan como `.txt` con solo A, C, T, G y saltos de línea, de hasta 20 MB | #15 |

# 2. Flujo de trabajo

## Milestones

Uno por control. `develop` pasa a `main` el día anterior a cada uno, con un PR que abre Integrante 1.

| Milestone | Fecha | Qué cierra |
|---|---|---|
| Control 1 (17/11) | martes 17/11, presencial | La base (#2, #3) |
| Control 2 (24/11) | martes 24/11, virtual | El primer issue de cada uno y el bot (#4–#8) |
| Control 3 (1/12) | martes 1/12, presencial | El circuito principal (#9–#15) |
| Entrega (8/12) | martes 8/12, entrega y defensa | El resto (#16–#21) |

El tablero de BI del 22/12 queda fuera de estos issues: se arma sobre `historial_estados`, `asientos_financieros` y las fechas de `sample_sets`, que estos issues ya dejan cargados.

## Labels

| Label | Para qué |
|---|---|
| `area:acceso` | Acceso y alta clínica (E01–E11, E40) |
| `area:pagos` | Presupuesto, pagos y cobertura (E13–E18, E41) |
| `area:turnos` | Turnos y logística de muestras (E19–E26) |
| `area:corea` | Envío a Corea (E28–E31) |
| `area:analisis` | Análisis y resultados (E12, E27, E32–E35) |
| `area:gestion` | Gestión médica (E36–E38) |
| `infra` | Base, configuración, CI, deploy |
| `integracion` | El issue crea o amplía el cliente de una API externa |
| `tests` | Solo tests (por ejemplo, cubrir un bug) |
| `docs` | Solo documentación |
| `bug` | Algo que no anda en `develop` |

Cada issue lleva el label del área de su escenario principal (#4 es gestión por E36; #12 es gestión por E37 y E38) y `integracion` solo si crea o amplía el cliente de una API.

## Ramas y commits

- Cada issue sale de `develop` y vuelve a `develop` por PR. Rama: `<número>-<titulo-corto>`, por ejemplo `4-patologias-sintomas`. La base usa la rama `base`, que ya existe, y su PR va a `develop`.
- Commits: `feat`, `fix`, `refactor`, `test`, `docs` o `chore`, el escenario y el número del issue. Ejemplo: `feat: E36 alta de patología con síntomas SNOMED (#4)`. Es la regla de `CLAUDE.md` (commits en español que nombran el escenario) con el tipo y el issue adelante. #3 actualiza `CLAUDE.md` y la decisión S16 con esta convención.
- El PR lo revisa y lo aprueba **otro** integrante. Para que todos lean código de todas las áreas, la revisión rota: Integrante 2 revisa a Integrante 1, 3 a 2, 4 a 3 y 1 a 4.
- Antes de cada control, Integrante 1 abre el PR `develop` → `main`, aplica las migraciones nuevas con `npx supabase db push` y corre `flask seeds`.

## Piezas compartidas

Son las que, tocadas por dos issues a la vez, se rompen entre sí. Cada una tiene un dueño. Quien no es dueño solo la usa; si necesita cambiarla, el cambio va en el issue del dueño o en uno que dependa de él.

| Pieza | La crea | La modifican después (siempre en secuencia) |
|---|---|---|
| `core/estudios/estados.py` y `servicios.py` (`crear_estudio`, `cambiar_estado`, las 21 transiciones) | #3 | Nadie |
| `helpers/auth.py`, `controllers/autenticacion.py`, `templates/autenticacion/` | #2 | #9 agrega solo el enlace "Registrarse" en `login.html`; después #16 (depende de #9) |
| `tests/conftest.py`, fixture `login_como` | #2 | #16, para que siga entrando sin código de verificación |
| `layout.html` y `templates/inicio/index.html` | #2, #3 | Nadie: cada pantalla nueva entra por el menú y por los links de los avisos |
| `pyproject.toml` y `poetry.lock` | #2, #3 | Solo con `poetry add`; en esta guía, solo #12 (pypdf) |
| `core/usuarios/modelos.py` y `servicios.py` | #2, #3 | #10 (columna `debe_cambiar_contrasena`), #16 |
| `integraciones/base.py`, `integraciones/storage.py` | #3 | Nadie |
| `integraciones/apigen.py` | #3 | #4 (endpoints 1 y 9, Control 2) y #20 (endpoint 8, Entrega) |
| Buscador SNOMED (macro con parámetros, JS y endpoint) | #4 | Nadie; #9 y #10 lo usan pasándole su URL, tipo y campo |
| Mocks en `tests/fixtures/apis/<api>/` | El issue que crea el cliente | Nadie |
| `src/web/tareas.py` (APScheduler) | #7 | #8 y #13, en ese orden |
| `helpers/pdf.py` y el mapa (Leaflet y macro `_mapa.html`) | #7 | Nadie; #18 y #20 los usan |
| `core/pagos` (presupuesto y pago) | #6 | #12 (cupón) y #17 (diferencia de la cobertura), en ese orden |
| `core/finanzas` (asientos) | #6 | Nadie |
| `core/logistica` | #8 (modelos), #13 | #18 |
| `core/sample_sets` | #8 (modelo), #14 | #19 |
| `core/analisis` (pendientes, tomar, variantes) | #15 | #20 y después #21 |
| Detalle del estudio en el historial | #5 | #21 (botón de reanálisis) |
| Registros de una línea: `MENU_POR_ROL` en `helpers/menu.py`, `register_blueprint` en `web/__init__.py`, `seeds.py`, `tests/fabricas.py`, `DATOS_POR_ESTADO` de `src/core/demo.py`, `.env.example` | Todos | Solo se **agregan** líneas. Si hay conflicto al mergear, se conservan las dos |

## Migraciones

- Cada tabla la crea completa, como dice [modelo-datos.md](modelo-datos.md), el primer issue de esta guía que la necesita. La tabla de la sección 3 lo indica en cada issue.
- Antes de abrir el PR, si `develop` ya tiene una migración con timestamp posterior a la tuya, regenerala con `npx supabase migration new` y mové el SQL: `db push` no aplica migraciones más viejas que la última aplicada.
- Nadie aplica migraciones al Supabase compartido desde su rama. Para probar en el navegador se usa la base local de `DATABASE_URL_LOCAL` con `flask migrar-local` (punto 7 de la sección 1).

## El flujo de un issue

1. **Preparar.** `git switch develop`, `git pull` y `git switch -c 4-patologias-sintomas`. Abrí `claude` en la raíz del repo y, si venías de otra tarea, `/clear`. Comprobá que los issues de "Depende de" estén mergeados en `develop`.
2. **Planificar.** Plan mode (`Shift+Tab` hasta ver *plan mode on*) y pegá el **prompt de referencia** del issue (sección 5). Arranca con `/implementar-escenario`, que ya pide leer el escenario, el LEL, el contrato y el módulo de referencia.
3. **Revisar el plan (vos).** ¿Usa los nombres del LEL? ¿Crea solo las tablas que le tocan? ¿Toca una pieza compartida de la que no es dueño? ¿Hay un test por episodio? Si algo no cierra, pedí otro plan.
4. **Implementar.** Aprobá el plan. El agente edita y corre `pytest` hasta que pasa. Leé cada cambio y frenalo con `Esc` si se desvía.
5. **Probar a mano (vos).** `poetry run flask migrar-local`; si el escenario parte de un estado, `poetry run flask demo <estado>`; y `poetry run flask run --debug` sobre la base local, con los usuarios que dice el prompt, en la computadora y en el celular.
6. **Revisar con contexto limpio.** "Usá el subagente revisor-escenario para revisar E36, E07 y E08 contra el diff con develop". Corregí lo que afecte la corrección o los requisitos.
7. **Guía de estudio.** `/guia-estudio E07-E08-E36` (los escenarios del issue unidos con guiones). Deja `docs/estudio/E07-E08-E36.md`, que es lo que vas a estudiar para el coloquio.
8. **PR a develop.** "Commiteá y abrí un PR con gh a develop: el título nombra los escenarios, el cuerpo dice qué cambia, cómo se probó, qué se asumió, si hay migraciones, y cierra con Closes #4". Lo revisa el integrante que toca por rotación. La Action tiene que estar en verde.

# 3. Tabla de issues

Los números son los que va a asignar GitHub si el script de la sección 9 corre antes de abrir cualquier otro issue o PR. El último número usado es el del PR #1, así que los issues empiezan en #2. Si GitHub asigna otros, el script reescribe las referencias entre issues y deja la correspondencia en `scripts/issues-creados.csv`.

"Depende de" nombra los issues cuyo **código** usa este issue: tienen que estar mergeados en `develop` antes de empezar. Para el estado de partida de cada escenario no hace falta esperar al circuito completo: se usan las fábricas de test y los seeds de demo de #3. La numeración es topológica: cada issue depende solo de issues con número menor, así que no puede haber ciclos.

<!-- tabla-issues -->
| # | Título | Escenarios | Área (label) | Puntos | Rama | Depende de | Responsable | Milestone |
|---|---|---|---|---|---|---|---|---|
| #2 | Base: estructura, base de datos y login | — (sesiones 2–4) | `infra` | 5 | `base` | — | Integrante 1 | Control 1 (17/11) |
| #3 | Base: estados, notificaciones, integraciones y módulo de usuarios | E03, E39 | `infra` `integracion` | 5 | `base` | #2 | Integrante 1 | Control 1 (17/11) |
| #4 | Patologías, síntomas SNOMED y validación del diagnóstico | E07, E08, E36 | `area:gestion` `integracion` | 5 | `4-patologias-sintomas` | #3 | Integrante 2 | Control 2 (24/11) |
| #5 | Historial de estudios y chatbot del paciente | E11, E40 | `area:acceso` `integracion` | 3 | `5-historial-chatbot` | #3 | Integrante 1 | Control 2 (24/11) |
| #6 | Presupuesto, pago particular y registro financiero | E13, E14, E41 | `area:pagos` | 5 | `6-presupuesto-pago` | #3 | Integrante 3 | Control 2 (24/11) |
| #7 | Turnos de extracción: reservar, cancelar y recordar | E19, E20, E21 | `area:turnos` | 5 | `7-turnos-extraccion` | #3 | Integrante 4 | Control 2 (24/11) |
| #8 | Toma de muestra por el bot e inasistencias | E22 | `area:turnos` `integracion` | 3 | `8-bot-toma-muestra` | #7 | Integrante 1 | Control 2 (24/11) |
| #9 | Registro de médicos y del personal del laboratorio | E01, E02 | `area:acceso` | 3 | `9-registro-usuarios` | #4 | Integrante 2 | Control 3 (1/12) |
| #10 | Alta de paciente y familiograma | E06, E09 | `area:acceso` `integracion` | 5 | `10-alta-paciente` | #4 | Integrante 2 | Control 3 (1/12) |
| #11 | Alta de estudio con genes de Apigen | E10 | `area:acceso` | 3 | `11-alta-estudio` | #10 | Integrante 3 | Control 3 (1/12) |
| #12 | Cupones de descuento | E15, E37, E38 | `area:gestion` `integracion` | 5 | `12-cupones` | #6 | Integrante 3 | Control 3 (1/12) |
| #13 | Orden del día y retiro de muestras | E23, E24 | `area:turnos` `integracion` | 5 | `13-orden-del-dia` | #8 | Integrante 4 | Control 3 (1/12) |
| #14 | Sample set y autorización ministerial | E28, E29 | `area:corea` `integracion` | 5 | `14-sample-set` | #8 | Integrante 1 | Control 3 (1/12) |
| #15 | Nueva extracción, datos crudos y toma del estudio | E27, E32, E33 | `area:analisis` | 5 | `15-datos-crudos` | #8 | Integrante 4 | Control 3 (1/12) |
| #16 | Código de verificación y activación de la cuenta del paciente | E04, E05 | `area:acceso` | 3 | `16-verificacion-activacion` | #5, #9, #10 | Integrante 2 | Entrega (8/12) |
| #17 | Cobertura de obra social y reautorización | E16, E17, E18 | `area:pagos` `integracion` | 5 | `17-obra-social` | #12 | Integrante 4 | Entrega (8/12) |
| #18 | Seguimiento y llegada de las muestras al laboratorio central | E25, E26 | `area:turnos` | 5 | `18-llegada-muestras` | #13, #14, #15 | Integrante 3 | Entrega (8/12) |
| #19 | Retiro de FedEx y despacho del sample set | E30, E31 | `area:corea` `integracion` | 3 | `19-retiro-fedex` | #14 | Integrante 3 | Entrega (8/12) |
| #20 | Variantes y resultado del estudio | E34, E35 | `area:analisis` `integracion` | 5 | `20-variantes-resultado` | #5, #11, #15 | Integrante 2 | Entrega (8/12) |
| #21 | Reanálisis | E12 | `area:analisis` | 2 | `21-reanalisis` | #5, #11, #20 | Integrante 4 | Entrega (8/12) |
<!-- fin tabla-issues -->

**Total:** 20 issues, 85 puntos. Escala: 1 = un cambio chico; 2 = una pantalla con su regla; 3 = un escenario con una integración o una tarea programada, o dos escenarios chicos con una integración; 5 = dos o tres escenarios con varias reglas, integraciones o tareas programadas.

## Cada escenario en un solo issue

| Escenario | Issue | Escenario | Issue | Escenario | Issue | Escenario | Issue |
|---|---|---|---|---|---|---|---|
| E01 | #9 | E12 | #21 | E23 | #13 | E34 | #20 |
| E02 | #9 | E13 | #6 | E24 | #13 | E35 | #20 |
| E03 | #3 | E14 | #6 | E25 | #18 | E36 | #4 |
| E04 | #16 | E15 | #12 | E26 | #18 | E37 | #12 |
| E05 | #16 | E16 | #17 | E27 | #15 | E38 | #12 |
| E06 | #10 | E17 | #17 | E28 | #14 | E39 | #3 |
| E07 | #4 | E18 | #17 | E29 | #14 | E40 | #5 |
| E08 | #4 | E19 | #7 | E30 | #19 | E41 | #6 |
| E09 | #10 | E20 | #7 | E31 | #19 | | |
| E10 | #11 | E21 | #7 | E32 | #15 | | |
| E11 | #5 | E22 | #8 | E33 | #15 | | |

Cuatro escenarios tienen una parte que ya resolvió, o que completa, otro issue. No es una segunda asignación, pero conviene saberlo:

- **E04** está en #16. La base (#2) ya hizo los episodios 1–3 y 6 (usuario, contraseña, rechazo y vista por rol); #16 agrega el código de verificación (episodios 4 y 5) y vuelve a probar el escenario entero.
- **E14** está en #6. Su episodio 3 ("si tiene un cupón, realiza APLICAR CUPÓN") lo completa #12, que implementa E15 y lo repite como criterio.
- **E41** está en #6, que deja `registrar_asiento()` para todos los tipos. Sus episodios 2 (descuento del cupón) y 3 (cobertura de la obra social) se aceptan en #12 y #17, que los repiten como criterios.
- **E26** está en #18. Su episodio 5 llama a SOLICITAR NUEVA EXTRACCIÓN (E27, #15) y el 6 a ARMAR SAMPLE SET (E28, #14): #18 las usa, no las reescribe.

## Tablas que crea cada issue

Las 39 tablas de [modelo-datos.md](modelo-datos.md), cada una en un solo issue. El orden cambia un poco respecto del "Orden sugerido" del modelo: `pacientes` y `estudios` van en la base (sesión 5) antes que `patologias`, porque ninguna de las dos tiene clave foránea a patologías.

| Issue | Tablas o columnas nuevas |
|---|---|
| #2 | `roles`, `usuarios` |
| #3 | `usuarios.telefono`, `medicos`, `pacientes`, `estudios`, `historial_estados`, `analisis`, `analisis_genes` (sesión 5, hecha); `provincias`, `transportistas` (E03); `notificaciones` (sesión 6) |
| #4 | `terminos_snomed`, `patologias`, `patologia_sintomas` |
| #6 | `obras_sociales`, `cupones`, `presupuestos`, `pagos`, `asientos_financieros`. `cupones` y `obras_sociales` van acá porque `pagos` y `asientos_financieros` las referencian |
| #7 | `feriados`, `centros_extraccion`, `turnos_extraccion` |
| #8 | `mensajes_bot`, `ordenes_del_dia`, `paradas_orden_del_dia`, `sample_sets`, `muestras`. Las tres del medio son destino de claves foráneas de `muestras`; sus pantallas son de #13 y #14 |
| #9 | `medico_especialidades` |
| #10 | `usuarios.debe_cambiar_contrasena`, `paciente_sintomas`, `diagnosticos_presuntivos`, `familiares`, `familiar_sintomas`, `familiar_patologias` |
| #11 | `analisis_patologias` |
| #16 | `dispositivos_confiables`, `codigos_verificacion` |
| #17 | `coberturas`, `demandas_reautorizacion` |
| #20 | `variantes_encontradas` |
| #5, #12–#15, #18, #19, #21 | Ninguna: usan tablas de issues anteriores |

# 4. Reparto

| Integrante | Usuario de GitHub | Issues | Puntos | Áreas | Integraciones |
|---|---|---|---|---|---|
| Integrante 1 | | #2, #3, #5, #8, #14 | 5 + 5 + 3 + 3 + 5 = **21** | infra, acceso, turnos, corea | Crea: Apigen y Storage (#3), chatbot (#5), Telegram (#8), Ministerio de Salud (#14) |
| Integrante 2 | | #4, #9, #10, #16, #20 | 5 + 3 + 5 + 3 + 5 = **21** | gestión, acceso, análisis | Crea: SNOMED (#4), familiograma y transcripción (#10). Amplía Apigen: endpoints 1 y 9 (#4) y 8 (#20) |
| Integrante 3 | | #6, #11, #12, #18, #19 | 5 + 3 + 5 + 5 + 3 = **21** | pagos, acceso, gestión, turnos, corea | Crea: módulo de cupones (#12), FedEx (#19). Usa Apigen (#11) |
| Integrante 4 | | #7, #13, #15, #17, #21 | 5 + 5 + 5 + 5 + 2 = **22** | turnos, análisis, pagos | Crea: optimización de recorridos (#13), obras sociales (#17). Usa Apigen (#21) |

Carga por milestone:

| Integrante | Control 1 | Control 2 | Control 3 | Entrega |
|---|---|---|---|---|
| Integrante 1 | 10 (#2, #3) | 6 (#5, #8) | 5 (#14) | 0: pasa `develop` a `main`, aplica migraciones, corrige bugs y prepara el deploy |
| Integrante 2 | 0 | 5 (#4) | 8 (#9, #10) | 8 (#16, #20) |
| Integrante 3 | 0 | 5 (#6) | 8 (#11, #12) | 8 (#18, #19) |
| Integrante 4 | 0 | 5 (#7) | 10 (#13, #15) | 7 (#17, #21) |
| **Total** | 10 | 21 | 31 | 23 |

Hasta que #3 esté en `develop`, Integrantes 2 a 4 preparan su primer issue en plan mode (sin editar) y escriben el borrador del contrato de la API que les toca.

## Chequeo de los criterios

1. **Issues verticales.** Cada issue tiene core, controlador con sus rutas y roles, vistas y tests. Los que necesitan una tabla nueva traen su migración (tabla de arriba) y los que usan una API traen su cliente o lo amplían. No hay issues de "solo back" ni de "solo front". Los escenarios que hace el sistema solo (E21, E23, E28, E29) también tienen pantalla: la lista que consulta el rol que los sigue.
2. **Tres áreas y una integración por persona.** Integrante 1: acceso, turnos y corea, más la base. Integrante 2: gestión, acceso y análisis. Integrante 3: pagos, acceso, gestión, turnos y corea. Integrante 4: turnos, análisis y pagos. Cada uno crea al menos un cliente de API nuevo (columna Integraciones).
3. **Carga equitativa.** Promedio 21,25 puntos; el rango de ±10 % va de 19,1 a 23,4. Quedan 21, 21, 21 y 22, contando #2 como pide el reparto. Sobre lo pendiente, Integrante 1 tiene 16: es a propósito, porque en la Entrega se ocupa de pasar `develop` a `main`, aplicar las migraciones, el deploy y los bugs, que no son issues con puntos. Si el grupo prefiere emparejar lo pendiente, #19 (3 puntos, depende de su #14) pasa a Integrante 1: quedarían 24, 21, 18 y 22, fuera del ±10 % con #2 incluido.
4. **Dependencias sin ciclos y sin choques.** Cada issue depende solo de números menores. Los issues de un mismo milestone que se hacen en paralelo no comparten ninguna pieza de la tabla "Piezas compartidas": donde dos la tocan, uno depende del otro (#7 → #8 → #13 en `tareas.py`; #6 → #12 → #17 en `core/pagos`; #9 → #16 en `login.html`; #15 → #20 → #21 en `core/analisis`; #4 → #20 en `apigen.py`). En Control 3, #9 y #10 no comparten archivos: #9 pone las especialidades en un archivo nuevo, `core/usuarios/especialidades.py` (modelo y `guardar_especialidades`, que llama desde `controllers/usuarios.py`), y no toca `modelos.py` ni `servicios.py`; #10 es el único que modifica `modelos.py` en ese milestone. #13, #14 y #15 usan la fábrica de muestras de #8 y ninguno escribe la suya.

# 5. Detalle de cada issue

Cada detalle es también el cuerpo del issue en GitHub (el script lo copia entre las marcas `<!-- issue:N -->`). Los criterios de aceptación son los episodios del escenario, numerados `E##.n`. Los prompts no repiten lo que ya dice `CLAUDE.md` (decoradores, CSRF, `cambiar_estado()`, nombres del LEL, tests antes de terminar).

## #2 · Base: estructura, base de datos y login

<!-- issue:2 -->
**Escenarios:** ninguno (sesiones 2–4 de `docs/guia-agentes.md`) · **Área:** infra · **Puntos:** 5 · **Rama:** `base` · **Depende de:** — · **Milestone:** Control 1 (17/11) · **Estado:** hecho en la rama `base` (commits `4a48003` a `499e4e1`); se cierra con el PR de la base.

**Objetivo.** Que cualquiera pueda clonar, instalar, levantar la app, entrar con cada rol y correr los tests.

**Criterios de aceptación**

- Estructura MVC de `sistema/`, Poetry con las dependencias de la guía, `create_app()` con configuraciones Development, Testing y Production, páginas 403, 404, 500 y de CSRF.
- Flask-SQLAlchemy-Lite y migración inicial `roles` y `usuarios` con RLS activado y sin políticas.
- `tests/conftest.py` sobre `DATABASE_URL_TEST`: crea la base si falta, aplica las migraciones en orden y revierte cada test.
- Login y logout con Flask-Session y scrypt; la sesión vence tras 8 h y el login regenera su id; el mensaje de error no dice si el mail existe.
- `login_required`, `rol_requerido(*roles)`, CSRF en todo POST y `Cache-Control: no-store`.
- `layout.html` responsivo con Bootstrap local, menú por rol y mensajes flash; `flask seeds` con un usuario por rol.

**Qué toca por capa:** ya está hecho; ver la sección 1 de `docs/guia-issues.md`.

**Tests mínimos (existentes):** `test_app.py`, `test_autenticacion.py`, `test_base_de_datos.py`, `test_csrf.py`, `test_seeds.py`.

**Fuera de alcance:** el código por dispositivo nuevo (E04 ep. 4 y 5, en #16) y la activación de la cuenta del paciente (E05, en #16).

**Prompt de referencia:** no aplica. Se ejecutaron los prompts de las sesiones 2, 3 y 4 de `docs/guia-agentes.md`.
<!-- /issue:2 -->

## #3 · Base: estados, notificaciones, integraciones y módulo de usuarios

<!-- issue:3 -->
**Escenarios:** E03, E39 · **Área:** infra · **Puntos:** 5 · **Rama:** `base` · **Depende de:** #2 · **Milestone:** Control 1 (17/11) · **Estado:** sesión 5 hecha (commit `0200281`); faltan las sesiones 6 y 7.

**Objetivo.** Terminar las sesiones 5 a 7 de `docs/guia-agentes.md` y dejar las piezas que los demás issues usan sin modificarlas. Bloquea a todos los demás issues.

**Criterios de aceptación**

- Sesión 5 (hecha): modelos `Paciente`, `Estudio`, `HistorialEstado`, `Analisis` y `AnalisisGen`; enum de 16 estados con las 21 transiciones del LEL; `crear_estudio()` con el código del estudio, el análisis inicial y la primera fila del historial; `cambiar_estado(estudio, nuevo_estado, usuario, motivo=None)`, que rechaza lo que no está en el LEL y guarda el historial con fecha y usuario.
- Sesión 6: cliente base con `httpx` (timeout de 5 s, `IntegracionError` con mensaje legible, mock con `USE_MOCKS=1` desde `tests/fixtures/apis/`); cliente de Apigen con los endpoints 3, 4, 5 y 7 y `APIGEN_GRUPO_ID`; `integraciones/storage.py` con mock en disco; `layout.html` con los bloques `head` y `scripts`.
- E39.1 El sistema detecta un evento que requiere avisar a un usuario (lo invoca cada issue con `notificar(usuario, asunto, mensaje, link, estudio=None)`).
- E39.2 El sistema envía una notificación por mail (en desarrollo, por consola).
- E39.3 El sistema publica un aviso en la lista de pendientes del usuario.
- E39.4 El usuario consulta sus avisos y accede a la tarea pendiente (`GET /avisos/<id>` marca el aviso leído y redirige al link).
- E03.1 El administrador general elige el rol del nuevo usuario: médico tratante, gerente médico, administrativo, bioinformático o transportista.
- E03.2 El administrador general completa los datos que corresponden al rol (matrícula para médicos y gerentes; provincia para transportistas, con un solo transportista por provincia).
- E03.3 El sistema crea las credenciales de acceso (contraseña generada al azar).
- E03.4 El sistema envía al nuevo usuario una notificación por mail con sus credenciales.
- Cierre: grilla de usuarios con búsqueda, filtro por rol, orden y paginación, y las once piezas de "Lo que la base (#3) tiene que dejar" de la sección 1 de la guía.

**Qué toca por capa**

- Migración: una nueva con `provincias` (24 filas fijas), `transportistas` y `notificaciones`, como en `docs/modelo-datos.md`.
- Core: `core/notificaciones`; `core/usuarios` (alta por rol, `listar_activos_por_rol`, `telefono` en `crear_usuario`); `core/demo.py` (`DATOS_POR_ESTADO` y el camino de estados que hoy usa la fixture `crear_estudio`).
- Controlador: `usuarios` (administrador general): `GET /usuarios`, `GET|POST /usuarios/nuevo`. `avisos` (todos los roles): `GET /avisos`, `GET /avisos/<id>`.
- Vistas: `usuarios/listado.html`, `usuarios/formulario.html`, `avisos/listado.html`, `mails/credenciales.html`; contador de avisos sin leer en el layout.
- Integraciones: `base.py`, `apigen.py`, `storage.py`.
- Comandos: `flask migrar-local` (con `DATABASE_URL_LOCAL` y su protección) y `flask demo <estado>`.
- Tests: las fábricas pasan de `conftest.py` a `tests/fabricas.py`, cargado con `pytest_plugins`.
- Docs: `CLAUDE.md` (rutas sin sesión, convención de ramas y commits, "Cómo agregar un módulo"), `.claude/agents/revisor-escenario.md` (contra `develop` y con las rutas sin sesión) y S11 y S16 de `docs/decisiones.md`.

**Cambios de estado y reglas**

- No agrega transiciones: usa las 21 que ya están.
- Un solo transportista por provincia; matrícula única; mail único sin distinguir mayúsculas.
- `flask migrar-local` se niega si la URL es de Supabase o es igual a `DATABASE_URL`, porque borra el esquema `public`.
- `flask demo` crea siempre un paciente nuevo (O20) y solo usa `crear_estudio()` y `cambiar_estado()`. Un estado que necesita filas de un issue que todavía no está (turno, muestra, sample set) falla con un mensaje claro.

**Tests mínimos**

- E39: `notificar` guarda el aviso y manda el mail; el usuario ve solo sus avisos; abrir uno lo marca leído y lleva al link.
- E03: alta de cada rol; mail repetido; segundo transportista en la misma provincia; un médico tratante entra a `/usuarios` → 403; el mail con las credenciales sale.
- Cliente base: timeout, error HTTP y mock. Apigen: una prueba con mock por endpoint.
- `migrar-local` con una URL de Supabase o igual a `DATABASE_URL` → se niega.
- `flask demo habilitado_turno` → paciente nuevo con su estudio en ese estado y el historial completo.
- La suite existente sigue en verde después de mover las fábricas.

**Fuera de alcance y supuestos:** especialidades SNOMED en el alta de médicos (las agrega #9); bajas y modificación de usuarios (restricción de E03); O9 y O20.

**Prompt de referencia.** Quedan dos sesiones, cada una con `/clear` y plan mode. La sesión 5 ya está en `0200281`.

Sesión 6:

```text
/implementar-escenario E39
Issue #3, sesión 6 de @docs/guia-agentes.md (notificaciones e integraciones). La sesión 5 está
hecha: leé src/core/estudios y src/core/usuarios antes de planificar.
Migración: notificaciones según @docs/modelo-datos.md.
notificar(usuario, asunto, mensaje, link, estudio=None) guarda el aviso y manda el mail (en
desarrollo, por consola). "Mis avisos" en el layout; GET /avisos/<id> lo marca leído y redirige.
Cliente base con httpx: timeout de 5 s, IntegracionError con mensaje legible y mocks desde
tests/fixtures/apis/ con USE_MOCKS=1. Cliente de Apigen con los endpoints 3, 4, 5 y 7 de
@apigen/contrato.md y APIGEN_GRUPO_ID (agregala a .env.example); copiá el contrato a
docs/apis/apigen.md. integraciones/storage.py: bucket privado de Supabase Storage, con mock en
instance/storage/.
layout.html con bloques head y scripts, para que ningún módulo lo tenga que editar.
No toques core/estudios ni la lógica del login.
Tests: un mock por función, timeout sin romper, avisos de otro usuario que no se ven, E39.1-4.
Control: pytest en verde; con flask run, un aviso de prueba aparece en "Mis avisos" y el mail sale
por consola.
```

Sesión 7:

```text
/implementar-escenario E03
Issue #3, sesión 7 de @docs/guia-agentes.md: el módulo de referencia que copian todos. Grilla de
usuarios con búsqueda, filtro por rol, orden y paginación del servidor; alta con validación en
servidor y cliente; mail con credenciales. Solo el administrador general.
Migración: provincias (24 filas fijas) y transportistas según @docs/modelo-datos.md. Médico y
gerente cargan matrícula (crear_perfil_medico); transportista, provincia (uno por provincia).
Agregá crear_usuario(telefono=...) y listar_activos_por_rol(rol).
Cerrá las piezas de "Lo que la base (#3) tiene que dejar" en la sección 1 de @docs/guia-issues.md:
fábricas de conftest.py a tests/fabricas.py con pytest_plugins; flask migrar-local con
DATABASE_URL_LOCAL y la protección de _url_de_test; flask demo <estado> con DATOS_POR_ESTADO;
.github/workflows/tests.yml; CLAUDE.md, revisor-escenario.md, y S11 y S16 de decisiones.md.
No cambies core/estudios/estados.py ni servicios.py, ni la lógica del login.
Tests: alta de cada rol, mail repetido, segundo transportista en una provincia, permisos,
migrar-local que se niega con Supabase y flask demo habilitado_turno.
Control: pytest en verde; admin@exoma.test da de alta un transportista y le llega el mail. Decime
qué falta de "Qué incluye la base" de @docs/guia-agentes.md.
```
<!-- /issue:3 -->

## #4 · Patologías, síntomas SNOMED y validación del diagnóstico

<!-- issue:4 -->
**Escenarios:** E07, E08, E36 · **Área:** gestión médica · **Puntos:** 5 · **Rama:** `4-patologias-sintomas` · **Depende de:** #3 · **Milestone:** Control 2 (24/11)

**Objetivo.** El gerente médico define las patologías con su síntoma cardinal y sus síntomas secundarios codificados en SNOMED. Quedan dos piezas que usan otros issues sin modificarlas: el buscador de síntomas (E07) y la regla que valida el diagnóstico presuntivo (E08).

**Criterios de aceptación**

- E07.1 El médico tratante o el gerente médico escribe parte del síntoma.
- E07.2 El sistema consulta el módulo SNOMED a medida que se escribe.
- E07.3 El sistema muestra los términos que coinciden con lo escrito.
- E07.4 El médico tratante o el gerente médico elige el síntoma.
- E07.5 El sistema agrega el síntoma a la lista.
- E08.1 El sistema obtiene el síntoma cardinal y los síntomas secundarios de cada patología del diagnóstico presuntivo.
- E08.2 El sistema compara esos síntomas con la lista de síntomas del paciente.
- E08.3 Si el paciente presenta el síntoma cardinal o al menos dos síntomas secundarios, el sistema acepta el alta.
- E08.4 Si no se cumple la regla, el sistema rechaza el alta.
- E08.5 Si rechaza el alta, el sistema informa la inconsistencia al médico tratante (qué patología y qué falta).
- E08.6 Si se rechazó el alta, el médico tratante corrige el diagnóstico presuntivo o la lista de síntomas (la función se puede volver a llamar; el formulario es de #10).
- E36.1 El gerente médico carga el nombre de la patología lisosomal (y, si es propia del grupo, el código y la herencia que pide el endpoint 9 de Apigen).
- E36.2 El gerente médico selecciona el síntoma cardinal mediante BUSCAR SÍNTOMA.
- E36.3 El gerente médico selecciona los síntomas secundarios mediante BUSCAR SÍNTOMA.
- E36.4 El sistema guarda la patología para su uso en VALIDAR DIAGNÓSTICO PRESUNTIVO.
- E36.5 Cuando lo necesite, el gerente médico modifica el síntoma cardinal o los síntomas secundarios.

**Qué toca por capa**

- Migración: `terminos_snomed`, `patologias`, `patologia_sintomas` (con el índice único parcial de un solo cardinal). Seeds: las 5 patologías base de Apigen con síntomas inventados.
- Core: `core/patologias` (modelos, alta, modificación, activar/desactivar) y `validar_diagnostico_presuntivo(sintomas, patologias, tipo_sospecha, patologias_de_familiares)`, una función pura que devuelve si acepta y las inconsistencias por patología. `core/snomed`: guardar el término elegido en `terminos_snomed` (upsert).
- Controlador: `patologias` (gerente médico): `GET /patologias`, `GET|POST /patologias/nueva`, `GET|POST /patologias/<id>/editar`, `POST /patologias/<id>/activa`. `snomed` (médico tratante y gerente médico): `GET /snomed/terminos?q=&tipo=sintoma` en JSON.
- Vistas: `patologias/listado.html`, `patologias/formulario.html`; macro `snomed/_buscador.html` con parámetros (URL del endpoint, tipo `sintoma` o `especialidad`, nombre del campo oculto y si admite uno o varios términos) y `static/js/buscador_snomed.js` (desde 3 letras, con espera entre teclas). Se puede repetir en la misma página: #10 lo usa para el paciente y para cada familiar, y #4 para el cardinal (uno) y los secundarios (varios).
- Integración: `integraciones/snomed.py` con `buscar_terminos(texto, tipo)` (**contrato pendiente**: mocks de síntomas y de especialidades, y borrador en `docs/apis/snomed.md`). Apigen: endpoint 1 (buscar genes) y 9 (alta de patología del grupo), que se agregan a `apigen.py`.

**Cambios de estado y reglas**

- Sin cambios de estado del estudio.
- Un solo síntoma cardinal por patología; el cardinal no puede estar también entre los secundarios.
- Regla de E08 con O2: con sospecha clínica, cardinal o al menos dos secundarios; con sospecha familiar, se acepta si algún familiar tiene diagnóstico de esa patología. Con varias patologías, todas tienen que cumplir (G2).
- Una patología inactiva no se ofrece en el diagnóstico presuntivo. No hay bajas.
- Una patología que no es base se da de alta en Apigen (endpoint 9, con `APIGEN_GRUPO_ID`, código de 2 a 30 caracteres en mayúsculas, números o `_`, y herencia) con los genes elegidos (endpoint 1); si Apigen falla, no se guarda.

**Tests mínimos**

- Regla: solo cardinal → acepta; dos secundarios → acepta; un secundario → rechaza; ninguno → rechaza con la inconsistencia; dos patologías con una que falla → rechaza; sospecha familiar sin síntomas con familiar diagnosticado → acepta; sin familiar diagnosticado → rechaza.
- E36: alta con cardinal y dos secundarios; dos cardinales → error; nombre repetido → error; modificar los síntomas; desactivar.
- Buscador: menos de 3 letras → lista vacía; SNOMED caído → JSON de error legible.
- Permisos: médico tratante → 403 en `/patologias`; paciente → 403 en `/snomed/terminos`.
- Apigen caído en el alta de una patología del grupo → no se guarda.

**Fuera de alcance y supuestos:** el catálogo SNOMED completo vive en el módulo; MPS 2 no se carga (O11); G2.

**Prompt de referencia**

```text
/implementar-escenario E36 E07 E08
Issue #4; la base (#3) está en develop. Leé el módulo usuarios, integraciones/base.py y apigen.py,
apigen/contrato.md (endpoints 1 y 9), O2 y O11 de @docs/decisiones.md y las tablas
terminos_snomed, patologias y patologia_sintomas de @docs/modelo-datos.md.
Migración: esas tres tablas tal cual (con el índice de un solo cardinal) y seeds de las 5
patologías base de Apigen con síntomas inventados.
SNOMED no tiene contrato: integraciones/snomed.py con buscar_terminos(texto, tipo), mocks de
síntomas y especialidades en tests/fixtures/apis/snomed/ y un borrador en docs/apis/snomed.md.
E07 queda reutilizable: GET /snomed/terminos en JSON (médico tratante y gerente médico) y un macro
con parámetros (URL, tipo, nombre del campo, uno o varios) que se puede repetir en una página.
E08 es una función pura validar_diagnostico_presuntivo(sintomas, patologias, tipo_sospecha,
patologias_de_familiares), sin base ni Flask, que devuelve si acepta y las inconsistencias.
Aplicá O2 y que cumplan todas las patologías (G2 de @docs/guia-issues.md).
E36 solo para el gerente médico, sin bajas (activa). Patología del grupo: código, herencia y genes
(endpoint 1); alta en Apigen con el 9 y APIGEN_GRUPO_ID; si falla, no se guarda.
En apigen.py solo agregás los endpoints 1 y 9. No toques core/estudios, layout.html ni auth.
Tests: cada caso de la regla (cardinal, dos secundarios, uno, ninguno, dos patologías con una que
falla, familiar con y sin diagnóstico), dos cardinales, permisos y APIs caídas.
Control: pytest en verde; gerente@exoma.test da de alta una patología y le cambia un secundario.
```
<!-- /issue:4 -->

## #5 · Historial de estudios y chatbot del paciente

<!-- issue:5 -->
**Escenarios:** E11, E40 · **Área:** acceso y alta clínica · **Puntos:** 3 · **Rama:** `5-historial-chatbot` · **Depende de:** #3 · **Milestone:** Control 2 (24/11)

**Objetivo.** El médico tratante y el paciente ven el estudio y en qué estado está; el paciente le hace preguntas al chatbot. Es la vista del paciente que habilita E05.

**Criterios de aceptación**

- E11.1 El médico tratante o el paciente accede al historial de estudios del paciente.
- E11.2 El sistema muestra cada estudio con su estado actual (por O20 hay uno solo, con sus análisis: el inicial y cada reanálisis, y las fechas de cada cambio de estado).
- E11.3 El médico tratante o el paciente selecciona un estudio.
- E11.4 El sistema muestra el detalle del estudio y, si está Finalizado, el resultado del estudio (descarga del PDF).
- E40.1 El paciente escribe una pregunta en la interfaz del sistema.
- E40.2 El sistema delega la pregunta al chatbot de pacientes.
- E40.3 El sistema muestra la respuesta al paciente.

**Qué toca por capa**

- Migración: ninguna.
- Core: `core/historial` con consultas de solo lectura (`estudio_del_paciente`, `estudios_del_medico(busqueda)`, `puede_ver(usuario, estudio)`). No modifica `core/estudios`.
- Controlador: `historial` (paciente y médico tratante): `GET /historial`, `GET /historial/estudios/<id>`, `GET /historial/analisis/<id>/resultado` (descarga desde Storage). `chatbot` (paciente): `GET|POST /chatbot`.
- Vistas: `historial/listado.html` (el médico busca por DNI o nombre), `historial/detalle.html` (estado con el nombre del LEL, línea de tiempo de `historial_estados`, análisis con su resultado), `chatbot/conversacion.html`.
- Integración: `integraciones/chatbot.py` con `preguntar(texto)` (**contrato pendiente**: mock y `docs/apis/chatbot.md`); Storage para la descarga.

**Cambios de estado y reglas**

- Sin cambios de estado.
- El paciente ve solo su estudio y el médico tratante solo los de sus pacientes: un estudio ajeno responde 404, para no revelar que existe.
- La descarga del resultado exige el mismo permiso y que el análisis tenga `resultado_path`.
- Pregunta obligatoria y de hasta 1000 caracteres. Las conversaciones no se guardan. Si el chatbot no responde, se muestra "el chatbot no está disponible" sin romper.

**Tests mínimos**

- El paciente ve su estudio y su estado; pide el de otro → 404.
- El médico ve los de sus pacientes y no los de otro médico.
- Un estudio Finalizado muestra la descarga y uno en análisis no; descarga sin permiso → 404.
- El administrativo entra a `/historial` → 403; el médico entra a `/chatbot` → 403.
- Chatbot: respuesta con mock, pregunta vacía → 400, API caída → aviso.

**Fuera de alcance y supuestos:** el PDF del resultado lo genera #20 y el botón de reanálisis lo agrega #21; O20.

**Prompt de referencia**

```text
/implementar-escenario E11 E40
Issue #5; la base (#3) está en develop. Leé primero el módulo usuarios como referencia,
src/core/estudios (modelos y estados, sin modificarlos), src/integraciones/base.py y storage.py,
y la observación O20 de @docs/decisiones.md: hay un solo estudio por paciente y el historial
muestra sus análisis (inicial y reanálisis) con su resultado y la línea de tiempo de estados.
Creá core/historial con consultas de solo lectura y un blueprint historial para paciente y
médico tratante. Un estudio ajeno responde 404, también en la descarga del resultado.
La descarga baja analisis.resultado_path de Storage; el PDF lo genera #20, así que en los tests
subí un PDF de prueba con el mock.
Chatbot sin contrato: creá integraciones/chatbot.py con preguntar(texto), mocks en
tests/fixtures/apis/chatbot/ y un borrador provisorio en docs/apis/chatbot.md. No guardes las
conversaciones. Si la API falla, mensaje legible.
Usá las fábricas de tests/fabricas.py para estudios en distintos estados.
Tests: paciente y médico con estudio propio y ajeno, Finalizado con y sin resultado, permisos de
otros roles, chatbot con respuesta, vacío y caído.
No toques core/estudios ni layout.html.
Control: pytest en verde; paciente@exoma.test ve su estudio y le pregunta al chatbot.
```
<!-- /issue:5 -->

## #6 · Presupuesto, pago particular y registro financiero

<!-- issue:6 -->
**Escenarios:** E13, E14, E41 · **Área:** presupuesto y pagos · **Puntos:** 5 · **Rama:** `6-presupuesto-pago` · **Depende de:** #3 · **Milestone:** Control 2 (24/11)

**Objetivo.** El administrativo emite el presupuesto, el paciente paga de forma particular y cada operación queda en el registro financiero para el tablero de control.

**Criterios de aceptación**

- E13.1 El administrativo consulta los estudios en estado Creado.
- E13.2 El sistema calcula el importe: 500 USD hasta 5 genes y 30 USD por cada gen adicional, con la extracción incluida.
- E13.3 El administrativo emite el presupuesto del estudio.
- E13.4 El sistema publica el presupuesto en la vista del paciente y cambia el estudio a Presupuestado.
- E13.5 El sistema notifica al paciente por mail y por aviso.
- E14.1 El paciente consulta el presupuesto del estudio.
- E14.2 El paciente elige pagar de forma particular.
- E14.3 Si tiene un cupón de descuento, el paciente realiza APLICAR CUPÓN (lo completa #12).
- E14.4 El paciente confirma el pago simulado por el importe final.
- E14.5 El sistema realiza REGISTRAR OPERACIÓN FINANCIERA.
- E14.6 El sistema cambia el estudio a Habilitado para turno y notifica al paciente.
- E41.1 El sistema registra cada pago particular con su importe, el paciente y la fecha.
- E41.2 El sistema registra el descuento aplicado con cada cupón (la función queda lista; la usa #12).
- E41.3 El sistema registra el importe que cubre la obra social al autorizarse la cobertura (la función queda lista; la usa #17).
- E41.4 El sistema conserva los registros para consultar la caja y la deuda por obra social y por paciente.

**Qué toca por capa**

- Migración: `obras_sociales`, `cupones`, `presupuestos`, `pagos`, `asientos_financieros`, con los `check` del modelo. Las pantallas de cupones y obras sociales son de #12 y #17.
- Core: `core/pagos` (`calcular_importe(cantidad_genes)`, `emitir_presupuesto`, `pagar_particular`); `core/finanzas` (`registrar_asiento(tipo, estudio, importe, pago=None, obra_social=None)`, `caja()`, `deuda_por_paciente()`, `deuda_por_obra_social()`).
- Controlador: `pagos`. Administrativo: `GET /presupuestos` (estudios en Creado), `POST /presupuestos/<estudio_id>`. Paciente: `GET /estudios/<id>/presupuesto`, `GET|POST /estudios/<id>/pago`.
- Vistas: `pagos/pendientes.html`, `pagos/presupuesto.html` (detalle y opción de pago), `pagos/pagar.html` (confirmación con el importe final). El presupuesto se publica en la vista del paciente con la entrada "Mi presupuesto" del menú y el link del aviso; no se edita `inicio/index.html`.
- Integración: ninguna (el pago es simulado).

**Cambios de estado y reglas**

- `creado` → `presupuestado` al emitir; `presupuestado` → `habilitado_turno` al pagar.
- Importe según los genes del análisis inicial; los de hallazgos secundarios no cuentan (O13). El precio es fijo: no hay forma de editarlo y hay un solo presupuesto por estudio.
- Pago único y sin cuotas: el importe que confirma el paciente tiene que ser igual al importe final. Un solo pago particular por estudio.
- Asientos: `presupuesto_emitido` al emitir y `pago_particular` al pagar. Solo se insertan. Pago, asiento y cambio de estado van en la misma transacción.
- Solo el paciente del estudio paga su presupuesto.

**Tests mínimos**

- `calcular_importe`: 1, 5, 6 y 10 genes → 500, 500, 530 y 650.
- Emitir: cambia a Presupuestado, crea el presupuesto y el asiento y avisa al paciente; emitir dos veces → error; estudio que no está en Creado → error.
- Pagar: crea el pago y el asiento, pasa a Habilitado para turno y avisa; importe distinto → rechazo y nada cambia; paciente ajeno → 404; administrativo → 403 en la ruta de pago.
- Finanzas: caja y deuda por paciente con datos de ejemplo; un asiento con importe 0 falla en la base.

**Fuera de alcance y supuestos:** cupón (#12), obra social (#17), el tablero (22/12) y el asiento `cobro_obra_social` (O16).

**Prompt de referencia**

```text
/implementar-escenario E13 E14 E41
Issue #6; la base (#3) está en develop. Leé el módulo usuarios como referencia, src/core/estudios
(sin modificarlo), y en @docs/modelo-datos.md las tablas presupuestos, pagos, cupones,
obras_sociales y asientos_financieros con sus check y las consultas del tablero (E41).
Migración: esas cinco tablas completas. cupones y obras_sociales van acá solo porque pagos y
asientos las referencian; no hagas sus pantallas (son de #12 y #17).
Core en core/pagos y core/finanzas. registrar_asiento() sirve para todos los tipos: #12 y #17 la
van a llamar. Dejá caja(), deuda_por_paciente() y deuda_por_obra_social() con tests, sin pantalla.
Reglas en código con test: 500 USD hasta 5 genes y 30 por gen adicional del análisis inicial (O13),
precio fijo, un presupuesto por estudio, pago único por el importe exacto, pago + asiento + cambio
de estado en una sola transacción.
Transiciones: creado → presupuestado y presupuestado → habilitado_turno.
Usá tests/fabricas.py para estudios en Creado con 1, 5, 6 y 10 genes.
Tests: importes, doble emisión, estado inválido, importe distinto, paciente ajeno y permisos.
No implementes el cupón: dejá pagar_particular sin ese parámetro; lo agrega #12.
Control: pytest en verde; administrativo@exoma.test emite el presupuesto del estudio de prueba y
paciente@exoma.test lo paga.
```
<!-- /issue:6 -->

## #7 · Turnos de extracción: reservar, cancelar y recordar

<!-- issue:7 -->
**Escenarios:** E19, E20, E21 · **Área:** turnos y logística · **Puntos:** 5 · **Rama:** `7-turnos-extraccion` · **Depende de:** #3 · **Milestone:** Control 2 (24/11)

**Objetivo.** El paciente elige un centro de extracción en el mapa, reserva un turno de 15 minutos, lo puede cancelar y recibe un recordatorio. Quedan tres piezas reutilizables: el mapa, la generación de PDFs y las tareas programadas.

**Criterios de aceptación**

- E19.1 El paciente consulta en un mapa los centros de extracción.
- E19.2 El paciente elige el centro de extracción que le queda más cerca.
- E19.3 El sistema muestra los turnos libres de ese centro.
- E19.4 El paciente reserva un turno libre.
- E19.5 El sistema cambia el estudio a Turno sacado.
- E19.6 El sistema envía al paciente la orden de extracción y el consentimiento informado.
- E20.1 El paciente consulta su turno de extracción.
- E20.2 El paciente cancela el turno.
- E20.3 El sistema libera el turno en el turnero del centro de extracción.
- E20.4 El sistema cambia el estudio a Habilitado para turno.
- E20.5 El paciente realiza RESERVAR TURNO DE EXTRACCIÓN cuando pueda asistir.
- E21.1 El sistema identifica los turnos de extracción próximos.
- E21.2 El sistema envía al paciente un recordatorio por mail con la fecha, la hora y el centro de extracción.
- E21.3 El sistema publica el recordatorio en la lista de avisos del paciente.

**Qué toca por capa**

- Migración: `feriados` (seeds con los feriados nacionales de 2026), `centros_extraccion` (seeds: unos 10 centros inventados en 3 provincias, con coordenadas y un `telegram_chat_id` de prueba, que usa `flask bot simular` de #8), `turnos_extraccion` con sus dos índices únicos parciales.
- Core: `core/turnos` (`franjas_libres(centro, desde, hasta)`, `reservar`, `cancelar`, `enviar_recordatorios(fecha)`); `core/centros` (listado con coordenadas).
- Controlador: `turnos` (paciente): `GET /turnos/centros`, `GET /turnos/centros/<id>/franjas`, `POST /turnos`, `GET /turnos/mio`, `POST /turnos/<id>/cancelar`, `GET /turnos/<id>/orden.pdf`, `GET /turnos/consentimiento.pdf`.
- Vistas: `turnos/centros.html` (mapa y lista de centros, que también sirve en el celular), `turnos/franjas.html`, `turnos/mio.html`; `pdf/orden_extraccion.html` (con el código del estudio, que el centro manda al bot en E22) y `pdf/consentimiento.html`; macro `mapa/_mapa.html` con Leaflet en `static/vendor/`.
- Piezas nuevas: `helpers/pdf.py` (xhtml2pdf desde Jinja) y `src/web/tareas.py` (APScheduler; no arranca en testing) con el job diario de recordatorios.
- Integración: ninguna API de compañeros; teselas de OpenStreetMap.

**Cambios de estado y reglas**

- `habilitado_turno` → `turno_sacado` y `requiere_nueva_extraccion` → `turno_sacado` al reservar; `turno_sacado` → `habilitado_turno` al cancelar.
- Franjas de 15 minutos, de lunes a viernes, desde las 9:00 y la última a las 17:45, fuera de `feriados` y nunca en el pasado.
- Un paciente por franja: el índice único es el que manda; si dos reservan a la vez, el segundo recibe "ese turno ya se reservó". Un turno vigente por estudio.
- Desde Requiere nueva extracción se reserva sin pagar de nuevo (E27).
- Cancelar solo antes del inicio del turno y sin costo.
- El recordatorio sale una vez por turno (`recordatorio_enviado_en`), el día hábil anterior (G4), por mail y como aviso.

**Tests mínimos**

- Franjas: no hay sábados, feriados, 18:00 ni franjas ocupadas.
- Reservar: cambia a Turno sacado y manda la orden y el consentimiento; con el estudio en Presupuestado → error; dos reservas de la misma franja → la segunda falla; segundo turno vigente → error; desde Requiere nueva extracción → funciona.
- Cancelar: vuelve a Habilitado para turno y libera la franja; turno ya pasado → error; paciente ajeno → 404.
- Recordatorios: salen para los turnos del día hábil siguiente y una sola vez.
- El médico tratante entra a `/turnos/centros` → 403.

**Fuera de alcance y supuestos:** la inasistencia (O7) va en #8; "el más cercano" lo elige el paciente en el mapa (el navegador puede centrarlo en su ubicación, sin guardarla); G4.

**Prompt de referencia**

```text
/implementar-escenario E19 E20 E21
Issue #7; la base (#3) está en develop. Leé el módulo usuarios como referencia, src/core/estudios
(sin modificarlo), notificar() y storage, y en @docs/modelo-datos.md las tablas feriados,
centros_extraccion y turnos_extraccion con sus índices parciales.
Migración: esas tres tablas; seeds con los feriados de 2026 y unos 10 centros inventados en 3
provincias con coordenadas.
Dejá tres piezas reutilizables, porque las usan otros issues sin modificarlas: el macro de mapa
con Leaflet servido en static/vendor (#18), helpers/pdf.py con xhtml2pdf (#20) y src/web/tareas.py
con APScheduler, que no arranca en testing (#8 y #13 le agregan jobs).
Reglas en código con test: franjas de 15 min, lunes a viernes de 9 a 18 (última 17:45), sin
feriados ni pasado; un paciente por franja (capturá el IntegrityError del índice); un turno vigente
por estudio; cancelar solo antes del inicio; recordatorio el día hábil anterior y una sola vez.
Transiciones: habilitado_turno y requiere_nueva_extraccion → turno_sacado; turno_sacado →
habilitado_turno al cancelar.
La orden de extracción es un PDF con fecha, hora, centro, indicaciones y el código del estudio.
Agregá a tests/fabricas.py centro y turno, y a DATOS_POR_ESTADO el turno de turno_sacado.
No toques layout.html: el CSS y el JS del mapa van en los bloques head y scripts.
Control: pytest en verde; el paciente de flask demo habilitado_turno reserva en el celular,
descarga la orden y cancela.
```
<!-- /issue:7 -->

## #8 · Toma de muestra por el bot e inasistencias

<!-- issue:8 -->
**Escenarios:** E22 (más el supuesto O7) · **Área:** turnos y logística · **Puntos:** 3 · **Rama:** `8-bot-toma-muestra` · **Depende de:** #7 · **Milestone:** Control 2 (24/11)

**Objetivo.** El centro de extracción avisa por Telegram que tomó la muestra y el estudio pasa solo a Listo para retirar, sin llamados. Si el paciente no fue, el turno se libera al cierre del día.

**Criterios de aceptación**

- E22.1 El paciente presenta la orden de extracción (fuera del sistema; la orden de #7 lleva el código del estudio).
- E22.2 El paciente entrega el consentimiento informado firmado (fuera del sistema; no se guarda).
- E22.3 El centro de extracción toma la muestra de sangre (fuera del sistema).
- E22.4 El centro de extracción envía el mensaje de muestra tomada al bot de mensajería.
- E22.5 El sistema cambia el estudio a Listo para retirar.
- E22.6 El sistema incluye el centro de extracción en la próxima orden del día de su provincia (consulta `centros_con_muestras_listas(provincia)`, que usa #13).
- O7: al cierre del día del turno, si no llegó el mensaje, el turno queda `ausente`, el estudio vuelve a Habilitado para turno y el paciente recibe un aviso.

**Qué toca por capa**

- Migración: `mensajes_bot`, `ordenes_del_dia`, `paradas_orden_del_dia`, `sample_sets` y `muestras`. Solo las tablas y sus modelos (`core/logistica/modelos.py`, `core/sample_sets/modelos.py`); la lógica de las tres del medio es de #13 y #14.
- Core: `core/muestras` (modelos `Muestra` y `MensajeBot`, `registrar_toma(update)`, `centros_con_muestras_listas(provincia)`, `procesar_inasistencias(fecha)`).
- Controlador: `bot`. `POST /bot/telegram`: sin sesión, exento de CSRF, valida el header `X-Telegram-Bot-Api-Secret-Token`. Administrativo: `GET /bot/mensajes` (mensajes recibidos y los que no se pudieron procesar).
- Vistas: `bot/mensajes.html`.
- Integración: Telegram Bot API (webhook). `integraciones/telegram.py` responde al centro con `sendMessage` y tiene mock. Comando `flask bot simular <chat_id> <texto>` para probar sin Telegram. Borrador del formato del mensaje en `docs/apis/telegram.md` (**formato pendiente** de acordar). Variables nuevas en `.env.example`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`.
- Tareas: job diario de inasistencias a las 18:30 en `tareas.py`.

**Cambios de estado y reglas**

- `turno_sacado` → `listo_para_retirar` al procesar el mensaje; `turno_sacado` → `habilitado_turno` por inasistencia.
- `telegram_update_id` único: un mensaje repetido no hace nada.
- Chat que no es de un centro, código inexistente, estudio que no está en Turno sacado o turno de otro centro: se guarda el error en `mensajes_bot.error` y no cambia nada. El webhook responde 200 igual, para que Telegram no reintente.
- Al procesar: se crea la muestra con `turno_id` y `tomada_en`, y el turno pasa a `asistido`.
- Sin el secreto correcto, el webhook responde 403 y no guarda nada.

**Tests mínimos**

- Mensaje válido → muestra, turno `asistido`, estudio Listo para retirar; repetido → sin cambios.
- Chat desconocido, código desconocido, estudio en otro estado y turno de otro centro → error guardado y sin cambios.
- Sin el header secreto → 403.
- `centros_con_muestras_listas` devuelve el centro con la muestra nueva.
- Inasistencia: turno de hoy sin muestra → `ausente`, Habilitado para turno y aviso; turno con muestra → no se toca.
- El administrativo ve los mensajes con error; el paciente entra a `/bot/mensajes` → 403.

**Fuera de alcance y supuestos:** crear el bot en Telegram y registrar el webhook es parte del deploy (consulta); O7.

**Prompt de referencia**

```text
/implementar-escenario E22
Issue #8; #7 (turnos) ya está en develop. Leé src/core/turnos, src/web/tareas.py, el módulo
usuarios como referencia y en @docs/modelo-datos.md las tablas mensajes_bot, muestras,
ordenes_del_dia, paradas_orden_del_dia y sample_sets.
Migración: esas cinco tablas completas. De ordenes_del_dia, paradas y sample_sets hacé solo los
modelos (core/logistica/modelos.py y core/sample_sets/modelos.py): su lógica es de #13 y #14.
El webhook POST /bot/telegram es una ruta sin sesión: eximila de CSRF y validá el header
X-Telegram-Bot-Api-Secret-Token contra TELEGRAM_WEBHOOK_SECRET (agregala a .env.example).
Guardá cada update en mensajes_bot (update_id único) y respondé 200 aunque haya error.
El formato del mensaje no está acordado: asumí que trae el código del estudio (EX-AAAA-NNNNN) y
dejalo en un borrador provisorio en docs/apis/telegram.md. Agregá flask bot simular.
Transiciones: turno_sacado → listo_para_retirar; y por inasistencia (O7 de @docs/decisiones.md),
turno_sacado → habilitado_turno con un job a las 18:30 en tareas.py.
Dejá centros_con_muestras_listas(provincia) en core/muestras (la usa #13), las fábricas de muestra
y mensaje en tests/fabricas.py y la muestra de listo_para_retirar en DATOS_POR_ESTADO.
Tests: válido, repetido, chat desconocido, código desconocido, estado inválido, otro centro, sin
secreto, inasistencia con y sin muestra, y permisos de /bot/mensajes.
Control: pytest en verde; con flask demo turno_sacado y flask bot simular, ese estudio pasa a Listo
para retirar y administrativo@exoma.test ve el mensaje. Solo tocás core/turnos para asistido/ausente.
```
<!-- /issue:8 -->

## #9 · Registro de médicos y del personal del laboratorio

<!-- issue:9 -->
**Escenarios:** E01, E02 · **Área:** acceso y alta clínica · **Puntos:** 3 · **Rama:** `9-registro-usuarios` · **Depende de:** #4 · **Milestone:** Control 3 (1/12)

**Objetivo.** Médicos tratantes, gerentes médicos, administrativos y bioinformáticos se registran solos y entran con su rol, como alternativa al alta por el administrador (E03).

**Criterios de aceptación**

- E01.1 El médico tratante o el gerente médico completa matrícula, nombre, apellido, teléfono y mail.
- E01.2 El médico tratante o el gerente médico selecciona sus especialidades desde el módulo SNOMED.
- E01.3 El médico tratante o el gerente médico indica su rol.
- E01.4 El sistema crea las credenciales de acceso con el rol indicado.
- E02.1 El administrativo o el bioinformático completa nombre, apellido, teléfono y mail.
- E02.2 El administrativo o el bioinformático indica su rol.
- E02.3 El sistema crea las credenciales de acceso con el rol indicado.
- E02.4 Si el rol es bioinformático, el sistema lo agrega a los destinatarios de las notificaciones de datos crudos (por el modelo, son todos los bioinformáticos activos: `listar_activos_por_rol`).

**Qué toca por capa**

- Migración: `medico_especialidades`.
- Core: `core/usuarios/registro.py` (`registrar_medico`, `registrar_personal`) y `core/usuarios/especialidades.py` (modelo `MedicoEspecialidad` y `guardar_especialidades(medico, codigos)`, que llaman el registro y el alta de E03 desde `controllers/usuarios.py`). No modifica `modelos.py` ni `servicios.py`: usa `crear_usuario` y `crear_perfil_medico`.
- Controlador: `registro`, rutas públicas como el login: `GET|POST /registro/medico`, `GET|POST /registro/laboratorio`, `GET /registro/especialidades?q=` (JSON, usa el cliente SNOMED de #4 con tipo especialidad). Además, el alta de E03 suma las especialidades para médicos y gerentes.
- Vistas: `registro/medico.html`, `registro/laboratorio.html` (usan el macro del buscador de #4 con la URL pública y el tipo `especialidad`); enlace "Registrarse" en `login.html` (único cambio en auth).
- Integración: SNOMED (cliente de #4, sin modificarlo).

**Cambios de estado y reglas**

- Sin cambios de estado.
- E01 solo acepta `medico_tratante` y `gerente_medico`; E02 solo `administrativo` y `bioinformatico`. Cualquier otro rol en el POST → 400 (no se puede auto registrar un administrador general, un paciente ni un transportista).
- La persona elige su contraseña (al menos 8 caracteres, con confirmación) (G1).
- Mail único sin distinguir mayúsculas; matrícula única; al menos una especialidad; teléfono obligatorio.
- Un usuario con sesión iniciada que entra a `/registro` vuelve al inicio.

**Tests mínimos**

- Registro de un médico con dos especialidades → usuario, perfil, especialidades e inicio de sesión correcto; lo mismo para un gerente.
- Rol `administrador_general` en el POST → 400.
- Mail repetido con otras mayúsculas, matrícula repetida o sin especialidades → error y nada creado.
- Registro de un bioinformático → aparece en `listar_activos_por_rol('bioinformatico')`; registro de un administrativo.
- SNOMED caído en el buscador público → mensaje legible.
- Alta de E03 con especialidades.

**Fuera de alcance y supuestos:** aprobación de cuentas (consulta: cualquiera puede registrarse como gerente médico o administrativo); bajas y modificación (restricción de E03); G1.

**Prompt de referencia**

```text
/implementar-escenario E01 E02
Issue #9; #4 (SNOMED) ya está en develop. Leé el módulo usuarios (core, controlador y vistas de
E03), helpers/auth.py y el login, integraciones/snomed.py y el macro snomed/_buscador.html, y la
tabla medico_especialidades de @docs/modelo-datos.md.
Migración: medico_especialidades. El modelo va en core/usuarios/especialidades.py y la lógica en
core/usuarios/registro.py: no modifiques modelos.py ni servicios.py, que en este milestone toca #10.
Las rutas de /registro son públicas como el login (sin login_required); explicalo en un comentario.
Para las especialidades hacé un endpoint público GET /registro/especialidades que use el cliente
SNOMED con tipo especialidad; no cambies el endpoint de #4.
Reglas con test: E01 solo médico tratante o gerente médico y E02 solo administrativo o
bioinformático (otro rol → 400); contraseña elegida por la persona (G1 de @docs/guia-issues.md);
mail y matrícula únicos; al menos una especialidad.
E02.4: no hay tabla de destinatarios; probá que el bioinformático registrado aparece en
listar_activos_por_rol.
Sumá las especialidades al alta de E03 con guardar_especialidades desde controllers/usuarios.py (no
en servicios.py) y un enlace "Registrarse" en login.html: es el único cambio permitido en auth.
Control: pytest en verde; en el navegador, sin sesión, registrá un médico con dos especialidades y
entrá con él.
```
<!-- /issue:9 -->

## #10 · Alta de paciente y familiograma

<!-- issue:10 -->
**Escenarios:** E06, E09 · **Área:** acceso y alta clínica · **Puntos:** 5 · **Rama:** `10-alta-paciente` · **Depende de:** #4 · **Milestone:** Control 3 (1/12)

**Objetivo.** El médico tratante registra al paciente en la misma consulta, con su diagnóstico presuntivo validado, sus síntomas, el resumen de historia clínica dictado y, si hay, sus familiares y el familiograma.

**Criterios de aceptación**

- E06.1 El médico tratante carga DNI, nombre, apellido, fecha de nacimiento, teléfono y mail del paciente.
- E06.2 El médico tratante registra el diagnóstico presuntivo, con una o más patologías lisosomales, y el tipo de sospecha.
- E06.3 El médico tratante graba el resumen de historia clínica y el sistema lo transcribe a texto.
- E06.4 El médico tratante carga la lista de síntomas del paciente mediante BUSCAR SÍNTOMA.
- E06.5 Si el paciente informa familiares, el médico tratante realiza REGISTRAR FAMILIOGRAMA.
- E06.6 El sistema realiza VALIDAR DIAGNÓSTICO PRESUNTIVO y, si es válido, envía las credenciales de acceso al paciente.
- E09.1 El médico tratante da de alta un familiar con su parentesco y su nombre.
- E09.2 El médico tratante carga los síntomas del familiar mediante BUSCAR SÍNTOMA.
- E09.3 El médico tratante indica si el familiar tiene diagnóstico de alguna patología lisosomal.
- E09.4 El médico tratante repite los episodios anteriores por cada familiar.
- E09.5 El sistema envía los familiares a la API de familiograma.
- E09.6 El sistema asocia al paciente el familiograma en PDF devuelto.

**Qué toca por capa**

- Migración: `usuarios.debe_cambiar_contrasena`, `paciente_sintomas`, `diagnosticos_presuntivos`, `familiares`, `familiar_sintomas`, `familiar_patologias`.
- Core: `core/pacientes` (`dar_de_alta(...)` en una transacción: valida con E08 de #4, crea el usuario paciente con contraseña provisoria y `debe_cambiar_contrasena`, el paciente, síntomas, diagnóstico y familiares; después del commit pide el familiograma y manda el mail; `pacientes_del_medico(busqueda)`; `reintentar_familiograma`). Agrega la columna nueva al modelo `Usuario`.
- Controlador: `pacientes` (médico tratante): `GET /pacientes`, `GET|POST /pacientes/nuevo`, `POST /pacientes/transcribir` (fetch con el audio), `GET /pacientes/<id>`, `POST /pacientes/<id>/familiograma`, `GET /pacientes/<id>/familiograma.pdf`.
- Vistas: `pacientes/listado.html` ("Mis pacientes", con búsqueda por DNI o nombre y el botón de alta), `pacientes/formulario.html` (datos, diagnóstico con las patologías activas, tipo de sospecha, grabación con MediaRecorder y texto editable, buscador de síntomas de #4, familiares que se agregan en la misma página), `pacientes/detalle.html`, `mails/credenciales_paciente.html`.
- Integraciones: `integraciones/transcripcion.py` (`transcribir(audio)`) y `integraciones/familiograma.py` (`generar(familiares)` → PDF), las dos con **contrato pendiente** (mocks y borradores en `docs/apis/`); Storage para el audio y el PDF.

**Cambios de estado y reglas**

- Sin cambios de estado: el estudio lo da de alta #11.
- Todos los datos son obligatorios salvo el familiograma. DNI único (7 u 8 dígitos, sin puntos); fecha de nacimiento no futura; mail único (O10); al menos una patología activa; tipo de sospecha `clinica` o `familiar`.
- Si E08 rechaza: no se guarda nada y el formulario vuelve con los datos cargados y la inconsistencia (E08.5 y E08.6).
- Si la transcripción falla, el médico escribe el resumen; el texto es obligatorio.
- Si la API de familiograma falla, el alta queda guardada sin PDF y el detalle ofrece reintentarlo (G3).
- La contraseña provisoria va solo en el mail: nunca en el aviso ni en los logs.

**Tests mínimos**

- Alta completa → usuario paciente con `debe_cambiar_contrasena`, paciente, síntomas, diagnóstico y mail con las credenciales.
- Validación rechazada → no se crea nada y se muestra la inconsistencia; sospecha familiar con un familiar diagnosticado y sin síntomas → acepta.
- DNI repetido, mail repetido o sin resumen → error.
- Con familiares → la API recibe parentesco, nombre, síntomas y diagnóstico, y el PDF queda guardado; API caída → alta guardada sin PDF; el reintento lo genera.
- Transcripción con mock.
- El médico ve solo sus pacientes (otro → 404); el administrativo entra a `/pacientes` → 403.

**Fuera de alcance y supuestos:** el responsable del menor usa la cuenta del paciente (LEL); modificar datos (restricción de E03); O2, O10, G3.

**Prompt de referencia**

```text
/implementar-escenario E06 E09
Issue #10; #4 ya está en develop. Leé core/patologias (validar_diagnostico_presuntivo), el macro
snomed/_buscador.html, src/core/pacientes y src/core/usuarios, storage.py y en
@docs/modelo-datos.md las tablas pacientes, paciente_sintomas, diagnosticos_presuntivos,
familiares, familiar_sintomas, familiar_patologias y la columna usuarios.debe_cambiar_contrasena.
Migración: esas cinco tablas y la columna; sos el único issue del milestone que toca modelos.py.
dar_de_alta va en una transacción: valida con E08 (si rechaza, no guarda nada y el formulario vuelve
con los datos y la inconsistencia) y crea usuario con contraseña provisoria, paciente, síntomas,
diagnóstico y familiares. Después del commit: familiograma y mail con credenciales.
Transcripción y familiograma sin contrato: integraciones/transcripcion.py y familiograma.py con
mocks y borradores provisorios en docs/apis/. Si falla la transcripción, el médico escribe el
texto; si falla el familiograma, el alta se guarda y se reintenta (G3 de @docs/guia-issues.md).
El audio se graba en el navegador (MediaRecorder) y va por fetch con X-CSRFToken.
Reglas con test: todo obligatorio salvo el familiograma; DNI y mail únicos (O10); al menos una
patología activa; la contraseña provisoria nunca en avisos ni logs.
Tests: alta completa, rechazo de E08, sospecha familiar, duplicados, familiograma ok, caído y
reintento, médico ajeno y permisos. No toques core/patologias ni el buscador de #4.
Control: pytest en verde; medico@exoma.test da de alta desde el celular un paciente con dos
familiares y el mail con las credenciales sale por consola.
```
<!-- /issue:10 -->

## #11 · Alta de estudio con genes de Apigen

<!-- issue:11 -->
**Escenarios:** E10 · **Área:** acceso y alta clínica · **Puntos:** 3 · **Rama:** `11-alta-estudio` · **Depende de:** #10 · **Milestone:** Control 3 (1/12)

**Objetivo.** El médico tratante inicia el circuito del exoma para un paciente: el estudio queda Creado, con los genes que devuelve Apigen para el diagnóstico presuntivo y los que agrega a mano.

**Criterios de aceptación**

- E10.1 El médico tratante selecciona al paciente; si no existe, realiza DAR DE ALTA PACIENTE (botón hacia el alta de #10).
- E10.2 El sistema obtiene de la API de bioinformática los genes asociados al diagnóstico presuntivo.
- E10.3 Si sospecha otra causa, el médico tratante agrega genes manualmente.
- E10.4 El médico tratante indica si el estudio evalúa hallazgos secundarios.
- E10.5 El sistema registra el estudio en estado Creado y avisa al administrativo para emitir el presupuesto.

**Qué toca por capa**

- Migración: `analisis_patologias`.
- Core: `core/estudios/alta.py` (`genes_para(patologias)` con el endpoint 3, que también usa #21; `dar_de_alta_estudio(paciente, medico, genes_a_mano, evalua_hallazgos)`). Envuelve `crear_estudio()` de la base, que ya genera el código, el análisis inicial, `analisis_genes` y la primera fila del historial: este issue calcula `pompe_urgente`, pide los genes a Apigen, copia el diagnóstico en `analisis_patologias` y avisa. No modifica `estados.py` ni `servicios.py`.
- Controlador: `estudios` (médico tratante): `GET /pacientes/<id>/estudio/nuevo`, `POST /pacientes/<id>/estudio`, `GET /estudios/genes?q=` (endpoint 1 de Apigen, para los genes a mano).
- Vistas: `estudios/nuevo.html` (genes de Apigen como lista fija, genes a mano con buscador, casilla de hallazgos secundarios); botón "Dar de alta estudio" en la ficha y en "Mis pacientes" de #10.
- Integración: Apigen, endpoints 1 y 3 (ya están en el cliente).

**Cambios de estado y reglas**

- Alta → `creado`, con la primera fila del historial (la registra `crear_estudio()`).
- Solo un estudio por paciente (O20): si ya tiene uno, se muestra ese y se ofrece el reanálisis (#21).
- Pompe urgente: POMPE en el diagnóstico y paciente menor de 4 meses al dar de alta el estudio (O14).
- Genes sin repetir; un gen agregado a mano tiene que existir en Apigen y queda con `agregado_a_mano`.
- Si Apigen falla, no se crea nada y se muestra el error.
- El aviso va a todos los administrativos activos.

**Tests mínimos**

- Alta con FABRY → gen GLA, análisis inicial, `analisis_patologias`, historial y aviso a los administrativos.
- Gen a mano marcado `agregado_a_mano`; gen repetido no se duplica; gen inexistente → error.
- Pompe con 3 meses → urgente; Pompe con 5 meses → no; Fabry con 1 mes → no.
- Segundo estudio del mismo paciente → rechazo.
- Apigen caído → nada creado.
- Paciente de otro médico → 404; gerente médico → 403.

**Fuera de alcance y supuestos:** el presupuesto (#6) y el reanálisis (#21); O13, O14, O20.

**Prompt de referencia**

```text
/implementar-escenario E10
Issue #11; #10 (alta de paciente) ya está en develop. Leé src/core/estudios (modelos y
crear_estudio() de servicios.py, sin modificarlos), src/core/pacientes, controllers/pacientes.py,
integraciones/apigen.py, apigen/contrato.md (endpoints 1 y 3) y en @docs/modelo-datos.md las tablas
estudios, analisis, analisis_genes y analisis_patologias.
Migración: solo analisis_patologias.
La lógica va en core/estudios/alta.py. Dejá genes_para(patologias) como función aparte: #21 la
reutiliza en el reanálisis.
Reglas con test: un estudio por paciente (O20); Pompe urgente si hay POMPE y el paciente tiene
menos de 4 meses al dar de alta (O14); genes sin repetir; gen a mano que exista en Apigen y quede
agregado_a_mano; si Apigen falla, no se crea nada.
dar_de_alta_estudio envuelve crear_estudio(): no insertes el estudio ni el historial a mano. Avisa
a todos los administrativos activos.
El punto de entrada es la ficha del paciente y "Mis pacientes" de #10: agregá ahí el botón "Dar de
alta estudio"; si el paciente no está, el botón de alta de #10 ya existe.
Tests: FABRY, gen a mano, repetido, inexistente, los tres casos de Pompe, segundo estudio, Apigen
caído y permisos.
Control: pytest en verde; medico@exoma.test da de alta un estudio para un paciente nuevo de #10
(el de los seeds ya tiene uno, O20) y administrativo@exoma.test recibe el aviso.
```
<!-- /issue:11 -->

## #12 · Cupones de descuento

<!-- issue:12 -->
**Escenarios:** E15, E37, E38 (y completa E14.3) · **Área:** gestión médica · **Puntos:** 5 · **Rama:** `12-cupones` · **Depende de:** #6 · **Milestone:** Control 3 (1/12)

**Objetivo.** El gerente médico genera cupones y los reparte entre los médicos tratantes; cada médico decide a qué paciente beneficiar, y el paciente lo usa al pagar.

**Criterios de aceptación**

- E37.1 El gerente médico define el descuento y la cantidad de cupones.
- E37.2 El sistema solicita los cupones al módulo de cupones.
- E37.3 El sistema recibe los cupones en PDF, con código QR o código numérico.
- E37.4 El gerente médico asigna los cupones a un médico tratante.
- E37.5 El sistema notifica al médico tratante los cupones recibidos.
- E38.1 El médico tratante consulta sus cupones disponibles.
- E38.2 El médico tratante elige un cupón y un paciente.
- E38.3 El médico tratante asigna el cupón al paciente.
- E38.4 El sistema envía una notificación al paciente.
- E38.5 El sistema deja el cupón disponible en la vista del paciente.
- E14.3 (de #6) Si tiene un cupón de descuento, el paciente realiza APLICAR CUPÓN.
- E41.2 (de #6) El sistema registra el descuento aplicado con cada cupón de descuento.
- E15.1 El paciente sube el PDF del cupón o ingresa su código.
- E15.2 El sistema consulta al módulo de cupones si el cupón está vigente.
- E15.3 Si el cupón no está vigente, el sistema lo rechaza.
- E15.4 Si rechaza el cupón, el sistema informa el rechazo al paciente.
- E15.5 Si el cupón está vigente, el sistema aplica el descuento al presupuesto.
- E15.6 Si se confirma el pago, el sistema informa al módulo de cupones el uso del cupón para que lo venza.

**Qué toca por capa**

- Migración: ninguna (`cupones` la creó #6).
- Core: `core/cupones` (`generar(gerente, descuento, cantidad, medico)`, `disponibles_del_medico`, `asignar_a_paciente`, `validar_para(codigo, paciente)`); `core/pagos.pagar_particular` suma el cupón opcional: descuento, `pagos.cupon_id` y `descuento_usd`, asiento `descuento_cupon` y cupón `utilizado`.
- Controlador: `cupones`. Gerente médico: `GET /cupones`, `GET|POST /cupones/generar`. Médico tratante: `GET /mis-cupones`, `POST /mis-cupones/<id>/asignar`. Paciente: `GET /cupones/mios`, `GET /cupones/<id>/pdf`. En la ruta de pago de #6, el campo del código o del PDF.
- Vistas: `cupones/listado.html`, `cupones/generar.html`, `cupones/del_medico.html`, `cupones/del_paciente.html`; cambio en `pagos/pagar.html`.
- Dependencia nueva: `pypdf` con `poetry add`, para leer el código del PDF (G7). Es el único issue que cambia `pyproject.toml`.
- Integración: `integraciones/cupones.py` con `generar(descuento, cantidad)`, `consultar(codigo)` y `vencer(codigo)` (**contrato pendiente**: mock y `docs/apis/cupones.md`); Storage para los PDF.

**Cambios de estado y reglas**

- No cambia el estado del estudio. El cupón pasa de `vigente` a `utilizado`.
- Descuento en porcentaje, de 1 a 100 (O15). El médico solo asigna cupones suyos, vigentes y sin paciente, y solo a sus pacientes. El paciente solo usa un cupón asignado a él. Un cupón por pago.
- El descuento se calcula sobre el total del presupuesto y solo en el pago particular (G6).
- El cupón se vence en el módulo dentro de la transacción del pago, antes del commit: si el módulo falla, no se registra el pago.
- PDF subido: se lee el código del texto del PDF; si no se puede, se pide escribirlo (G7).

**Tests mínimos**

- Generar 3 → 3 cupones asignados al médico y aviso al médico; un médico tratante entra a `/cupones/generar` → 403.
- Asignar a un paciente propio → aviso y el cupón aparece en su vista; paciente de otro médico, cupón de otro médico o ya asignado → error.
- Aplicar uno vigente → importe con descuento; vencido según el módulo o de otro paciente → rechazo con mensaje.
- Pagar con cupón → pago con `cupon_id` y descuento, asientos `pago_particular` y `descuento_cupon`, cupón `utilizado` y módulo llamado para vencerlo; módulo caído al vencer → no hay pago; segundo uso → rechazo.

**Fuera de alcance y supuestos:** O15, G6, G7.

**Prompt de referencia**

```text
/implementar-escenario E37 E38 E15
Issue #12; #6 (pagos) ya está en develop. Leé core/pagos, core/finanzas, controllers/pagos.py y
pagos/pagar.html, la tabla cupones de @docs/modelo-datos.md y O15 de @docs/decisiones.md.
Sin migración: cupones ya existe.
El módulo de cupones no tiene contrato: creá integraciones/cupones.py con generar, consultar y
vencer, mocks en tests/fixtures/apis/cupones/ y un borrador provisorio en docs/apis/cupones.md.
Los PDF van a Storage.
Agregá a pagar_particular un cupón opcional; es el único cambio en core/pagos: registrá el descuento
en el pago y el asiento descuento_cupon con registrar_asiento(). El vencimiento en el módulo va
dentro de la transacción, antes del commit: si falla, no hay pago.
Reglas con test: porcentaje de 1 a 100; el médico asigna solo sus cupones vigentes y sin paciente,
a sus pacientes; el paciente usa solo el suyo; un cupón por pago; solo en el pago particular del
total (G6). Para el PDF subido, leé el código del texto y si no se puede pedilo a mano (G7).
Tests: generación y aviso, asignación propia y ajena, cupón vencido, de otro paciente, pago con
cupón, módulo caído al vencer y segundo uso.
No cambies el resto de core/pagos ni las rutas de presupuesto: las modifica #17.
Control: pytest en verde; gerente@exoma.test genera cupones para medico@exoma.test, que le asigna
uno al paciente de flask demo presupuestado, y ese paciente paga con descuento.
```
<!-- /issue:12 -->

## #13 · Orden del día y retiro de muestras

<!-- issue:13 -->
**Escenarios:** E23, E24 · **Área:** turnos y logística · **Puntos:** 5 · **Rama:** `13-orden-del-dia` · **Depende de:** #8 · **Milestone:** Control 3 (1/12)

**Objetivo.** Cada mañana hábil, cada transportista recibe la lista de centros a visitar en un orden fijo, y al retirar en cada centro las muestras pasan a En camino al laboratorio central.

**Criterios de aceptación**

- E23.1 El sistema reúne, por provincia, los centros de extracción con estudios Listo para retirar.
- E23.2 El sistema envía las direcciones de esos centros al módulo de optimización de recorridos.
- E23.3 El sistema recibe el orden del recorrido.
- E23.4 El sistema asigna la orden del día al transportista de la provincia.
- E23.5 El transportista recibe la orden del día (aviso y mail).
- E24.1 El transportista llega al siguiente centro de extracción de la orden del día.
- E24.2 El centro de extracción entrega las muestras al transportista (fuera del sistema).
- E24.3 El transportista registra el retiro de las muestras.
- E24.4 El sistema cambia esos estudios a En camino al laboratorio central.
- E24.5 El transportista repite los episodios en cada centro hasta completar la orden del día.

**Qué toca por capa**

- Migración: ninguna (tablas de #8).
- Core: `core/logistica` (`generar_ordenes(fecha)`, `orden_de_hoy(transportista)`, `registrar_retiro(parada, transportista)`). Usa `centros_con_muestras_listas` de #8.
- Controlador: `logistica`. Transportista: `GET /orden-del-dia`, `POST /orden-del-dia/paradas/<posicion>/retiro`. Administrativo: `GET /ordenes-del-dia?fecha=`, `POST /ordenes-del-dia/generar` (regenerar a mano).
- Vistas: `logistica/orden_del_dia.html` (pensada para el celular: centro, dirección y botón de retiro por parada), `logistica/ordenes.html`.
- Integración: `integraciones/optimizacion.py` con `ordenar(centros)`, que recibe la dirección y las coordenadas de cada centro y devuelve el orden (**contrato pendiente**: mock que ordena por cercanía; `docs/apis/optimizacion.md`).
- Tareas: job de lunes a viernes a las 7:00 en `tareas.py`, que no corre en feriados.

**Cambios de estado y reglas**

- `listo_para_retirar` → `en_camino_laboratorio` al registrar el retiro en un centro.
- Una orden por transportista y fecha: generar dos veces no duplica.
- No se genera en sábados, domingos ni feriados.
- Provincia con muestras y sin transportista → aviso a los administrativos.
- El orden lo da el módulo y no se puede cambiar: solo se puede registrar el retiro de la siguiente parada pendiente.
- El retiro se lleva todas las muestras Listo para retirar del centro (G10) y les carga `orden_del_dia_id`.
- Si el módulo falla, no se genera la orden y se avisa a los administrativos, que la regeneran (G5).
- Solo el transportista de la orden registra sus retiros.

**Tests mínimos**

- Una orden por provincia con muestras, y ninguna en una provincia sin muestras.
- Sábado y feriado → no genera; segunda corrida → no duplica.
- Con un mock que invierte el orden, las paradas respetan el orden del módulo.
- Módulo caído → sin orden y aviso.
- Retiro en orden → paradas y estudios actualizados; fuera de orden → error; de otro transportista → 404.
- El paciente entra a `/orden-del-dia` → 403.

**Fuera de alcance y supuestos:** la ubicación del transportista y la llegada al laboratorio (#18); G5, G10.

**Prompt de referencia**

```text
/implementar-escenario E23 E24
Issue #13; #8 ya está en develop. Leé core/muestras (centros_con_muestras_listas),
core/logistica/modelos.py, src/web/tareas.py, el modelo Transportista y en @docs/modelo-datos.md
las tablas ordenes_del_dia, paradas_orden_del_dia y muestras.
Sin migración: las tablas las creó #8.
El módulo de optimización no tiene contrato: creá integraciones/optimizacion.py con
ordenar(centros) (dirección y coordenadas), un mock que ordena por cercanía y un borrador provisorio en
docs/apis/optimizacion.md.
Agregá en tareas.py un job de lunes a viernes a las 7:00 que no corra en feriados; generar_ordenes
también se puede llamar a mano desde la pantalla del administrativo.
Reglas con test: una orden por transportista y fecha; nada en fin de semana ni feriado; aviso si una
provincia no tiene transportista; orden fijo (solo la siguiente parada); el retiro se lleva todas
las muestras listas del centro (G10); si el módulo falla, no hay orden y se avisa (G5).
Transición: listo_para_retirar → en_camino_laboratorio.
La pantalla del transportista se usa en el celular.
Tests: generación por provincia, sin muestras, sábado, feriado, sin duplicar, orden del módulo,
módulo caído, retiro en orden, fuera de orden, de otro transportista y permisos.
No toques core/muestras ni core/sample_sets.
Control: pytest en verde; con flask demo listo_para_retirar, administrativo@exoma.test genera la
orden y transportista@exoma.test registra el retiro desde el celular.
```
<!-- /issue:13 -->

## #14 · Sample set y autorización ministerial

<!-- issue:14 -->
**Escenarios:** E28, E29 · **Área:** envío a Corea · **Puntos:** 5 · **Rama:** `14-sample-set` · **Depende de:** #8 · **Milestone:** Control 3 (1/12)

**Objetivo.** Las muestras válidas se juntan en paquetes de 10 (o menos si hay un Pompe urgente) y el Ministerio de Salud autoriza su salida con el CCB.

**Criterios de aceptación**

- E28.1 El sistema agrega cada muestra En laboratorio central al sample set en armado (`agregar_muestra`, que llama #18 cuando el volumen es válido).
- E28.2 El sistema identifica como Pompe urgente todo estudio con diagnóstico presuntivo de Pompe en un paciente menor de 4 meses (la marca `pompe_urgente` que calcula #11).
- E28.3 Si el sample set llega a 10 muestras, el sistema lo cierra.
- E28.4 Si el sample set contiene un Pompe urgente, el sistema lo cierra aunque esté incompleto.
- E28.5 El sistema cambia los estudios del sample set cerrado a Pendiente de autorización ministerial.
- E28.6 El sistema realiza SOLICITAR AUTORIZACIÓN MINISTERIAL.
- E29.1 El sistema genera el CCB con los pacientes del sample set.
- E29.2 El sistema envía el CCB a la API del Ministerio de Salud.
- E29.3 El Ministerio de Salud devuelve el PDF de autorización.
- E29.4 El sistema asocia el CCB y el PDF de autorización a cada estudio del sample set.
- E29.5 El sistema cambia el sample set a Pendiente de retiro y sus estudios a Pendiente de envío.
- E29.6 El sistema avisa al administrativo que el sample set está listo para programar el retiro.

**Qué toca por capa**

- Migración: ninguna (tablas de #8).
- Core: `core/sample_sets` (`agregar_muestra(muestra)`, `cerrar`, `solicitar_autorizacion`, `generar_ccb` con openpyxl). `agregar_muestra` trabaja dentro de la transacción de quien la llama y devuelve el sample set si lo cerró; quien la llama hace commit y recién después llama a `solicitar_autorizacion`, para que la llamada al Ministerio no quede dentro de una transacción que después se revierte.
- Tests y demo: fábrica de sample set en `tests/fabricas.py` y las entradas de `pendiente_autorizacion_ministerial` y `pendiente_envio` en `DATOS_POR_ESTADO`.
- Controlador: `sample_sets` (administrativo): `GET /sample-sets`, `GET /sample-sets/<id>`, `GET /sample-sets/<id>/ccb.xlsx`, `GET /sample-sets/<id>/autorizacion.pdf`, `POST /sample-sets/<id>/autorizacion` (reintentar).
- Vistas: `sample_sets/listado.html` (estado, cantidad de muestras, si tiene un Pompe urgente), `sample_sets/detalle.html`.
- Integración: `integraciones/ministerio.py` con `autorizar(ccb)` → PDF (**contrato pendiente**: mock y `docs/apis/ministerio.md`); Storage para el CCB y el PDF.

**Cambios de estado y reglas**

- Estudio: `en_laboratorio_central` → `pendiente_autorizacion_ministerial` al cerrar; → `pendiente_envio` al llegar el PDF. Sample set: `en_armado` → `cerrado` → `pendiente_retiro`.
- Un solo sample set en armado (índice de la base); máximo 10 muestras; un sample set cerrado no admite más (la siguiente muestra abre uno nuevo).
- Cierra al llegar a 10 o en cuanto contiene un Pompe urgente.
- Solo entran muestras con volumen registrado, que no son insuficientes y que no están en otro sample set.
- El CCB tiene una fila por estudio: código, DNI, nombre, apellido y fecha de nacimiento.
- Si el Ministerio falla, el sample set queda Cerrado, sus estudios en Pendiente de autorización ministerial, y el administrativo recibe un aviso y puede reintentar (G8).
- Cerrar y cambiar los estados de los estudios va en una sola transacción.

**Tests mínimos**

- Nueve muestras → sigue en armado; la décima → cerrado, 10 estudios en Pendiente de autorización ministerial y la siguiente muestra abre otro.
- Un Pompe urgente solo → cierra con 1; un Pompe urgente en un sample set con 3 → cierra con 4.
- Muestra sin volumen, insuficiente o ya incluida → error.
- CCB con una fila por estudio y las columnas pedidas.
- Autorización correcta → PDF guardado, Pendiente de retiro, estudios en Pendiente de envío y aviso; Ministerio caído → Cerrado, y el reintento funciona.
- El transportista entra a `/sample-sets` → 403.

**Fuera de alcance y supuestos:** el retiro de FedEx (#19); la espera al día siguiente si no llega a 10 no necesita código; O14, G8.

**Prompt de referencia**

```text
/implementar-escenario E28 E29
Issue #14; #8 ya está en develop. Leé core/sample_sets/modelos.py, core/muestras, el modelo
Estudio (pompe_urgente), storage.py, la tabla sample_sets de @docs/modelo-datos.md con su índice
de un solo sample set en armado, y los estados del sample set en @docs/lel.md.
Sin migración.
agregar_muestra(muestra) es el punto de entrada (lo llama #18 al registrar un volumen válido): no
hace commit ni llama a la API; quien la llama hace commit y después solicitar_autorizacion.
El Ministerio no tiene contrato: creá integraciones/ministerio.py con autorizar(ccb) → PDF, un mock
y un borrador provisorio en docs/apis/ministerio.md. El CCB se arma con openpyxl.
Reglas con test: máximo 10; cierra con 10 o con un Pompe urgente; cerrado no admite más; solo
muestras con volumen válido y sin sample set; cerrar y cambiar estados en una transacción; si el
Ministerio falla, queda Cerrado y se puede reintentar (G8 de @docs/guia-issues.md).
Transiciones: en_laboratorio_central → pendiente_autorizacion_ministerial → pendiente_envio.
El CCB tiene datos de pacientes: solo lo baja el administrativo y va a Storage privado.
Tests: 9 y 10 muestras, Pompe solo y acompañado, muestras inválidas, columnas del CCB,
autorización correcta, Ministerio caído con reintento y permisos.
No toques core/logistica ni core/muestras: la llegada y el volumen son de #18.
Dejá la fábrica de sample set y DATOS_POR_ESTADO de pendiente_envio. Control: pytest en verde;
con flask demo pendiente_envio, administrativo@exoma.test descarga el CCB y la autorización.
```
<!-- /issue:14 -->

## #15 · Nueva extracción, datos crudos y toma del estudio

<!-- issue:15 -->
**Escenarios:** E27, E32, E33 · **Área:** análisis y resultados · **Puntos:** 5 · **Rama:** `15-datos-crudos` · **Depende de:** #8 · **Milestone:** Control 3 (1/12)

**Objetivo.** El administrativo carga los datos crudos que llegan de Corea, o pide una nueva extracción si la muestra no sirve, y cada bioinformático toma un estudio sin que otro lo tome a la vez.

**Criterios de aceptación**

- E27.1 El administrativo registra que la muestra es insuficiente e indica el motivo.
- E27.2 El sistema cambia el estudio a Requiere nueva extracción.
- E27.3 El sistema notifica al paciente y al médico tratante.
- E27.4 El paciente realiza RESERVAR TURNO DE EXTRACCIÓN sin un nuevo pago (ya lo permite #7).
- E32.1 El laboratorio de secuenciación envía los datos crudos de un estudio (fuera del sistema).
- E32.2 Si el laboratorio de secuenciación informa ADN insuficiente, el administrativo realiza SOLICITAR NUEVA EXTRACCIÓN.
- E32.3 Si el ADN es suficiente, el administrativo carga los datos crudos en el estudio.
- E32.4 Si el ADN es suficiente, el sistema cambia el estudio a En área de bioinformática.
- E32.5 Si el ADN es suficiente, el sistema notifica a todos los bioinformáticos.
- E33.1 El bioinformático consulta la lista de estudios En área de bioinformática.
- E33.2 El sistema ordena la lista con los Pompe urgentes primero y el resto por orden de llegada.
- E33.3 El bioinformático toma un estudio.
- E33.4 El sistema cambia el estudio a En análisis y lo quita de la lista de los demás bioinformáticos.

**Qué toca por capa**

- Migración: ninguna.
- Core: `core/muestras/nueva_extraccion.py` (`solicitar_nueva_extraccion(muestra, motivo, administrativo)`, que también usa #18 para el volumen); `core/analisis` (`cargar_datos_crudos`, `pendientes()`, `tomar(analisis, bioinformatico)`).
- Controlador: `datos_crudos` (administrativo): `GET /datos-crudos` (estudios En viaje a Corea), `POST /estudios/<id>/datos-crudos`, `POST /estudios/<id>/adn-insuficiente`. `bioinformatica` (bioinformático): `GET /bioinformatica/pendientes`, `POST /bioinformatica/analisis/<id>/tomar`, `GET /bioinformatica/mis-analisis`.
- Vistas: `datos_crudos/listado.html`, `bioinformatica/pendientes.html`, `bioinformatica/mis_analisis.html`.
- Integración: Storage para el archivo de datos crudos.
- Demo: entradas de `en_area_bioinformatica` y `en_analisis` (tomado por `bioinformatico@exoma.test`) en `DATOS_POR_ESTADO`.

**Cambios de estado y reglas**

- `en_viaje_corea` → `en_area_bioinformatica` al cargar los datos crudos; `en_viaje_corea` → `requiere_nueva_extraccion` por ADN insuficiente; `en_laboratorio_central` → `requiere_nueva_extraccion` por volumen (la función; la pantalla es de #18); `en_area_bioinformatica` → `en_analisis` al tomarlo.
- Datos crudos: `.txt` con solo A, C, T, G y saltos de línea, no vacío, hasta 20 MB (G12). Se guardan en Storage; `estudios.datos_crudos_*` y `analisis.disponible_en` del análisis abierto.
- Nueva extracción: motivo `volumen` o `adn`; marca la muestra (`insuficiente_motivo`, `insuficiente_en`); mismo estudio y sin cobro.
- Aviso a todos los bioinformáticos activos (`listar_activos_por_rol`).
- Pendientes: análisis con `disponible_en` y sin bioinformático, Pompe urgente primero y después por `disponible_en`.
- Tomar: `update ... where bioinformatico_id is null`; si no actualiza ninguna fila, "ya lo tomó otro bioinformático".

**Tests mínimos**

- Carga válida → archivo en Storage, En área de bioinformática y aviso a dos bioinformáticos; archivo con una X → 400; estudio en otro estado → error.
- ADN insuficiente → Requiere nueva extracción, muestra marcada y avisos al paciente y al médico; por volumen desde En laboratorio central → igual; desde un estado inválido → error.
- Lista: un Pompe urgente reciente aparece antes que uno común más viejo; uno tomado no aparece.
- Tomar → En análisis; dos bioinformáticos toman el mismo → el segundo falla.
- El paciente entra a `/bioinformatica/pendientes` → 403; el administrativo intenta tomar → 403.

**Fuera de alcance y supuestos:** registrar variantes y finalizar (#20); O5, G12.

**Prompt de referencia**

```text
/implementar-escenario E27 E32 E33
Issue #15; #8 ya está en develop. Leé src/core/estudios (Estudio, Analisis, cambiar_estado),
core/muestras, storage.py, listar_activos_por_rol de core/usuarios, la tabla analisis de
@docs/modelo-datos.md (lista de pendientes y la regla para tomar) y O5 de @docs/decisiones.md.
Sin migración.
solicitar_nueva_extraccion va en core/muestras/nueva_extraccion.py: la usa este issue por ADN
insuficiente y #18 por volumen menor a 2 ml. Dejá su firma clara y probala desde los dos estados.
La lista y la toma van en core/analisis; #20 y #21 le agregan funciones después.
Reglas con test: datos crudos .txt solo con A, C, T, G y saltos de línea, hasta 20 MB (G12 de
@docs/guia-issues.md); aviso a todos los bioinformáticos activos; Pompe urgente primero y después
por disponible_en; tomar con update where bioinformatico_id is null.
Transiciones: en_viaje_corea → en_area_bioinformatica o requiere_nueva_extraccion;
en_laboratorio_central → requiere_nueva_extraccion; en_area_bioinformatica → en_analisis.
Tests: carga válida e inválida, ADN insuficiente, volumen, estado inválido, orden de la lista,
doble toma y permisos.
No toques core/muestras/__init__ ni los modelos de #8.
Control: pytest en verde; administrativo@exoma.test carga un .txt en el estudio de flask demo
en_viaje_corea y bioinformatico@exoma.test lo toma.
```
<!-- /issue:15 -->

## #16 · Código de verificación y activación de la cuenta del paciente

<!-- issue:16 -->
**Escenarios:** E04, E05 · **Área:** acceso y alta clínica · **Puntos:** 3 · **Rama:** `16-verificacion-activacion` · **Depende de:** #5, #9, #10 · **Milestone:** Entrega (8/12)

**Objetivo.** Proteger los datos genéticos: quien entra desde un dispositivo o una red nuevos confirma un código que llega por mail, y el paciente cambia la contraseña provisoria en su primer ingreso.

**Criterios de aceptación**

- E04.1 El usuario ingresa su usuario y su contraseña (hecho en #2).
- E04.2 El sistema valida las credenciales de acceso (hecho en #2).
- E04.3 Si las credenciales no son válidas, el sistema rechaza el ingreso (hecho en #2).
- E04.4 Si el dispositivo o la red son nuevos, el sistema envía un código de verificación al mail del usuario.
- E04.5 Si recibió un código, el usuario ingresa el código de verificación.
- E04.6 El sistema muestra la vista que corresponde al rol del usuario (hecho en #2).
- E05.1 El paciente recibe por mail su usuario y su contraseña provisoria (lo manda #10).
- E05.2 El paciente ingresa al sistema con las credenciales provisorias.
- E05.3 El sistema solicita el cambio de contraseña.
- E05.4 El paciente define una contraseña nueva.
- E05.5 El sistema habilita la vista del paciente con sus estudios y sus avisos (historial de #5).

**Qué toca por capa**

- Migración: `dispositivos_confiables`, `codigos_verificacion`.
- Core: `core/usuarios/verificacion.py` (`huella(cookie, ip)` con HMAC y `SECRET_KEY`, `necesita_codigo`, `emitir_codigo`, `validar_codigo`, `confiar`); `cambiar_contrasena(usuario, nueva)`.
- Controlador: `autenticacion`. El login, si hace falta código, deja la sesión pendiente y redirige a `GET|POST /login/verificacion`; `POST /login/verificacion/reenviar`; `GET|POST /cuenta/contrasena`. En `helpers/auth.py`, mientras `debe_cambiar_contrasena` sea verdadero, toda ruta salvo logout y estáticos redirige al cambio de contraseña.
- Vistas: `autenticacion/verificacion.html`, `autenticacion/cambiar_contrasena.html`, `mails/codigo_verificacion.html`.
- Tests: `login_como` de `conftest.py` tiene que seguir funcionando para todos los issues (por ejemplo, marcando el dispositivo del cliente de test como confiable).

**Cambios de estado y reglas**

- Sin cambios de estado del estudio.
- Código de 6 dígitos, guardado como hash, vence a los 10 minutos, de un solo uso y con 5 intentos; pedir otro invalida el anterior.
- La cookie del dispositivo es aleatoria, `HttpOnly` y `Secure` en producción; la huella combina cookie e IP y nunca se guarda en claro.
- Al validar el código se agrega el dispositivo confiable y se regenera la sesión.
- Los mensajes siguen sin revelar si el mail existe.
- Contraseña nueva de al menos 8 caracteres, con confirmación y distinta de la provisoria; al cambiarla, `debe_cambiar_contrasena` pasa a falso.

**Tests mínimos**

- Dispositivo nuevo → pide código y manda el mail; código correcto → entra y el dispositivo queda confiable; la segunda vez no pide código; otra IP → lo pide.
- Código incorrecto 5 veces → deja de valer; vencido → rechazo; reenviado → el anterior no vale.
- Paciente con contraseña provisoria → redirige al cambio y no puede navegar; contraseña nueva igual a la provisoria → error; al cambiarla ve sus estudios.
- Credenciales inválidas → el mismo mensaje de antes.
- `login_como` sigue funcionando (corre la suite completa).

**Fuera de alcance y supuestos:** recuperar la contraseña olvidada (no está en los escenarios).

**Prompt de referencia**

```text
/implementar-escenario E04 E05
Issue #16; #5, #9 y #10 ya están en develop. Sos el único issue de este milestone que toca auth: leé
helpers/auth.py, controllers/autenticacion.py, templates/autenticacion/, core/usuarios,
tests/conftest.py (login_como) y test_autenticacion.py, la decisión S6 de @docs/decisiones.md y
las tablas dispositivos_confiables y codigos_verificacion de @docs/modelo-datos.md.
Migración: esas dos tablas.
E04 ya tiene hechos los episodios 1-3 y 6: agregá el 4 y el 5 sin romperlos. Tras validar la
contraseña, si la huella (cookie aleatoria + IP, con HMAC) no es confiable, la sesión queda
pendiente hasta ingresar el código; al validarlo, se regenera la sesión.
Reglas con test: código de 6 dígitos con hash, 10 minutos, un uso, 5 intentos, reenviar invalida el
anterior; los mensajes no revelan si el mail existe.
E05: mientras debe_cambiar_contrasena sea verdadero, toda ruta salvo logout y estáticos redirige al
cambio; nueva de 8 o más, con confirmación y distinta de la provisoria; después va al historial.
login_como tiene que seguir andando para todos los tests del repo: ajustalo en conftest.py.
Tests: dispositivo nuevo, confiable, otra IP, 5 intentos, vencido, reenvío, paciente con
provisoria, contraseña igual y credenciales inválidas.
Control: la suite completa en verde; en el navegador, un paciente nuevo de #10 entra desde una
ventana privada, recibe el código por consola y cambia la contraseña.
```
<!-- /issue:16 -->

## #17 · Cobertura de obra social y reautorización

<!-- issue:17 -->
**Escenarios:** E16, E17, E18 · **Área:** presupuesto y pagos · **Puntos:** 5 · **Rama:** `17-obra-social` · **Depende de:** #12 · **Milestone:** Entrega (8/12)

**Objetivo.** El paciente pide que su obra social cubra el estudio; el administrativo registra la respuesta y, si la obra social rechaza, el paciente puede reclamar con una resolución judicial.

**Criterios de aceptación**

- E41.3 (de #6) El sistema registra el importe que cubre la obra social al autorizarse la cobertura.
- E16.1 El paciente elige usar la cobertura de su obra social.
- E16.2 El sistema consulta la API de obras sociales y muestra las obras sociales con su porcentaje de cobertura.
- E16.3 El paciente selecciona su obra social.
- E16.4 El sistema cambia el estudio a Pendiente de autorización.
- E16.5 El sistema envía una notificación al administrativo para que solicite la autorización a la obra social.
- E17.1 Si la obra social autoriza, el administrativo registra la autorización.
- E17.2 Ante una autorización, el sistema realiza REGISTRAR OPERACIÓN FINANCIERA.
- E17.3 Ante una autorización, el sistema cambia el estudio a Habilitado para turno (con cobertura parcial, recién cuando el paciente paga la diferencia: O3 y O18).
- E17.4 Si la obra social rechaza, el administrativo registra el rechazo.
- E17.5 Ante un rechazo, el sistema cambia el estudio a Rechazado por obra social.
- E17.6 El sistema envía una notificación al paciente con la respuesta de la obra social.
- E18.1 El paciente carga una demanda de reautorización asociada al estudio.
- E18.2 El paciente sube el PDF de la resolución judicial favorable.
- E18.3 El sistema cambia el estudio a Pendiente de autorización.
- E18.4 El sistema avisa al administrativo que hay una reautorización pendiente.
- E18.5 El administrativo realiza AUTORIZAR COBERTURA.

**Qué toca por capa**

- Migración: `coberturas`, `demandas_reautorizacion`.
- Core: `core/coberturas` (`opciones()`, `solicitar`, `autorizar`, `rechazar`, `cargar_demanda`). En `core/pagos`, el pago particular también acepta la diferencia de una cobertura autorizada parcial.
- Controlador: `coberturas`. Paciente: `GET|POST /estudios/<id>/cobertura`, `GET|POST /estudios/<id>/reautorizacion`. Administrativo: `GET /coberturas`, `POST /coberturas/<id>/autorizar`, `POST /coberturas/<id>/rechazar`.
- Vistas: `coberturas/elegir.html`, `coberturas/pendientes.html`, `coberturas/reautorizacion.html`; botón "Usar mi obra social" en `pagos/presupuesto.html` y el aviso "falta pagar la diferencia".
- Integración: `integraciones/obras_sociales.py` con `listar()` (**contrato pendiente**: mock y `docs/apis/obras_sociales.md`); Storage para el PDF de la resolución.

**Cambios de estado y reglas**

- `presupuestado` → `pendiente_autorizacion` al elegir; `pendiente_autorizacion` → `habilitado_turno` (100 % o diferencia pagada) o → `rechazado_obra_social`; `rechazado_obra_social` → `pendiente_autorizacion` con la demanda.
- El porcentaje se copia de la API al elegir; la obra social elegida se guarda en `obras_sociales` (upsert).
- Autorizar: `importe_cubierto = total × porcentaje`, pago de tipo `obra_social` y asiento `cobertura_obra_social` (una autorización equivale a un pago).
- Con menos del 100 %, la cobertura queda `autorizada` y el estudio sigue en Pendiente de autorización hasta que el paciente paga la diferencia con el flujo de E14 (O3, O18).
- La demanda solo se carga desde Rechazado por obra social, con un PDF de hasta 5 MB; la cobertura vuelve a `pendiente`.
- Si la API no responde, se muestra el error y el estudio no cambia.

**Tests mínimos**

- Elegir → Pendiente de autorización, cobertura `pendiente` y aviso a los administrativos; con el estudio fuera de Presupuestado → error.
- Autorizar 100 % → Habilitado para turno, pago y asiento; autorizar 70 % → sigue pendiente y pide el 30 %; pagar la diferencia → Habilitado para turno.
- Rechazar → Rechazado por obra social y aviso al paciente.
- Demanda con PDF → Pendiente de autorización y aviso; sin PDF, con otro tipo de archivo o desde otro estado → error.
- API caída → mensaje y sin cambios.
- El paciente intenta autorizar → 403.

**Fuera de alcance y supuestos:** la gestión telefónica con la obra social y el cobro real (O16); O3, O18.

**Prompt de referencia**

```text
/implementar-escenario E16 E17 E18
Issue #17; #12 ya está en develop. Leé core/pagos (con el cupón de #12), core/finanzas,
controllers/pagos.py y pagos/presupuesto.html, las tablas coberturas, demandas_reautorizacion y
pagos de @docs/modelo-datos.md, y O3, O16 y O18 de @docs/decisiones.md.
Migración: coberturas y demandas_reautorizacion.
La API de obras sociales no tiene contrato: creá integraciones/obras_sociales.py con listar(), un
mock con tres obras sociales (una al 100 % y otra al 70 %) y un borrador en docs/apis/.
Autorizar equivale a un pago: pago obra_social y asiento cobertura_obra_social con
registrar_asiento(). Con cobertura parcial, el estudio sigue en pendiente_autorizacion con la
cobertura autorizada hasta que el paciente paga la diferencia; adaptá pagar_particular para ese
caso sin romper el cupón.
Transiciones: presupuestado → pendiente_autorizacion; pendiente_autorizacion → habilitado_turno o
rechazado_obra_social; rechazado_obra_social → pendiente_autorizacion.
La demanda solo desde rechazado, con un PDF de hasta 5 MB guardado en Storage.
Tests: elegir, estado inválido, 100 %, 70 % más la diferencia, rechazo, demanda válida e inválida,
API caída y permisos.
Control: pytest en verde; el paciente de flask demo presupuestado elige la obra social al 70 %,
administrativo@exoma.test autoriza y el paciente paga la diferencia.
```
<!-- /issue:17 -->

## #18 · Seguimiento y llegada de las muestras al laboratorio central

<!-- issue:18 -->
**Escenarios:** E25, E26 · **Área:** turnos y logística · **Puntos:** 5 · **Rama:** `18-llegada-muestras` · **Depende de:** #13, #14, #15 · **Milestone:** Entrega (8/12)

**Objetivo.** El administrativo ve en un mapa por dónde va una muestra en traslado; al llegar al laboratorio central se registra su volumen y la muestra sigue sola a un sample set o a una nueva extracción.

**Criterios de aceptación**

- E25.1 El transportista informa su ubicación durante el recorrido.
- E25.2 El administrativo busca el estudio de un paciente.
- E25.3 El sistema identifica al transportista que lleva la muestra.
- E25.4 El sistema muestra en un mapa la ubicación del transportista.
- E26.1 El transportista entrega las muestras en el laboratorio central (fuera del sistema).
- E26.2 El transportista registra la llegada con todas las muestras recolectadas.
- E26.3 El sistema cambia esos estudios a En laboratorio central.
- E26.4 El administrativo registra el volumen de cada muestra.
- E26.5 Si una muestra tiene menos de 2 ml, el administrativo realiza SOLICITAR NUEVA EXTRACCIÓN (función de #15).
- E26.6 El sistema realiza ARMAR SAMPLE SET con las muestras válidas (`agregar_muestra` de #14).

**Qué toca por capa**

- Migración: ninguna.
- Core: `core/logistica` (`informar_ubicacion`, `ubicar_muestra(busqueda)`, `registrar_llegada(orden, transportista)`, `registrar_volumen(muestra, ml, administrativo)`; si `agregar_muestra` cerró el sample set, después del commit llama a `solicitar_autorizacion` de #14).
- Controlador: `logistica`. Transportista: `POST /orden-del-dia/ubicacion` (fetch con JSON y `X-CSRFToken`), `POST /orden-del-dia/llegada`. Administrativo: `GET /seguimiento?q=` (código de estudio o DNI), `GET /recepcion`, `POST /recepcion/muestras/<id>/volumen`.
- Vistas: script de ubicación en `logistica/orden_del_dia.html` (geolocalización del navegador cada 2 minutos, G9); `logistica/seguimiento.html` con el macro del mapa de #7; `logistica/recepcion.html`.
- Integración: ninguna nueva; usa las funciones de #14 y #15.

**Cambios de estado y reglas**

- `en_camino_laboratorio` → `en_laboratorio_central` al registrar la llegada. Después, `registrar_volumen` lleva a `requiere_nueva_extraccion` (vía #15) o a un sample set (vía #14).
- Ubicación: solo del transportista con una orden de hoy en curso (sin llegada), con latitud y longitud válidas.
- La búsqueda muestra la última ubicación y su hora; si el estudio no está En camino, dice en qué estado está.
- La llegada solo se registra con todas las paradas retiradas, y lleva todas las muestras de la orden (se asume que toda muestra retirada llega).
- Volumen entre 0,1 y 99,9 ml, una sola vez por muestra; menos de 2 ml → nueva extracción con motivo `volumen`; 2 ml o más → al sample set en armado.

**Tests mínimos**

- Ubicación guardada; sin orden en curso → 409; otro rol → 403.
- Búsqueda de un estudio En camino → posición del transportista; de uno que no está En camino → mensaje con su estado.
- Llegada con paradas pendientes → error; llegada completa → estudios En laboratorio central.
- Volumen 1,5 → Requiere nueva extracción y avisos; volumen 2,0 → en el sample set en armado; la décima muestra cierra el sample set; volumen registrado dos veces → error.

**Fuera de alcance y supuestos:** el historial de ubicaciones (se guarda solo la última); O4, G9.

**Prompt de referencia**

```text
/implementar-escenario E25 E26
Issue #18; #13, #14 y #15 ya están en develop. Leé core/logistica y logistica/orden_del_dia.html
(#13), agregar_muestra de core/sample_sets (#14), solicitar_nueva_extraccion de
core/muestras/nueva_extraccion.py (#15), el macro de mapa de #7, el modelo Transportista y la tabla
muestras de @docs/modelo-datos.md.
Sin migración.
E26.5 y E26.6 llaman a las funciones de #14 y #15 sin modificarlas; si agregar_muestra cierra el
sample set, llamá a solicitar_autorizacion después del commit.
La ubicación sale del navegador del celular del transportista (geolocalización) cada 2 minutos
mientras la orden de hoy no tiene llegada (G9 de @docs/guia-issues.md), por fetch con X-CSRFToken.
Se guarda solo la última, en transportistas.
Reglas con test: llegada solo con todas las paradas retiradas y para todas las muestras de la orden;
volumen entre 0,1 y 99,9 ml una sola vez; menos de 2 ml → nueva extracción; 2 ml o más →
agregar_muestra.
Transición propia: en_camino_laboratorio → en_laboratorio_central.
Tests: ubicación con y sin orden en curso, búsqueda en camino y en otro estado, llegada incompleta y
completa, volumen 1,5 y 2,0, décima muestra y volumen repetido, permisos.
Control: pytest en verde; con flask demo listo_para_retirar y su orden del día,
transportista@exoma.test registra el retiro y la llegada, y
administrativo@exoma.test lo sigue en el mapa y registra los volúmenes.
```
<!-- /issue:18 -->

## #19 · Retiro de FedEx y despacho del sample set

<!-- issue:19 -->
**Escenarios:** E30, E31 · **Área:** envío a Corea · **Puntos:** 3 · **Rama:** `19-retiro-fedex` · **Depende de:** #14 · **Milestone:** Entrega (8/12)

**Objetivo.** El administrativo programa con FedEx el retiro de cada sample set; cuando FedEx lo retira, invoca una URL y los estados cambian solos.

**Criterios de aceptación**

- E30.1 El administrativo consulta los sample sets pendientes de retiro.
- E30.2 El administrativo elige un día y una hora hábiles para el retiro.
- E30.3 El administrativo envía a FedEx el día, la hora y la URL del sample set.
- E30.4 El sistema cambia el sample set a Retiro programado.
- E31.1 FedEx retira el sample set en el día y la hora programados (fuera del sistema).
- E31.2 FedEx invoca la URL del sample set.
- E31.3 El sistema cambia el sample set a Despachado.
- E31.4 El sistema cambia todos los estudios del sample set a En viaje a Corea.

**Qué toca por capa**

- Migración: ninguna (`sample_sets.token_retiro` y las fechas ya existen).
- Core: `core/sample_sets/retiro.py` (`programar_retiro(sample_set, fecha_hora, administrativo)`, `despachar(token)`).
- Controlador: `sample_sets` (administrativo): `GET /sample-sets?estado=pendiente_retiro`, `POST /sample-sets/<id>/retiro`. `fedex`: `POST /fedex/retiros/<token>`, sin sesión y exento de CSRF; el token secreto es la autenticación.
- Vistas: formulario de retiro en `sample_sets/detalle.html`.
- Integración: `integraciones/fedex.py` con `programar_retiro(dia, hora, url)` (**contrato pendiente**: mock y `docs/apis/fedex.md`).

**Cambios de estado y reglas**

- Sample set: `pendiente_retiro` → `retiro_programado` → `despachado`. Estudios: `pendiente_envio` → `en_viaje_corea`, con historial sin usuario (lo dispara FedEx).
- Día hábil y futuro: de lunes a viernes, de 9 a 18, fuera de `feriados`.
- Cada sample set es un paquete aparte: un retiro por sample set.
- `token_retiro` aleatorio (`secrets.token_urlsafe`) y la URL absoluta con `url_for(..., _external=True)`.
- Si FedEx no responde, el sample set no cambia y se muestra el error.
- `despachar`: token inexistente → 404; sample set en otro estado → 409; llamada repetida → 200 sin cambios (G11). Todo en una transacción.

**Tests mínimos**

- Programar un retiro válido → token, Retiro programado y FedEx llamado con la URL.
- Sábado, 19 h, feriado o fecha pasada → error; sample set en otro estado → error; FedEx caído → sin cambios.
- Despachar → Despachado y sus estudios En viaje a Corea con historial sin usuario; token inválido → 404; repetido → 200 sin cambios; `GET` → 405.
- El transportista intenta programar → 403.

**Fuera de alcance y supuestos:** el seguimiento del envío a Corea; G11.

**Prompt de referencia**

```text
/implementar-escenario E30 E31
Issue #19; #14 ya está en develop. Leé core/sample_sets y controllers/sample_sets.py, la tabla
sample_sets de @docs/modelo-datos.md (token_retiro y fechas), la tabla feriados, la decisión S6 de
@docs/decisiones.md sobre las rutas exentas de CSRF y los estados del sample set en @docs/lel.md.
Sin migración.
FedEx no tiene contrato: creá integraciones/fedex.py con programar_retiro(dia, hora, url), un mock
y un borrador provisorio en docs/apis/fedex.md.
La lógica va en core/sample_sets/retiro.py; no cambies las funciones de #14.
POST /fedex/retiros/<token> no tiene sesión: eximila de CSRF, y que el token aleatorio sea lo que
autentica. Explicalo en un comentario.
Reglas con test: día y hora hábiles, futuros y fuera de feriados; un retiro por sample set; si FedEx
falla, no cambia nada; despachar con token inválido → 404, en otro estado → 409, repetido → 200 sin
cambios (G11 de @docs/guia-issues.md); todo en una transacción.
Transiciones: pendiente_envio → en_viaje_corea para todos los estudios del sample set.
Tests: programación válida, sábado, 19 h, feriado, pasado, FedEx caído, despacho, token inválido,
repetido, GET y permisos.
Control: pytest en verde; administrativo@exoma.test programa el retiro del sample set de flask demo
pendiente_envio y, con curl, la URL lo despacha.
```
<!-- /issue:19 -->

## #20 · Variantes y resultado del estudio

<!-- issue:20 -->
**Escenarios:** E34, E35 · **Área:** análisis y resultados · **Puntos:** 5 · **Rama:** `20-variantes-resultado` · **Depende de:** #5, #11, #15 · **Milestone:** Entrega (8/12)

**Objetivo.** El bioinformático registra las variantes que encontró en los genes pedidos, y al finalizar el sistema calcula el resultado con Apigen, arma el PDF y avisa al médico y al paciente.

**Criterios de aceptación**

- E34.1 El bioinformático elige un gen de los solicitados en el estudio.
- E34.2 El sistema consulta a la API de bioinformática las variantes conocidas de ese gen.
- E34.3 El bioinformático selecciona la variante encontrada.
- E34.4 El sistema registra la variante con su clasificación: patogénica, probablemente patogénica, benigna o VUS (O12).
- E34.5 El bioinformático repite los episodios por cada gen con variantes, incluidos los de hallazgos secundarios.
- E34.6 El bioinformático finaliza el análisis y el sistema realiza INFORMAR RESULTADO.
- E35.1 El sistema determina si el estudio es positivo, es decir, si hay una variante patogénica en los genes del diagnóstico presuntivo (con O12, el resultado puede ser además portador o negativo).
- E35.2 El sistema genera el resultado del estudio en PDF con la plantilla del laboratorio.
- E35.3 El sistema cambia el estudio a Finalizado.
- E35.4 El sistema notifica el resultado al médico tratante y al paciente por mail y por aviso.
- E35.5 El médico tratante y el paciente descargan el resultado del estudio (descarga de #5).

**Qué toca por capa**

- Migración: `variantes_encontradas`.
- Core: `core/analisis` (`genes_del_analisis` = `analisis_genes` más los ACMG del endpoint 4 si evalúa hallazgos; `variantes_de(gen)` con el endpoint 5; `registrar_variante(analisis, variante_id, copias, bioinformatico)`; `finalizar(analisis)`).
- Controlador: `bioinformatica` (bioinformático que tomó el análisis): `GET /bioinformatica/analisis/<id>`, `GET /bioinformatica/analisis/<id>/genes/<gen>`, `POST /bioinformatica/analisis/<id>/variantes`, `POST /bioinformatica/analisis/<id>/finalizar`.
- Vistas: `bioinformatica/analisis.html` (genes con sus variantes registradas), `bioinformatica/gen.html` (variantes de Apigen, paginadas); `pdf/resultado.html` con `helpers/pdf.py` de #7.
- Integración: Apigen endpoints 4, 5 y 7, y se agrega el 8 (hallazgos secundarios) a `apigen.py`; Storage para el PDF.

**Cambios de estado y reglas**

- `en_analisis` → `finalizado`.
- Solo el bioinformático que tomó el análisis registra y finaliza.
- El gen tiene que estar en el análisis (o en la lista ACMG si evalúa hallazgos); la variante tiene que ser de ese gen según Apigen. Clasificación copiada de Apigen; `copias` 1 o 2 (homocigota); una vez por análisis.
- Resultado (ver `analisis` en el modelo): por patología con el endpoint 7; genes agregados a mano: positivo si hay una patogénica, si no negativo (O19); el del análisis es el peor en el orden positivo, portador, negativo; sin variantes, negativo.
- Hallazgos secundarios con el endpoint 8, excluyendo las patologías del análisis.
- `fecha_reevaluacion` a un año si no hay variantes patogénicas pero sí alguna VUS o probablemente patogénica (las benignas no cambian nada), como dice el contrato de Apigen.
- Si Apigen falla al finalizar, el análisis no se finaliza y el estudio sigue En análisis.

**Tests mínimos**

- Registrar una patogénica en GAA → fila con su clasificación; variante de otro gen, gen no pedido o repetida → error; otro bioinformático → 404.
- Finalizar Pompe con una patogénica (mock: portador) → portador; con dos → positivo; sin variantes → negativo; gen a mano con una patogénica → positivo.
- Un hallazgo secundario aparece en el PDF; una VUS y una benigna, sin patogénicas → `fecha_reevaluacion`.
- Al finalizar: PDF en Storage, Finalizado y avisos al médico y al paciente; Apigen caído → sigue En análisis.
- El paciente entra a `/bioinformatica/analisis/<id>` → 403.

**Fuera de alcance y supuestos:** quitar una variante mal registrada (no hay bajas: consulta); O6, O12, O19.

**Prompt de referencia**

```text
/implementar-escenario E34 E35
Issue #20; #5, #11 y #15 ya están en develop. Leé core/analisis y controllers/bioinformatica.py
(#15), integraciones/apigen.py y apigen/contrato.md (endpoints 4, 5, 7 y 8), helpers/pdf.py (#7),
la descarga del resultado de #5, y las tablas analisis, analisis_patologias, analisis_genes y
variantes_encontradas de @docs/modelo-datos.md con la regla "Resultado del análisis".
Migración: variantes_encontradas.
En apigen.py solo agregás el endpoint 8; no cambies los existentes.
Reglas con test: solo el bioinformático que tomó el análisis; gen del análisis o ACMG; variante del
gen según Apigen; una vez por análisis; resultado por patología con el endpoint 7, genes a mano
con O19, el peor de todos; hallazgos con el 8 excluyendo las patologías del análisis;
fecha_reevaluacion si no hay patogénicas y sí alguna VUS o probablemente patogénica.
finalizar: si Apigen falla, no se finaliza nada. Si responde: PDF con pdf/resultado.html a Storage,
resultado y finalizado_en en el análisis, en_analisis → finalizado y avisos al médico y al paciente.
Tests: registro válido e inválido, otro bioinformático, portador, positivo, negativo, gen a mano,
hallazgo secundario, reevaluación, Apigen caído y permisos.
No toques la toma ni la lista de pendientes de #15.
Control: pytest en verde; con flask demo en_analisis, bioinformatico@exoma.test registra dos
variantes en GAA y finaliza, y ese paciente descarga el PDF.
```
<!-- /issue:20 -->

## #21 · Reanálisis

<!-- issue:21 -->
**Escenarios:** E12 · **Área:** análisis y resultados · **Puntos:** 2 · **Rama:** `21-reanalisis` · **Depende de:** #5, #11, #20 · **Milestone:** Entrega (8/12)

**Objetivo.** El médico tratante pide analizar otros genes del mismo exoma, sin nueva extracción ni nueva lectura del ADN.

**Criterios de aceptación**

- E12.1 El médico tratante realiza CONSULTAR HISTORIAL DE ESTUDIOS (pantalla de #5).
- E12.2 El médico tratante selecciona un estudio finalizado.
- E12.3 El médico tratante elige la nueva patología lisosomal o los nuevos genes a analizar.
- E12.4 El sistema obtiene de la API de bioinformática los genes de la nueva patología lisosomal.
- E12.5 El sistema devuelve el estudio a En área de bioinformática, con los mismos datos crudos.
- E12.6 El sistema notifica a los bioinformáticos.

**Qué toca por capa**

- Migración: ninguna.
- Core: `core/analisis/reanalisis.py` (`solicitar_reanalisis(estudio, medico, patologia=None, genes=(), evalua_hallazgos=False)`): análisis número n+1 de tipo `reanalisis`, `analisis_patologias` si hay patología, `analisis_genes` con `genes_para` de #11 más los genes a mano, `disponible_en` ahora.
- Controlador: `historial` (médico tratante): `GET|POST /historial/estudios/<id>/reanalisis`.
- Vistas: `historial/reanalisis.html`; botón "Solicitar reanálisis" en `historial/detalle.html` (#5).
- Integración: Apigen endpoints 1 y 3 (a través de `genes_para` y del buscador de genes de #11).

**Cambios de estado y reglas**

- `finalizado` → `en_area_bioinformatica`.
- Solo con el estudio Finalizado y solo el médico tratante del paciente.
- Hace falta una patología o al menos un gen.
- Mismos datos crudos: no se piden ni se cambian. Sin costo (O8): no hay presupuesto ni asiento.
- Un solo análisis abierto por estudio (índice de la base).

**Tests mínimos**

- Reanálisis por patología → análisis 2 con los genes de Apigen, En área de bioinformática, aviso a los bioinformáticos y datos crudos sin cambios.
- Reanálisis solo por genes → `analisis_patologias` vacía y genes `agregado_a_mano`.
- Estudio no finalizado o sin patología ni genes → error; médico ajeno → 404; paciente → 403.
- Ningún asiento financiero nuevo; el historial muestra los dos análisis.

**Fuera de alcance y supuestos:** O8, O17, O20.

**Prompt de referencia**

```text
/implementar-escenario E12
Issue #21; #5, #11 y #20 ya están en develop. Leé genes_para en core/estudios/alta.py (#11),
core/analisis (#15 y #20), controllers/historial.py e historial/detalle.html (#5), la tabla
analisis de @docs/modelo-datos.md (numero, tipo, disponible_en, índice de un análisis abierto) y
O8, O17 y O20 de @docs/decisiones.md.
Sin migración.
La lógica va en core/analisis/reanalisis.py y reutiliza genes_para; no la copies.
Reglas con test: solo estudio finalizado y del médico tratante del paciente; patología o al menos un
gen; mismos datos crudos; sin costo, así que no se crea presupuesto ni asiento; el análisis nuevo
lleva numero n+1, tipo reanalisis y disponible_en para entrar en la lista de pendientes.
Transición: finalizado → en_area_bioinformatica, con aviso a todos los bioinformáticos activos.
Agregá el botón "Solicitar reanálisis" en el detalle de #5, visible solo para el médico tratante y
con el estudio Finalizado.
Tests: por patología, por genes, estudio no finalizado, sin patología ni genes, médico ajeno,
paciente, sin asientos nuevos e historial con dos análisis. No toques genes_para ni la toma de #15.
Control: pytest en verde; medico@exoma.test pide un reanálisis del estudio de flask demo finalizado y
bioinformatico@exoma.test lo ve en sus pendientes.
```
<!-- /issue:21 -->

# 6. Cronograma por sprint

Cada sprint termina el día anterior al control: ese día se mergea lo terminado en `develop`, Integrante 1 abre el PR `develop` → `main`, aplica las migraciones y corre los seeds. En el control se muestra `main`.

| Sprint | Fechas | Issues que cierran | Qué se muestra en el control |
|---|---|---|---|
| 1 | 13/11 – 16/11 | #2, #3 | Login con cada rol y menú por rol; alta de usuarios (E03) con la grilla y el mail; "Mis avisos"; la máquina de estados con sus tests; el cliente de Apigen con mock; la Action en verde. Integrantes 2 a 4 muestran el plan de su primer issue y el borrador del contrato que les toca |
| 2 | 17/11 – 23/11 | #4, #5, #6, #7, #8 | El gerente define una patología con sus síntomas SNOMED; el administrativo emite el presupuesto y el paciente paga; el paciente reserva un turno en el mapa y recibe la orden; el bot marca la muestra lista; el paciente ve su estudio y consulta al chatbot. Los estados de partida salen de los seeds |
| 3 | 24/11 – 30/11 | #9, #10, #11, #12, #13, #14, #15 | El circuito desde el principio: registro del médico, alta del paciente con validación y familiograma, alta del estudio con genes de Apigen, pago con cupón, orden del día y retiro, sample set con CCB y autorización, carga de datos crudos y toma del estudio |
| 4 | 1/12 – 7/12 | #16, #17, #18, #19, #20, #21 | El circuito de punta a punta sin seeds intermedios: código de verificación, obra social, llegada con volumen y sample set, despacho con FedEx, variantes y resultado en PDF, reanálisis. Es la entrega y la defensa del 8/12 |
| Después | 9/12 – 22/12 | Tablero de BI | Fuera de esta guía: usa `historial_estados`, `asientos_financieros` y las fechas de `sample_sets` |

**Riesgos y cómo cubrirlos**

- **El sprint 1 son cuatro días.** Si #3 no llega completo al 16/11, se mergea por partes en `develop`: primero las sesiones 5 y 6, que es lo que necesitan los primeros issues de los demás (estados, fábricas, `notificar`, cliente base y Storage), y después E03. El 17/11 se muestra lo que esté.
- **El sprint 3 tiene dependencias internas.** #11 espera a #10 (mismo sprint). Integrante 2 empieza por #10, y #9 queda para después. Mientras tanto, Integrante 3 avanza con #12.
- **#13, #14 y #15 esperan a #8, que espera a #7.** #7 mergea primero un PR parcial con la migración, los modelos y `tareas.py`, para que Integrante 1 empiece #8 a mitad del sprint 2. Así #8 está en `develop` el 24/11.
- **El sprint 4 termina el día de la defensa.** #21 es el último eslabón (#15 → #20 → #21) y vale 2 puntos: si se atrasa, se recorta antes que cualquier otro.

# 7. Consultas para el ayudante

Marcá cada una cuando tenga respuesta y actualizá [decisiones.md](decisiones.md) con la fecha.

**Observaciones del LEL y del modelo**

- [ ] O2: ¿la sospecha familiar se valida con un familiar diagnosticado en lugar de los síntomas?
- [ ] O3 y O18: con cobertura parcial, ¿el paciente paga la diferencia antes del turno? ¿Hace falta un estado nuevo?
- [ ] O7: ¿cómo se detecta la inasistencia? ¿Se implementa la pérdida del pago a la quinta?
- [ ] O8: ¿el reanálisis cobra los genes nuevos?
- [ ] O10: ¿dos hermanos menores pueden usar el mail del mismo responsable? ¿Se entra con DNI?
- [ ] O13: ¿los genes de hallazgos secundarios cuentan en el presupuesto?
- [ ] O14: ¿la edad del Pompe urgente se mide al alta del estudio?
- [ ] O15: ¿el descuento del cupón es un porcentaje o un monto fijo?
- [ ] O16: ¿quién registra el cobro de la obra social, y cuándo?
- [ ] O20: ¿un paciente puede tener más de un estudio, o todo va por reanálisis?
- [ ] G1: ¿cualquiera puede auto registrarse como gerente médico o como administrativo, sin aprobación?
- [ ] G2: con varias patologías en el diagnóstico presuntivo, ¿tienen que cumplir todas la regla de E08?
- [ ] G6: ¿el cupón se puede usar en la diferencia de una cobertura parcial?
- [ ] E34: ¿se puede quitar una variante registrada por error antes de finalizar? (el modelo no tiene bajas)

**Contratos de APIs**

- [ ] Quién provee y cuándo llegan los contratos de SNOMED, familiograma, obras sociales, cupones, optimización de recorridos, Ministerio de Salud, FedEx y chatbot.
- [ ] La transcripción del audio del resumen de historia clínica: ¿es un módulo de otro grupo o un servicio que elegimos nosotros?
- [ ] El bot: ¿quién crea el bot de Telegram del laboratorio y qué texto manda el centro? (supuesto: el código del estudio).
- [ ] El módulo de cupones: ¿recibe el PDF o solo el código? ¿Cómo valida que el cupón es del paciente?
- [ ] ¿Alcanza con mocks para las APIs que no lleguen antes del 8/12?
- [ ] Apigen v1 sacó MPS 2 (O11): ¿se deja así?

**Deploy y entrega**

- [ ] ¿Dónde se despliega la app (servidor de la cátedra u otro) y con qué URL pública? FedEx y Telegram necesitan llamarla.
- [ ] APScheduler necesita un solo proceso: ¿el deploy lo permite, o las tareas se disparan con un cron externo?
- [ ] ¿Se puede usar un SMTP real (Gmail) para la demo, o alcanza con los mails por consola?
- [ ] ¿Las teselas de OpenStreetMap se pueden usar en la demo?
- [ ] ¿Qué se entrega el 8/12 además del repositorio (manual, informe, video)?

# 8. Preparación del coloquio

El criterio es el de [guia-agentes.md](guia-agentes.md): cada uno tiene que poder explicar cualquier parte del sistema, aunque la haya escrito otro agente. Por eso el reparto mezcla áreas y la revisión de PR rota.

| Tema | Qué hay que poder explicar | Dónde verlo |
|---|---|---|
| Flujo de un request | Ruta → decoradores de sesión y rol → controlador que valida → core → commit → redirect (PRG) → plantilla. Qué pasa sin sesión (redirige al login), con otro rol (403) y sin token CSRF (400) | #2, #3 y el módulo usuarios |
| Máquina de estados | Los 16 estados, por qué el estado cambia solo con `cambiar_estado()`, qué guarda el historial y para qué sirve al tablero. Recorrer el circuito completo con el diagrama del LEL | #3, y las transiciones de cada issue |
| Transacciones | Qué va en un mismo commit (pago, asiento y estado; cierre del sample set y sus estudios; cupón vencido y pago) y qué pasa si algo falla en el medio. Por qué el mail sale después del commit | #6, #12, #14, #10 |
| Concurrencia | Dos pacientes que reservan la misma franja (índice único) y dos bioinformáticos que toman el mismo estudio (`update ... where bioinformatico_id is null`) | #7, #15 |
| Permisos y datos genéticos | Roles por ruta, 404 en lugar de 403 para lo ajeno, código por dispositivo nuevo, contraseña provisoria, RLS sin políticas, rutas sin sesión (login, registro, webhooks) y cómo se autentican | #5, #8, #9, #16, #19 |
| Integraciones y mocks | El cliente base (timeout, `IntegracionError`, `USE_MOCKS`), cómo se prueba sin la API, qué pasa si la API no responde en cada escenario, y por qué los contratos pendientes tienen un borrador | #3 y todos los `integracion` |
| Sample sets y Pompe urgente | Por qué 10 (envío gratis), por qué un Pompe urgente cierra antes, cómo se calcula la marca (O14), CCB y PDF del Ministerio, y por qué el Pompe urgente va primero en la lista de bioinformática | #11, #14, #15 |
| Resultado del estudio | Patogénica, portador y negativo con Apigen; genes agregados a mano (O19); hallazgos secundarios; reanálisis sobre los mismos datos crudos | #20, #21 |
| Trabajo con agentes | `CLAUDE.md`, plan mode, skills, el subagente revisor, permisos y por qué las reglas de negocio están en código con test | [guia-agentes.md](guia-agentes.md) |

**Recordatorio.** Por cada issue terminado, antes del PR, corré `/guia-estudio` con sus escenarios (por ejemplo `/guia-estudio E07-E08-E36`). Deja `docs/estudio/<escenarios>.md` con el recorrido del código, las reglas, los tests y una guía de estudio. Antes del 8/12, cada uno lee las guías de los issues que **no** hizo, empezando por los que revisó en los PR.

# 9. Script para cargar los issues

`scripts/crear_issues.ps1` lee este archivo y carga todo en GitHub con `gh`. No duplica el contenido: toma la tabla de la sección 3 (entre las marcas `tabla-issues`) y el cuerpo de cada issue de la sección 5 (entre las marcas `issue:N`). Si se cambia la guía antes de correrlo, el script usa la versión nueva.

Qué hace:

1. Crea o actualiza los 11 labels (`gh label create --force`).
2. Crea los 4 milestones que falten, con su fecha (`gh api repos/{owner}/{repo}/milestones`).
3. Crea los 20 issues en orden, sin asignar, con su título, sus labels, su milestone y el cuerpo. Si ya existe un issue con el mismo título, lo saltea.
4. Si GitHub asignó números distintos de los de la guía, reescribe las referencias `#N` de cada cuerpo con los números reales.
5. Deja la correspondencia en `scripts/issues-creados.csv`.

Se corre desde la raíz del repo, con `gh auth login` hecho y **antes de abrir otro issue o PR**, para que los números coincidan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/crear_issues.ps1
```

Con `-Prueba` muestra lo que haría sin crear nada.
