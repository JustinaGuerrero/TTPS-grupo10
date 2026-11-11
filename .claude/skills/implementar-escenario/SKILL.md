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