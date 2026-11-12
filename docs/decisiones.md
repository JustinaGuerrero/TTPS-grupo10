# Decisiones del proyecto

Registro de decisiones del sistema de exoma clínico (TTPS 2026, grupo 10).
Cada decisión vale hasta que el equipo o el cliente la cambie; al cambiarla, se edita acá y se anota la fecha.

## Decisiones de stack

Tomadas de [guia-agentes.md](guia-agentes.md) ("Decisiones ya tomadas", "Sprint 0") y de `CLAUDE.md`.

| # | Tema | Decisión |
|---|---|---|
| S1 | Framework y patrón | Flask 3 con MVC: vistas en Jinja2 + Bootstrap. El profesor confirmó el 11/11 que Flask MVC con Jinja está bien, aunque su lista de soporte nombra MVC solo con Django. |
| S2 | Lenguaje y dependencias | Python 3.12 con Poetry. Las versiones las resuelve `poetry add`; no se escriben a mano. |
| S3 | Base de datos | PostgreSQL en Supabase: proyecto propio, separado del de Apigen, en la región São Paulo. Conexión por *Session pooler* en `DATABASE_URL`. |
| S4 | Esquema | Se define solo con migraciones SQL en `sistema/supabase/migrations` (sin `create_all`), con RLS activado en todas las tablas y sin políticas. Las aplica una persona con `npx supabase db push`. |
| S5 | Acceso a datos | SQLAlchemy 2 + Flask-SQLAlchemy-Lite (no es Flask-SQLAlchemy) + `psycopg[binary]`. |
| S6 | Sesión y autenticación | Flask-Session (sesión en el servidor, con `cachelib`) y hash scrypt de Werkzeug. Decoradores `login_required` y `rol_requerido(*roles)`; toda ruta los lleva. |
| S7 | Frontend | Bootstrap 5 servido localmente, `layout.html` responsivo con menú según el rol y mensajes flash. |
| S8 | Arquitectura | Modelo en `src/core/<modulo>/` (sin Flask ni request), controlador en `src/web/controllers/<modulo>.py` (un blueprint por módulo), vista en `src/web/templates/<modulo>/`. Módulo de referencia: usuarios (E03). |
| S9 | Estados del estudio | Enum con los 16 estados; el estado cambia solo con `cambiar_estado()` de `src/core/estudios`, que permite solo las transiciones del LEL y guarda cada cambio con fecha y usuario. |
| S10 | Integraciones | `httpx`; un cliente por API en `src/integraciones/<api>.py` con timeout de 5 s, errores legibles y modo mock (`USE_MOCKS=1`). `apigen/` es nuestra API (módulo 5) y no se modifica desde el sistema. |
| S11 | Notificaciones | `notificar(usuario, asunto, mensaje, link)` guarda el aviso y manda el mail con `flask-mail`; en desarrollo sale por consola. No se usan WhatsApp ni SMS. |
| S12 | Otras librerías | `apscheduler` (orden del día y recordatorios), `xhtml2pdf` (PDFs desde Jinja), `openpyxl` (Excel del CCB), `supabase` (PDFs en Storage), `python-dotenv` (`.env`). |
| S13 | Calidad | pytest con base de test separada (`DATABASE_URL_TEST`, nunca la compartida), `ruff` como linter y GitHub Action que corre los tests en cada PR. |
| S14 | Agente | Claude Code con `CLAUDE.md`, permisos del equipo en `.claude/settings.json` (`.env` bloqueado; migraciones y push piden aprobación) y MCP de Supabase en solo lectura, limitado al proyecto. |
| S15 | Seguridad y datos | Las claves solo en `.env` (con `.env.example` versionado); nunca datos reales de pacientes, solo los de los seeds. |
| S16 | Flujo de trabajo | Un issue = una rama (`e10-alta-estudio`) = una sesión. Commits en español que nombran el escenario. Nadie mergea un PR que otro no leyó. |

## Observaciones abiertas del LEL

Las 9 observaciones de la sección "Observaciones a validar con el cliente" de [lel.md](lel.md).
Donde el LEL ya adopta un supuesto, se mantiene; donde solo deja una pregunta, el supuesto es propuesto por el equipo y está **pendiente de confirmar** con el cliente.

| # | Observación | Supuesto adoptado | Origen |
|---|---|---|---|
| O1 | **Patologías:** el cliente dice "cinco" pero enumera seis. | Se trabaja con seis: Fabry, Pompe, MPS 1, MPS 2, Gaucher y ASMD. El gerente médico puede dar de alta otras (E36). | LEL |
| O2 | **Validación del diagnóstico presuntivo** con sospecha familiar sin síntomas. | La regla (síntoma cardinal o dos secundarios, E08) se aplica solo con tipo de sospecha clínica. Con sospecha familiar se acepta el alta sin validar síntomas, siempre que haya al menos un familiar con diagnóstico confirmado de la patología. | Propuesto, a confirmar |
| O3 | **Cobertura parcial:** ¿el paciente paga la diferencia antes del turno? | Sí. Con la autorización, el sistema calcula la diferencia; si es mayor a cero, el estudio queda habilitado para turno recién cuando el paciente la paga (mismo flujo de E14). Ambos importes van al registro financiero (E41). | Propuesto, a confirmar |
| O4 | **Volumen de la muestra:** quién registra los mililitros. | El administrativo, al recibir la muestra en el laboratorio central (E26). | LEL |
| O5 | **Datos crudos:** quién los carga. | El administrativo los carga en el sistema, como hacía con el PDF de Corea (E32). | LEL |
| O6 | **Resultado del estudio:** cómo se genera. | El sistema genera el PDF con la plantilla a partir de las variantes registradas (E35). | LEL |
| O7 | **Inasistencia al turno:** cómo se detecta y quién vuelve el estudio a Habilitado para turno. | Si al cierre del día del turno no llegó el mensaje de muestra tomada (E22), el sistema libera el turno y vuelve el estudio a Habilitado para turno, notificando al paciente. No se penaliza; la pérdida del pago a la quinta inasistencia no se implementa. | Propuesto, a confirmar |
| O8 | **Reanálisis:** costo y registro. | Se registra en el mismo estudio (vuelve a En área de bioinformática, E12) y no tiene costo. | Propuesto, a confirmar |
| O9 | **Nombres de estados:** el cliente nombró solo siete. | Se usan los 16 estados del LEL; los no nombrados por el cliente quedan como propuestos. | LEL |

### Inconsistencia detectada en la conversión

El diagrama del ciclo de vida del estudio en el LEL (`img/ciclo-de-vida-del-estudio.png`) se titula "El estudio avanza por 13 estados", mientras que el texto dice 16 y el diagrama dibuja 16. Se toma como válido **16**.
