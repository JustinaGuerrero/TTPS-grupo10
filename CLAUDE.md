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