# Sistema de exoma clínico – TTPS 2026, grupo 10

Sistema web del laboratorio central para el circuito del exoma clínico (patologías lisosomales).
apigen/ es nuestra API de bioinformática (módulo 5): no se modifica desde el sistema.

## Stack
- Python 3.12 + Poetry · Flask 3, MVC con Jinja2 · SQLAlchemy 2 + Flask-SQLAlchemy-Lite + psycopg 3
- PostgreSQL en Supabase: el esquema se define SOLO con migraciones en sistema/supabase/migrations
- El proyecto Supabase del sistema es radpjgwkrzqtkczxcvxz (el del MCP en .mcp.json). Apigen usa otro proyecto: no tocarlo.
- Bootstrap 5 servido localmente · pytest

## Comandos (desde sistema/)
- Instalar: `poetry install`
- Correr: `poetry run flask run --debug`
- Tests: `poetry run pytest -q` (uno solo: `poetry run pytest tests/test_x.py -q`). Usan el Postgres
  local de DATABASE_URL_TEST (la crean si falta y aplican las migraciones); nunca la base de Supabase.
- Lint: `poetry run ruff check src tests` y `poetry run ruff format src tests`
- Datos de prueba: `poetry run flask seeds` → un usuario por rol (paciente@, medico@, administrativo@,
  bioinformatico@, transportista@, gerente@ y admin@exoma.test) con la contraseña de SEEDS_CONTRASENA
- Nueva migración: `npx supabase migration new <nombre>`. La aplica una persona con `npx supabase db push`.
- CI: .github/workflows/tests.yml corre ruff y pytest en cada PR, con Postgres 17 como servicio.

## Arquitectura (MVC)
- Modelo: src/core/<modulo>/ → modelos SQLAlchemy y reglas de negocio. Sin Flask ni request.
- Controlador: src/web/controllers/<modulo>.py → un blueprint por módulo: valida, llama a core, renderiza.
- Vista: src/web/templates/<modulo>/ → Jinja que extiende layout.html.
- APIs externas: src/integraciones/<api>.py → timeout de 5 s, errores legibles y modo mock (USE_MOCKS=1).
- Módulo de referencia: usuarios (E03). Un módulo nuevo copia su estructura.

## Cómo agregar un módulo (ejemplo: usuarios, E03)
1. Migración con las tablas completas de docs/modelo-datos.md y `enable row level security`, sin
   políticas (supabase/migrations/…_e03_usuarios.sql).
2. Core en src/core/<modulo>/: modelos.py; la validación devuelve {campo: mensaje} y lanza
   ErrorDeValidacion (usuarios/alta.py); las grillas paginan con paginar() de src/core/paginacion.py
   (usuarios/busqueda.py). Core no hace commit: lo decide el controlador.
3. Controlador src/web/controllers/<modulo>.py: registrar el blueprint en src/web/__init__.py y la
   entrada del menú en MENU_POR_ROL (src/web/helpers/menu.py).
4. Vistas en templates/<modulo>/ con las macros de templates/macros/ (formularios.html,
   paginacion.html). Un form con `data-validar` y js/formularios.js valida también en el cliente.
5. tests/test_<modulo>.py: un test por episodio y el acceso de cada rol (fixtures de tests/conftest.py:
   login_como, usuario_rapido, crear_estudio…).

## Reglas del dominio
- Los nombres salen del LEL (docs/lel.md): estudio, muestra, sample set, turno de extracción…
- Los escenarios están en docs/escenarios.md (E01–E41): cada episodio es un criterio de aceptación.
- El estado de un estudio cambia SOLO con cambiar_estado() de src/core/estudios.
- Toda ruta lleva @login_required y @rol_requerido(...).
- Todo `<form method="post">` lleva `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
  (un fetch, el header X-CSRFToken). Sin token, el POST responde 400.

## Flujo de trabajo
- Un issue = una rama (e10-alta-estudio) = una sesión.
- Antes de dar algo por terminado: correr los tests y mostrar la salida.
- Commits en español que nombran el escenario: "E10: alta de estudio con genes de Apigen".
- IMPORTANT: nunca leer ni escribir .env, ni hardcodear claves.