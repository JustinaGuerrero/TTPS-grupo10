---
name: guia-estudio
description: Genera el recorrido y la guía de estudio de un issue terminado, para preparar el coloquio
disable-model-invocation: true
---
Generá el recorrido y la guía de estudio del issue $ARGUMENTS (escenario E## del sistema de exoma clínico).

## Fuentes
- La rama actual contra develop: `git log --oneline develop..HEAD`, `git diff --stat develop...HEAD` y el diff completo.
- El escenario en docs/escenarios.md, los términos en docs/lel.md y el modelo en docs/modelo-datos.md.
- Las migraciones nuevas en sistema/supabase/migrations y los contratos de docs/apis/ que se usen.
- Si existe docs/teoria/, citá clase y diapositiva en cada paso de estudio. Si no, nombrá el concepto teórico sin inventar números de diapositiva.

## Reglas
- No modifiques código del sistema. Lo único que escribís es el documento.
- Todo lo que afirmes sale del diff, de los tests o de la especificación. Lo que no puedas confirmar va como "Pendiente de confirmar".
- Corré `poetry run pytest -q` desde sistema/ y usá los números reales (tests nuevos, total, pasados, omitidos).
- Para la sección de tests, hacé de 3 a 5 mutaciones: rompé a propósito una regla, corré los tests, anotá qué test falla y restaurá con `git restore`. Al terminar, `git status` solo puede mostrar el documento nuevo.

## Documento: docs/estudio/$ARGUMENTS.md

1. **Objetivo y cómo usar este documento:** qué escenario implementa; rama, commits y números del cambio (archivos, líneas, tests); cómo leerlo; criterio (poder explicar en el coloquio el código generado por un agente); pendientes.
2. **Mapa de los cambios:** árbol de archivos marcados NUEVO/MODIFICADO con una línea cada uno, y una tabla Archivo | Capa MVC (Modelo, Controlador, Vista, Integración, Migración, Pruebas) | Cambio (+/− líneas) | Responsabilidad. Aclará si hay migraciones nuevas y si hay que aplicarlas con `npx supabase db push`.
3. **Qué pide el escenario y dónde se cumple:** una tabla Regla | Origen (episodio E##.n, símbolo del LEL o decisión del grupo) | Dónde se cumple (función o ruta) | Test que la verifica. Incluí los cambios de estado del estudio (estado origen → destino, vía `cambiar_estado()`), los roles con acceso y las llamadas a APIs externas. Después, las reglas que no están en la especificación y decidió el grupo, y qué observación abierta del LEL se resolvió y cómo.
4. **Recorrido archivo por archivo,** en orden de dependencias: modelo (core) → integraciones → controlador → vistas → migración → pruebas. Para cada archivo: qué se agregó, para qué, y los detalles técnicos que hay que entender (transacciones y commit, flush, permisos y roles, timeouts y mocks de APIs, PRG, validaciones). Usá tablas de funciones (Nueva/Modificada | Qué hace) y de rutas (Método | Ruta | Endpoint | Rol).
5. **Flujo de punta a punta:** un diagrama Mermaid del caso principal, de la vista al modelo y de vuelta, con los rechazos posibles (sin permiso, regla de negocio, error de API externa) y el cambio de estado.
6. **Decisiones de diseño y observaciones:** decisiones a validar con el grupo, supuestos del LEL adoptados, bugs encontrados al implementar, lo que no se implementó y por qué, y lo visto fuera de alcance.
7. **Guía de estudio paso a paso:** de 4 a 7 pasos, en el orden en que cada pieza se apoya en la anterior. Cada paso tiene **Leer** (teoría o especificación), **Recorrer** (archivos y funciones, en orden) y **Explicar** (de 2 a 4 preguntas concretas sobre ese código). Cerrá con un ejercicio sin mirar el código: escribir qué pasa, capa por capa, en el caso principal del escenario.
8. **Comandos para reproducir y verificar,** para PowerShell en Windows: ver los cambios (`git log`/`git diff` contra develop), instalar (`poetry install`), correr los tests con el resultado esperado, aplicar migraciones si hay, probar a mano (usuario de prueba, rol y pasos en el navegador) y los experimentos de mutación con el test que falla en cada uno.
9. **Glosario y autoevaluación:** una tabla Término | Significado en este proyecto | Dónde verlo (términos del LEL y técnicos que aparecen en el issue), y de 8 a 10 preguntas de autoevaluación que remitan al paso de la sección 7 donde se responden.

Escribí en español, con oraciones cortas y sin relleno. Cuando termines, mostrá la salida de pytest y el resultado de las mutaciones.