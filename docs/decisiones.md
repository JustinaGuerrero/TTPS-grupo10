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
| O1 | **Patologías:** el cliente dice "cinco" pero enumera seis. | Se trabaja con seis: Fabry, Pompe, MPS 1, MPS 2, Gaucher y ASMD. El gerente médico puede dar de alta otras (E36). Ver O11: Apigen no tiene MPS 2. | LEL |
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

## Observaciones del modelo de datos

Las 11 observaciones que surgieron al armar [modelo-datos.md](modelo-datos.md) (12/11/2026). Siguen la numeración de las del LEL. Todos los supuestos los propone el equipo y están **pendientes de confirmar** con el cliente.

| # | Observación | Supuesto adoptado | Origen |
|---|---|---|---|
| O10 | **Mail único y hermanos menores:** `usuarios.email` es único. Dos hermanos menores que usan el mail del mismo responsable no pueden tener una cuenta cada uno, y en estas patologías hereditarias es un caso frecuente. | Cada paciente tiene su propio mail. La alternativa es que el paciente ingrese con su DNI. | Propuesto, a confirmar |
| O11 | **MPS 2 en Apigen:** el LEL nombra seis patologías (O1), pero Apigen v1 sacó MPS 2 y el gen IDS por pedido del profesor: la API responde "Patología inexistente". | Se cargan las 5 patologías base de Apigen. MPS 2 no se puede estudiar mientras Apigen no tenga el gen. | Propuesto, a confirmar |
| O12 | **Clasificaciones y resultados:** el LEL nombra tres clasificaciones (patogénica, benigna y VUS) y dos resultados (positivo y negativo). Apigen agrega la clasificación probablemente patogénica y el resultado portador. | El modelo usa los valores de Apigen. | Propuesto, a confirmar |
| O13 | **Genes de hallazgos secundarios en el presupuesto:** no se sabe si los genes ACMG cuentan como genes adicionales. | No cuentan: el presupuesto usa solo los genes del análisis inicial. | Propuesto, a confirmar |
| O14 | **Edad del Pompe urgente:** no se sabe en qué momento se mide la edad de "menor de 4 meses". | Se mide al dar de alta el estudio y la marca no cambia después, para no perder la prioridad a mitad del circuito. | Propuesto, a confirmar |
| O15 | **Tipo de descuento del cupón:** no se sabe si es un porcentaje o un monto fijo, y todavía no está el contrato del módulo de cupones en `docs/apis/`. | Porcentaje. Se ajusta con el contrato del módulo. | Propuesto, a confirmar |
| O16 | **Cobro a la obra social:** ningún escenario registra la transferencia de la obra social, así que la deuda por obra social nunca bajaría. | El asiento `cobro_obra_social` queda previsto. Falta definir quién lo registra y cuándo. | Propuesto, a confirmar |
| O17 | **Diagnóstico presuntivo de un segundo estudio:** se carga en el alta del paciente (E06) y los usuarios no pueden modificar sus datos. Si el paciente vuelve con otra sospecha, no está claro dónde se carga. | No hay un segundo estudio (O20): una sospecha nueva va por reanálisis del mismo estudio (E12), que la guarda en `analisis_patologias`. | Propuesto, a confirmar |
| O18 | **Estado con cobertura parcial:** si la obra social autoriza solo una parte (O3), ninguno de los 16 estados describe "autorizado, falta pagar la diferencia". | El estudio sigue en Pendiente de autorización, con la cobertura `autorizada`, hasta que el paciente paga la diferencia; recién entonces pasa a Habilitado para turno. La alternativa es un estado nuevo, que el cliente tendría que aprobar. | Propuesto, a confirmar |
| O19 | **Resultado de los genes agregados a mano:** Apigen calcula el resultado por patología, y los genes que agrega el médico tratante (E10 ep. 3, E12 ep. 3) no tienen patología ni herencia conocida. | Core aplica la regla de E35 ep. 1: positivo si hay una variante patogénica en esos genes y negativo si no. Nunca da portador. | Propuesto, a confirmar |
| O20 | **Un solo estudio por paciente:** el LEL dice que el paciente "puede tener más de un estudio en su historial", y E11 habla de historial de estudios. Pero el ADN no cambia, así que un segundo estudio repetiría la lectura del mismo exoma. | Cada paciente tiene un solo estudio (`estudios.paciente_id` único). Las sospechas nuevas van por reanálisis (E12) y las muestras que no sirven, por nueva extracción (E27), siempre en el mismo estudio. El historial de E11 muestra sus análisis. | Decisión del equipo, a confirmar |
