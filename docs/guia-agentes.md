# Guía: desarrollar el sistema de exoma con agentes (Claude Code)

Nov 10, 2026 · @Someone

## Para qué sirve esta guía

Sí, conviene que una sola persona arme la base del proyecto antes de repartir los escenarios. Es el sprint 0. Esta guía explica cómo hacerlo con Claude Code siguiendo la clase de agentes de la cátedra, y cómo trabajar después los cuatro de la misma manera.

**Por qué una base primero.** Si los cuatro arrancan a la vez, cada agente inventa su propia estructura, su forma de manejar la sesión y su manera de cambiar el estado de un estudio. Después hay que unificar todo. Con una base hecha, cada agente copia el mismo módulo de ejemplo y respeta las mismas reglas.

**Plazo.** La base tiene que estar en `main` el viernes 13/11. Así el resto arranca con los escenarios y hay algo para mostrar en el control presencial del 17/11. Después vienen el control virtual del 24/11, el presencial del 1/12 y la defensa del 8/12.

**Cómo leerla.** Las secciones 2 a 6 son el método y sirven para todo el proyecto. Las secciones 7 y 8 son la base, con los prompts listos para usar. La 9 dice qué hacen los demás mientras tanto.

**Decisiones ya tomadas.** Flask con MVC (vistas en Jinja + Bootstrap), PostgreSQL en Supabase, Poetry, pytest y Claude Code como agente. El profesor confirmó el 11/11 que Flask MVC con Jinja está bien, aunque su lista de soporte nombra MVC solo con Django.

## La clase de agentes, aplicada a programar

Claude Code es un agente como los de la clase: un modelo que decide el camino, con instrucciones, tools, memoria y un loop. Programar bien con él no es escribir mejores prompts, sino configurar bien esas piezas y controlarlas.

| Pieza de la clase | En Claude Code | Qué hacemos en este proyecto |
| --- | --- | --- |
| LLM | El modelo; se cambia con `/model` | Modelo grande para planificar; uno más chico para tareas mecánicas |
| Instrucciones | `CLAUDE.md`, que se lee al empezar cada sesión | Un `CLAUDE.md` corto en el repo, que se cambia por PR como el código |
| Tools | Leer, editar y correr comandos; CLIs y servidores MCP | `poetry`, `pytest`, `gh`, CLI de Supabase y el MCP de Supabase en solo lectura |
| Memoria de corto plazo | La conversación (ventana de contexto) | Una sesión por issue y `/clear` al cambiar de tarea |
| Memoria de largo plazo | `CLAUDE.md` y archivos del repo | Decisiones y supuestos en `docs/decisiones.md` |
| Estado del proceso | El plan (plan mode), el issue y la rama | El plan aprobado queda en el PR |
| Conocimiento (RAG) | Archivos que se leen solo cuando hacen falta (`@archivo`, skills) | LEL, escenarios y contratos de APIs en `docs/`, referenciados con `@` |
| Loop | Lee, edita, corre, mira el resultado y repite | Siempre con un check que dé pasa o falla: los tests |
| Guardrails | Permisos allow/ask/deny y hooks | `.env` bloqueado; migraciones y push piden aprobación |
| Human-in-the-loop | Plan mode, aprobaciones y revisión del PR | Nadie mergea un PR que otro no leyó |
| Evals | Tests automáticos | pytest por escenario y GitHub Action en cada PR |
| Observabilidad | `/context`, historial de la sesión y commits | Commits chicos; PR con qué se pidió y cómo se probó |
|  |  |  |

**La escalera de complejidad también vale acá.** Subí un escalón solo cuando el anterior no alcanza:

1. Pedido directo, para cambios que se describen en una oración.
2. Plan mode y después implementación, para un escenario.
3. Subagentes, para investigar mucho código o revisar con contexto limpio.
4. Varias sesiones en paralelo, solo cuando ya dominan lo anterior.

**El costo oculto del loop también.** En cada paso el agente vuelve a mandar todo el historial. Cuando la ventana se llena, olvida instrucciones y se equivoca más. Por eso: tareas chicas, `/clear` entre tareas e investigaciones grandes en subagentes.

## Preparar el entorno

Cada integrante instala lo mismo una sola vez. La configuración del agente viene en el repo, así que no hay que configurarlo a mano.

1. **Claude Code.** Instalalo con la guía oficial de [code.claude.com/docs](https://code.claude.com/docs/en/best-practices).
2. **Herramientas.** Python 3.12, Poetry, Git y GitHub CLI (`gh auth login`). Para la CLI de Supabase usen `npm install` y `npx supabase …`, como en Apigen. Claude Code usa `gh` para leer issues y abrir PRs.
3. **Dónde abrirlo.** Siempre en la raíz del repo (`TTPS-grupo10/`), así carga `CLAUDE.md`, `.claude/` y `.mcp.json`.
4. **MCP de Supabase, en solo lectura y limitado al proyecto.** Una persona lo agrega y queda en `.mcp.json` para todos:

```bash
claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=<REF_DEL_PROYECTO>&read_only=true&features=database,docs"
```

Después, cada uno corre `/mcp` dentro de Claude Code, elige `supabase` y se autentica en el navegador; no hace falta un token. Con `read_only=true` las consultas corren con un usuario de Postgres de solo lectura, y con `project_ref` no puede tocar otros proyectos (como el de Apigen). Sirve para que el agente vea tablas y datos de prueba. Los cambios de esquema van siempre por migración, nunca por el MCP.

5. **Primer chequeo.** Abrí Claude Code y corré `/context` para ver que cargó `CLAUDE.md`, `/permissions` para ver las reglas del equipo y `/mcp` para ver Supabase conectado.

Los primeros días usen el modo de permisos Manual (se cambia con `Shift+Tab`): pide aprobación antes de cada edición y comando. Es más lento, pero es la mejor forma de aprender qué hace el agente y por qué.

## Los archivos que guían al agente

Cuatro archivos versionados hacen que los cuatro agentes trabajen igual. Son el "system prompt", los guardrails y los workflows del equipo. Se copian al repo antes de pedirle nada al agente y se cambian solo por PR.

### 1. `CLAUDE.md` (raíz del repo)

Tiene que ser corto: si el archivo es largo, el agente ignora la mitad. Para cada línea, preguntá si sacarla haría que el agente se equivoque. Si no, sacala. Los comandos se ajustan cuando la base esté hecha.

```markdown
# Sistema de exoma clínico – TTPS 2026, grupo 10

Sistema web del laboratorio central para el circuito del exoma clínico (patologías lisosomales).
apigen/ es nuestra API de bioinformática (módulo 5): no se modifica desde el sistema.

## Stack
- Python 3.12 + Poetry · Flask 3, MVC con Jinja2 · SQLAlchemy 2 + Flask-SQLAlchemy-Lite + psycopg 3
- PostgreSQL en Supabase: el esquema se define SOLO con migraciones en sistema/supabase/migrations
- Bootstrap 5 servido localmente · pytest

## Comandos (desde sistema/)
- Instalar: `poetry install`
- Correr: `poetry run flask run --debug`
- Tests: `poetry run pytest -q` (uno solo: `poetry run pytest tests/test_x.py -q`)
- Datos de prueba: `poetry run flask seeds`
- Nueva migración: `npx supabase migration new <nombre>`. La aplica una persona con `npx supabase db push`.

## Arquitectura (MVC)
- Modelo: src/core/<modulo>/ → modelos SQLAlchemy y reglas de negocio. Sin Flask ni request.
- Controlador: src/web/controllers/<modulo>.py → un blueprint por módulo: valida, llama a core, renderiza.
- Vista: src/web/templates/<modulo>/ → Jinja que extiende layout.html.
- APIs externas: src/integraciones/<api>.py → timeout de 5 s, errores legibles y modo mock (USE_MOCKS=1).
- Módulo de referencia: usuarios (E03). Un módulo nuevo copia su estructura.

## Reglas del dominio
- Los nombres salen del LEL (docs/lel.md): estudio, muestra, sample set, turno de extracción…
- Los escenarios están en docs/escenarios.md (E01–E41): cada episodio es un criterio de aceptación.
- El estado de un estudio cambia SOLO con cambiar_estado() de src/core/estudios.
- Toda ruta lleva @login_required y @rol_requerido(...).

## Flujo de trabajo
- Un issue = una rama (e10-alta-estudio) = una sesión.
- Antes de dar algo por terminado: correr los tests y mostrar la salida.
- Commits en español que nombran el escenario: "E10: alta de estudio con genes de Apigen".
- IMPORTANT: nunca leer ni escribir .env, ni hardcodear claves, ni usar datos reales de pacientes.
```

### 2. `.claude/settings.json` (permisos del equipo)

Son los guardrails "en código, no en el prompt" de la clase. `deny` siempre gana sobre `allow`, y `ask` es el human-in-the-loop: el agente puede proponer una migración o un push, pero una persona lo aprueba. Las excepciones personales van en `.claude/settings.local.json`, que no se versiona.

```json
{
  "permissions": {
    "allow": [
      "Bash(poetry install)",
      "Bash(poetry run pytest *)",
      "Bash(poetry run flask *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(gh issue view *)"
    ],
    "ask": [
      "Bash(poetry add *)",
      "Bash(git push *)",
      "Bash(gh pr create *)",
      "Edit(./sistema/supabase/migrations/**)"
    ],
    "deny": [
      "Read(**/.env)",
      "Edit(**/.env)",
      "Bash(cat *.env)",
      "Bash(npx supabase db *)",
      "Bash(git push --force *)"
    ]
  }
}
```

Se bloquea `.env` pero no `.env.example`, porque el agente necesita saber qué variables existen. Ojo: estas reglas controlan las herramientas del agente, no cualquier proceso. Un script de Python igual podría abrir `.env`; por eso, además, las claves nunca van en el código.

### 3. Skill `.claude/skills/implementar-escenario/SKILL.md`

Es el workflow del equipo para un escenario, fijo y repetible. Se usa con `/implementar-escenario E10`.

```markdown
---
name: implementar-escenario
description: Implementa un escenario (E01–E41) del sistema de exoma con el flujo del equipo
disable-model-invocation: true
---
Implementá el escenario $ARGUMENTS.

1. Leé el escenario en docs/escenarios.md y los términos que usa en docs/lel.md.
2. Si usa una API externa, leé su contrato en docs/apis/ y su cliente en src/integraciones/.
3. Mirá el módulo de referencia (usuarios) y seguí su estructura.
4. Proponé un plan: tablas y migración, funciones de core, rutas, vistas, roles,
   cambios de estado y un test por episodio. Esperá mi aprobación antes de editar.
5. Implementá el plan. Corré `poetry run pytest -q` hasta que pase y mostrá la salida.
6. Listá lo que asumiste o dejaste afuera (por ejemplo, una observación abierta del LEL).
```

### 4. Subagente `.claude/agents/revisor-escenario.md`

Es el patrón Evaluator de la clase: un revisor con contexto limpio que no vio cómo se escribió el código, así que no lo defiende. Se le pide: "usá el subagente revisor-escenario para revisar E10 contra el diff con main". Claude Code trae además `/code-review`, que busca bugs en el diff.

```markdown
---
name: revisor-escenario
description: Revisa un cambio contra su escenario y las reglas del proyecto, con contexto limpio
tools: Read, Grep, Glob, Bash
---
Sos el revisor del equipo. Te pasan un escenario (E01–E41); el cambio es `git diff main...HEAD`.
Revisá solo esto y citá archivo y línea:
- ¿Cada episodio del escenario está implementado y tiene un test?
- ¿Cada ruta tiene @login_required y el rol correcto?
- ¿Los estados cambian solo con cambiar_estado()?
- ¿Las llamadas a APIs externas tienen timeout, manejo de error y mock?
- ¿Hay claves, datos reales o SQL armado concatenando strings?
Informá solo problemas de corrección o de requisitos, no de estilo.
```

Cuando una regla del `CLAUDE.md` se saltea seguido, conviene convertirla en un permiso o en un hook, porque esos se cumplen siempre.

## El flujo de trabajo por issue

Cada issue sigue el mismo circuito: el agente propone y ejecuta, pero los tests y dos personas deciden qué entra a `main`. Es el flujo explorar, planificar, implementar y commitear que recomienda la documentación de Claude Code, con los controles humanos de la clase.

&#91;embedded content: flujo por issue · 7 pasos, 3 decisiones\]

Las tres marcas resaltadas son los controles humanos: el plan, la prueba en el navegador y la aprobación del PR. El loop de los tests lo cierra el agente solo.

1. **Preparar.** `git switch main`, `git pull` y `git switch -c e10-alta-estudio`. Abrí `claude` en la raíz. Si venías de otra tarea, `/clear`.
2. **Explorar y planificar.** Pasá a plan mode con `Shift+Tab` hasta ver *plan mode on*. En ese modo el agente lee y responde pero no edita. Corré `/implementar-escenario E10`.
3. **Revisar el plan (vos).** Con `Ctrl+G` lo abrís en el editor para corregirlo. Prestá atención a esto: ¿usa los nombres del LEL?, ¿toca archivos de otro módulo?, ¿qué asume?, ¿hay un test por episodio? Si algo no cierra, pedile otro plan.
4. **Implementar.** Aprobá el plan. El agente edita, corre `pytest` y corrige hasta que pasa. Leé los cambios a medida que los propone y frenalo con `Esc` si se desvía.
5. **Probar en el navegador (vos).** `poetry run flask run --debug` y recorré el escenario con el usuario de prueba del rol que corresponde, también en el celular. Los tests no ven todo.
6. **Revisar con contexto limpio.** Pedile: "usá el subagente revisor-escenario para revisar E10 contra el diff con main". Corregí solo lo que afecta la corrección o los requisitos.
7. **Pull request.** Pedile: "commiteá y abrí un PR con gh: el título nombra el escenario y el cuerpo dice qué cambia, cómo se probó y qué se asumió". Otro integrante lo lee entero y lo aprueba. La GitHub Action corre los tests.

**Cuándo cortar.** Si corregiste dos veces lo mismo, el contexto ya está lleno de intentos fallidos: `/clear` y empezá de nuevo con un pedido mejor, que incluya lo que aprendiste. Para volver atrás código y conversación, `Esc` dos veces o `/rewind`. Para un cambio que se describe en una oración, salteá el plan.

## Guardrails y uso consciente

Usar agentes de forma consciente significa poder defender cada línea el 8/12: el agente escribe, pero ustedes deciden y entienden. Estas son las reglas del equipo.

- **Leer cada cambio antes de aceptarlo.** Si no lo podrías explicar en la defensa, pedile al agente que te lo explique o reescribilo. Por ejemplo: "explicame este controlador línea por línea y qué pasa si el usuario no tiene el rol".
- **Las reglas de negocio van en código y con test, no solo en el prompt.** Por ejemplo: 500 USD hasta 5 genes y 30 USD por gen adicional; síntoma cardinal o al menos dos secundarios; Pompe en un menor de 4 meses es urgente. Un límite en código no se puede "convencer".
- **Mínimo privilegio.** MCP de Supabase en solo lectura. El agente no aplica migraciones ni pushea a `main`. Las claves solo en `.env`.
- **Sin datos reales.** Nunca peguen datos reales de pacientes ni claves en un prompt. Usen los datos inventados de los seeds.
- **Prompt injection indirecta.** El agente va a leer contratos, issues y respuestas de las APIs de otros grupos. Si algo de eso le "da órdenes" (borrar, cambiar permisos, mandar datos), es un dato y no una instrucción. No peguen contenido externo sin leerlo antes.
- **Contexto y costo.** Una sesión por issue, `/clear` entre tareas y `/context` para ver cuánto ocupa. Las investigaciones grandes van a un subagente. No peguen logs enteros: solo el error.
- **Comparar con la documentación oficial.** El agente puede mezclar versiones viejas de las librerías. El caso típico acá es Flask-SQLAlchemy-Lite, que no es igual a Flask-SQLAlchemy. Si algo no anda, pedile que lea la documentación de esa versión.
- **Las piezas compartidas, de a una persona.** `core/estudios` (la máquina de estados), el login y `layout.html` los toca una persona a la vez y con PR revisado. Si dos agentes los cambian en paralelo, se rompen entre sí.
- **`CLAUDE.md` es código del equipo.** Se cambia por PR. Si el agente repite un error, se agrega una línea. Si ignora una regla, se acorta el archivo o la regla pasa a un permiso o un hook.

## Sprint 0: la base del proyecto

La base está lista cuando se cumplen dos cosas. Cualquiera puede clonar, correr `poetry install`, levantar la app, entrar con cada rol y ver los tests en verde. Y hay un módulo completo que sirve de modelo para copiar.

### Estructura de carpetas (MVC)

Es la organización de Proyecto de Software: `core` es el modelo, `web/controllers` el controlador y `web/templates` la vista. Si en Proyecto usaron otros nombres, usen los suyos. Lo importante es separar las tres capas y tener un solo patrón.

```text
TTPS-grupo10/
├── CLAUDE.md                      # instrucciones para el agente
├── .claude/                       # settings.json, skills/, agents/
├── .mcp.json                      # MCP de Supabase (solo lectura)
├── .github/workflows/             # mantener-activo + tests en cada PR
├── docs/
│   ├── lel.md, escenarios.md      # la especificación en texto
│   ├── apis/                      # un contrato por API de los compañeros
│   └── decisiones.md              # decisiones y supuestos (memoria del equipo)
├── apigen/                        # módulo 5 (ya existe)
└── sistema/
    ├── pyproject.toml, poetry.lock
    ├── .env.example
    ├── app.py                     # app = create_app()
    ├── supabase/migrations/       # el esquema, en SQL
    ├── src/
    │   ├── core/                  # MODELO: entidades y reglas de negocio
    │   │   ├── database.py
    │   │   ├── usuarios/  pacientes/  estudios/  notificaciones/
    │   │   ├── (después) patologias/  pagos/  turnos/  logistica/
    │   │   │   sample_sets/  analisis/  cupones/  finanzas/
    │   │   └── seeds.py
    │   ├── integraciones/         # clientes de APIs externas + mocks
    │   └── web/
    │       ├── __init__.py        # create_app(), blueprints, errores
    │       ├── config.py
    │       ├── controllers/       # CONTROLADOR: un blueprint por módulo
    │       ├── helpers/           # login_required, rol_requerido, paginación
    │       ├── templates/         # VISTA: layout.html, una carpeta por módulo, pdf/, mails/
    │       └── static/            # Bootstrap local, validaciones.js, interfaz.js
    └── tests/
```

### Dependencias de Poetry

Las versiones las resuelve `poetry add`; no las escriban a mano. Werkzeug y Jinja2 vienen con Flask.

| Paquete | Para qué | Origen |
| --- | --- | --- |
| `flask` | Rutas, blueprints, sesión y plantillas | Proyecto |
| `sqlalchemy`, `flask-sqlalchemy-lite` | ORM y su integración con Flask | Proyecto |
| `psycopg[binary]` | Conexión con PostgreSQL | Proyecto |
| `flask-session`, `cachelib` | Sesión guardada en el servidor | Proyecto |
| `python-dotenv` | Variables del `.env` | Proyecto |
| `httpx` | Llamar a las APIs de los compañeros (como en la demo de Apigen) | Nuevo |
| `flask-mail` | Mails de notificaciones y credenciales | Nuevo |
| `apscheduler` | Tareas programadas: orden del día y recordatorios de turno | Nuevo |
| `xhtml2pdf` | PDFs a partir de plantillas Jinja (resultado, orden de extracción) | Nuevo |
| `openpyxl` | Excel del CCB para el Ministerio | Nuevo |
| `supabase` | Subir y bajar PDFs de Supabase Storage | Nuevo |
| `pytest` (dev) | Tests | Proyecto |
| `ruff` (dev) | Linter: le da al agente un segundo control automático | Nuevo |

### Supabase (lo creás vos)

1. Creá un proyecto nuevo, separado del de Apigen, en la región de São Paulo, que es la más cercana.
2. Guardá la contraseña de la base fuera del repo. La cadena del *Session pooler* va al `.env` como `DATABASE_URL`.
3. En `sistema/` corré `npx supabase init` y `npx supabase link --project-ref <ref>`.
4. Invitá a los otros tres a la organización de Supabase: lo necesitan para ver el panel y usar el MCP.
5. Copiá el workflow `mantener-activo` para el proyecto nuevo.
6. Para los tests, usá una base aparte (el PostgreSQL local de Proyecto) en `DATABASE_URL_TEST`. Los tests nunca corren contra la base compartida.

### Qué incluye la base

- [ ] Estructura de carpetas y `create_app()` con blueprints y páginas de error 403, 404 y 500.
- [ ] Poetry con todas las dependencias, y `poetry install` funcionando en una compu limpia.
- [ ] `.env.example` con todas las variables: `DATABASE_URL`, `DATABASE_URL_TEST`, `SECRET_KEY`, `MAIL_*`, `SUPABASE_URL`, `SUPABASE_KEY`, `APIGEN_URL`, `APIGEN_KEY`, `USE_MOCKS`.
- [ ] Migración inicial en Supabase, con RLS activado en todas las tablas y sin políticas.
- [ ] Login y logout con Flask-Session y hash scrypt, los decoradores `login_required` y `rol_requerido`, y un usuario de prueba por cada uno de los 7 roles del LEL.
- [ ] `layout.html` responsivo con Bootstrap local, menú según el rol y mensajes flash.
- [ ] Modelo mínimo de Paciente con los datos de E06, sin pantallas.
- [ ] Estudio con sus 16 estados. `cambiar_estado()` solo permite las transiciones del LEL y guarda cada cambio con fecha y usuario, que es lo que necesita el tablero de BI.
- [ ] `notificar(usuario, asunto, mensaje, link)`: guarda el aviso y manda el mail. En desarrollo el mail sale por consola.
- [ ] Un cliente base para APIs externas (timeout de 5 s, errores legibles y mock) y el cliente de Apigen como primer ejemplo.
- [ ] Módulo de referencia completo: E03 *Dar de alta usuario*. Incluye una grilla con búsqueda, filtro por rol, orden y paginación, el alta con validación y la notificación.
- [ ] Tests de login, de `cambiar_estado()` y de E03, con fixtures por rol y la base de test separada.
- [ ] GitHub Action que corre los tests en cada PR.
- [ ] Los archivos de la sección 4, y el LEL y los escenarios en `docs/`.

Queda afuera de la base, como issues: el registro (E01, E02), el código por dispositivo nuevo (parte de E04), la activación de la cuenta del paciente (E05) y todos los demás escenarios.

## Prompts para construir la base

Son siete sesiones, una por bloque. Cada una arranca con `/clear`, empieza en plan mode (salvo la primera) y termina con un control que el agente tiene que correr y mostrar. Al final de cada bloque, commit. Todo va en una rama `base` y un solo PR que revisa otro integrante.

**Antes de empezar (a mano):**

1. Creá la rama `base` y copiá los cuatro archivos de la sección 4.
2. Exportá esta guía a Markdown como `docs/guia-agentes.md`, para que los prompts la puedan citar con `@`.
3. Poné los PDFs del LEL y de los escenarios en `docs/`.
4. Con el proyecto de Supabase creado, completá tu `.env` a partir del ejemplo.

### Sesión 1 · La especificación en texto (sin plan)

```text
Convertí los PDFs de docs/ a markdown: docs/lel.md y docs/escenarios.md. Un ## por símbolo del LEL
y uno por escenario con su código (E01…E41). No resumas ni cambies palabras.
Después creá docs/decisiones.md con las decisiones de stack de @docs/guia-agentes.md y las 9
observaciones abiertas del LEL, cada una con el supuesto adoptado.
Control: contame cuántos escenarios y cuántos símbolos quedaron en cada archivo.
```

### Sesión 2 · Estructura, Poetry y app

```text
Vamos a crear la base del sistema en sistema/. Seguí la sección "Sprint 0" de @docs/guia-agentes.md
(estructura y tabla de dependencias) y @CLAUDE.md. No toques apigen/.
Planificá: la estructura de carpetas; poetry init con Python 3.12 y poetry add de cada dependencia;
app.py con app = create_app(); src/web/__init__.py con create_app(), registro de blueprints y
páginas de error 403/404/500; config.py con Development, Testing y Production leídas del .env;
.env.example con las variables de la guía; una ruta / que renderice layout.html.
Control: `poetry run flask run --debug` levanta, y `poetry run pytest -q` pasa un test que pide / y
recibe 200.
```

### Sesión 3 · Base de datos y migraciones

```text
Configurá la base de datos. El proyecto de Supabase ya existe y DATABASE_URL (Session pooler) está
en mi .env. Planificá:
- src/core/database.py con Flask-SQLAlchemy-Lite. Leé su documentación: no es Flask-SQLAlchemy.
- La primera migración con `npx supabase migration new inicial`: tablas de roles y usuarios (email
  único, hash, rol, activo, fechas) y `enable row level security` en cada tabla.
- Modelos SQLAlchemy que mapean esas tablas. Nada de create_all: el esquema sale de las migraciones.
- Un fixture de pytest que, sobre DATABASE_URL_TEST, crea un esquema limpio y aplica todas las
  migraciones en orden.
No apliques migraciones a Supabase: yo corro `npx supabase db push`.
Control: un test que inserta y lee un usuario contra la base de test.
```

### Sesión 4 · Login, roles y layout

```text
Implementá la autenticación como en Proyecto de Software. Planificá:
- Login y logout con Flask-Session (sesión en el servidor) y hash scrypt de Werkzeug.
- Decoradores login_required y rol_requerido(*roles) en src/web/helpers/auth.py.
- layout.html con Bootstrap servido localmente, menú según el rol, mensajes flash y vista responsiva.
- Un comando `flask seeds` que crea un usuario de prueba por cada uno de los 7 roles del LEL
  (Usuario en @docs/lel.md).
Control: tests de login correcto, contraseña incorrecta, acceso sin sesión (redirige al login) y
acceso con el rol equivocado (403).
```

### Sesión 5 · Estudio y máquina de estados

```text
Leé "Estados del estudio" en @docs/lel.md. Planificá src/core/estudios:
- El modelo mínimo de Paciente con los datos de E06 (sin pantallas) y el modelo Estudio: paciente,
  médico tratante, genes, si evalúa hallazgos secundarios, estado y fechas.
- Un enum con los 16 estados y una tabla de transiciones permitidas sacada de los impactos de cada
  estado.
- cambiar_estado(estudio, nuevo_estado, usuario, motivo=None): rechaza las transiciones inválidas y
  guarda cada cambio en historial_estados con fecha y usuario.
- La migración, con RLS. Todavía sin pantallas.
Control: un test por cada transición válida del LEL y tests de transiciones inválidas.
```

### Sesión 6 · Notificaciones e integraciones

```text
Planificá dos piezas que van a usar todos los escenarios:
1. src/core/notificaciones: modelo Aviso y notificar(usuario, asunto, mensaje, link), que guarda el
   aviso y manda el mail con Flask-Mail (en desarrollo se suprime el envío y sale por consola).
   Agregá "Mis avisos" al layout.
2. src/integraciones: un cliente base con httpx (timeout de 5 s, errores convertidos en una
   excepción propia con mensaje legible, modo mock con USE_MOCKS=1 que lee respuestas de
   tests/fixtures/apis/) y el cliente de Apigen según @apigen/contrato.md: genes de una patología,
   genes de hallazgos secundarios, variantes de un gen y resultado del diagnóstico.
Control: tests con mocks para cada función y un test de que la falta de respuesta de la API se
maneja sin romper.
```

### Sesión 7 · Módulo de referencia y cierre

```text
/implementar-escenario E03
Es el módulo de referencia: los demás lo van a copiar, así que tiene que quedar prolijo. Incluí una
grilla de usuarios con búsqueda por nombre o mail, filtro por rol, orden por columna y paginación del
lado del servidor; el alta con validación en el servidor y en el cliente; y el mail con las
credenciales (episodio 4). Solo accede el administrador general.
```

Cuando pase, en la misma sesión:

```text
Usá el subagente revisor-escenario para revisar E03 y toda la rama contra @CLAUDE.md. Después:
creá .github/workflows/tests.yml (Postgres como servicio, poetry install, pytest en cada PR);
actualizá CLAUDE.md con los comandos reales y una sección corta "Cómo agregar un módulo" con usuarios
como ejemplo; y decime qué falta de la lista "Qué incluye la base" de @docs/guia-agentes.md.
```

**Para cerrar (vos):** leé el PR completo, aplicá las migraciones con `npx supabase db push` y corré `flask seeds`. Después pedile a un compañero que clone el repo y lo levante siguiendo solo el `CLAUDE.md`. Si lo logra sin preguntarte nada, la base está lista para mergear.

## Mientras tanto, y después

Mientras armás la base, los otros tres preparan lo que la base no cubre, sin tocar `sistema/`. Así practican el flujo con tareas de bajo riesgo: casi todo en plan mode y sin escribir código del sistema.

| Quién | Qué | Resultado |
| --- | --- | --- |
| Integrante 2 | Estudiar las APIs de los compañeros: leer sus repos o contratos y probar los endpoints | Un `docs/apis/<api>.md` por módulo (URL, autenticación, endpoints, ejemplos) y respuestas de ejemplo para los mocks |
| Integrante 3 | Modelo de datos completo a partir del LEL: pacientes, estudios, muestras, sample sets, turnos, pagos, cupones | Diagrama entidad-relación en `docs/`, para que las migraciones de cada escenario no choquen |
| Integrante 4 | Issues: uno por escenario, con los episodios como criterios de aceptación, labels por módulo y milestones al 17/11, 24/11, 1/12 y 8/12 | Issue tracker completo en GitHub |
| Los cuatro | Instalar el entorno (sección 3) y hacer una tarea de práctica, por ejemplo pedirle al agente que explique la demo de Apigen | Todos conocen el flujo antes de tocar el sistema |

**Próximos pasos.**

1. Juntar los contratos de las APIs de los compañeros y los usuarios de GitHub de los cuatro. Con eso se arma la guía de issues y el reparto por integrante.
2. Con la base en `main`, cada uno toma sus escenarios y sigue el flujo de la sección 5.

## Fuentes

- *Ingeniería de Agentes de IA*, clase de la cátedra TTPS (PDF compartido por el grupo): fórmula del agente, escalera de complejidad, memoria, costo del loop, guardrails, prompt injection, patrón Evaluator y evals.
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices): plan mode, `CLAUDE.md`, permisos, skills, subagentes, hooks, `/clear`, `/rewind` y revisión con contexto limpio.
- [Supabase MCP Server](https://supabase.com/docs/guides/ai-tools/mcp): parámetros `read_only`, `project_ref` y `features`, configuración en Claude Code y recomendaciones de seguridad.
- `apigen/contrato.md` del repo: endpoints de Apigen para el cliente de integraciones.
- *LEL* v3 y *Escenarios* v2 del sistema de exoma clínico, y el cronograma TTPS 2026.
