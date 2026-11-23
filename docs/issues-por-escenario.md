# Issues por escenario

Una issue por escenario, de E01 a E45. Reemplaza el reparto de la guía, donde una issue juntaba
dos o tres escenarios. Lo carga en GitHub `scripts/issues-por-escenario.ps1` (ver abajo).

**Estado al 22/11:** 32 escenarios hechos y mergeados en `development`, 13 por hacer.

| Escenario | Título | Estado | Responsable | PR | Issue |
|---|---|---|---|---|---|
| E01 | Registrarse como médico tratante o gerente médico | Hecho | Integrante 2 | #46 | #30 (la de antes) |
| E02 | Registrarse como administrativo o bioinformático | Hecho | Integrante 2 | #46 | #66 (nueva; antes en #30) |
| E03 | Dar de alta usuario | Hecho | Integrante 1 | #22 | #24 (la de antes) |
| E04 | Iniciar sesión | Hecho | Integrante 2 | #55 | #37 (la de antes) |
| E05 | Activar cuenta del paciente | Hecho | Integrante 2 | #55 | #67 (nueva; antes en #37) |
| E06 | Dar de alta paciente | Hecho | Integrante 2 | #51 | #31 (la de antes) |
| E07 | Buscar síntoma | Hecho | Integrante 2 | #45 | #25 (la de antes) |
| E08 | Validar diagnóstico presuntivo | Hecho | Integrante 2 | #45 | #68 (nueva; antes en #25) |
| E09 | Registrar familiograma | Hecho | Integrante 2 | #51 | #69 (nueva; antes en #31) |
| E10 | Dar de alta estudio | Hecho | Integrante 3 | #53 | #32 (la de antes) |
| E11 | Consultar historial de estudios | Hecho | Integrante 1 | #50 | #26 (la de antes) |
| E12 | Solicitar reanálisis | **Falta** | Integrante 4 | — | #42 (la de antes) |
| E13 | Emitir presupuesto | Hecho | Integrante 3 | #47 | #27 (la de antes) |
| E14 | Pagar estudio | Hecho | Integrante 3 | #47 | #70 (nueva; antes en #27) |
| E15 | Aplicar cupón | Hecho | Integrante 3 | #49 | #33 (la de antes) |
| E16 | Solicitar cobertura de obra social | Hecho | Integrante 4 | #54, #63, #64 | #38 (la de antes) |
| E17 | Autorizar cobertura | Hecho | Integrante 4 | #54, #63, #64 | #71 (nueva; antes en #38) |
| E18 | Solicitar reautorización | Hecho | Integrante 4 | #54, #63, #64 | #72 (nueva; antes en #38) |
| E19 | Reservar turno de extracción | Hecho | Integrante 4 | #52 | #28 (la de antes) |
| E20 | Cancelar turno | Hecho | Integrante 4 | #52 | #73 (nueva; antes en #28) |
| E21 | Recordar turno | Hecho | Integrante 4 | #52 | #74 (nueva; antes en #28) |
| E22 | Registrar toma de muestra | Hecho | Integrante 1 | #56, #57 | #29 (la de antes) |
| E23 | Generar orden del día | Hecho | Integrante 4 | #58, #65 | #34 (la de antes) |
| E24 | Retirar muestras | Hecho | Integrante 4 | #58, #65 | #75 (nueva; antes en #34) |
| E25 | Seguir ubicación de la muestra | **Falta** | Integrante 3 | — | #39 (la de antes) |
| E26 | Registrar llegada al laboratorio central | **Falta** | Integrante 3 | — | #76 (nueva; antes en #39) |
| E27 | Solicitar nueva extracción | Hecho | Integrante 4 | #59 | #36 (la de antes) |
| E28 | Armar sample set | **Falta** | Integrante 1 | — | #35 (la de antes) |
| E29 | Solicitar autorización ministerial | **Falta** | Integrante 1 | — | #77 (nueva; antes en #35) |
| E30 | Programar retiro | **Falta** | Integrante 3 | — | #40 (la de antes) |
| E31 | Despachar sample set | **Falta** | Integrante 3 | — | #78 (nueva; antes en #40) |
| E32 | Cargar datos crudos | Hecho | Integrante 4 | #59 | #79 (nueva; antes en #36) |
| E33 | Tomar estudio | Hecho | Integrante 4 | #59 | #80 (nueva; antes en #36) |
| E34 | Registrar variante | **Falta** | Integrante 2 | — | #41 (la de antes) |
| E35 | Informar resultado | **Falta** | Integrante 2 | — | #81 (nueva; antes en #41) |
| E36 | Dar de alta patología | Hecho | Integrante 2 | #45 | #82 (nueva; antes en #25) |
| E37 | Generar cupón | Hecho | Integrante 3 | #49 | #83 (nueva; antes en #33) |
| E38 | Asignar cupón | Hecho | Integrante 3 | #49 | #84 (nueva; antes en #33) |
| E39 | Notificar | **Falta** (la base está hecha; falta el módulo de avisos) | Integrante 3 | #22 (base) | #85 (nueva; antes en #24) |
| E40 | Consultar chatbot | Hecho | Integrante 1 | #50 | #86 (nueva; antes en #26) |
| E41 | Registrar operación financiera | Hecho | Integrante 3 | #47 | #87 (nueva; antes en #27) |
| E42 | Modificar datos del paciente | **Falta** | Integrante 1 | — | #44 (la de antes) |
| E43 | Registrar cambios | Hecho | Integrante 3 | #48 | #43 (la de antes) |
| E44 | Sugerir patología con el CDSS | **Falta** | Integrante 2 | — | #60 (la de antes) |
| E45 | Elegir la estrategia del CDSS | **Falta** | Integrante 2 | — | #88 (nueva; antes en #60) |

«La de antes»: la issue vieja se editó y quedó solo con ese escenario. «Nueva»: se creó una issue
para ese escenario el 23/11, con el número que seguía en GitHub (no se puede empezar de #1, porque
los números los comparten las issues y los PR). El número que ordena es el del escenario, que va al
principio del título: «E19 · Reservar turno de extracción».

Cambios respecto de la guía:

- «Avisos por el módulo de avisos» (E39) y «Autorización de la obra social desde su módulo» (E16 y
  E17) eran ampliaciones de un escenario que ya tenía issue: se unifican en E39 y E16/E17. Si
  existen en GitHub, el script las cierra con un comentario que dice dónde quedaron.
- E39 queda abierta: la base mandó los avisos por mail (PR #22), pero falta el módulo de avisos.
- «Base: estructura, base de datos y login» no es un escenario: queda como está.
- E42, E44 y E45 todavía no están en `docs/escenarios.md`; sus criterios salen de la guía.

## Cómo cargarlo en GitHub

Desde la raíz del repo, con `gh auth login` hecho con tu cuenta (todo queda a tu nombre):

```powershell
gh auth status
powershell -ExecutionPolicy Bypass -File scripts/issues-por-escenario.ps1 -Prueba
powershell -ExecutionPolicy Bypass -File scripts/issues-por-escenario.ps1
```

Con `-Prueba` muestra lo que haría sin tocar nada. En su paso 2, cada issue de la guía tiene que
aparecer con su número (#24, #25…); la única que puede faltar es la del CDSS, si nunca se cargó. Si
falta otra, el script avisa y pregunta antes de seguir, porque crearía sus escenarios de cero.

Sin `-Prueba`:

1. Crea los labels y milestones que falten.
2. Edita cada issue vieja para que quede con su primer escenario (título, cuerpo, labels y
   milestone) y crea una issue nueva por cada escenario que le sobraba.
3. Cierra las de escenarios hechos (con el PR en el comentario) y deja abiertas las que faltan.
4. Comenta en cada issue vieja a qué número pasó cada escenario.
5. Deja la correspondencia escenario → número en `scripts/issues-por-escenario.csv`.

Si se corta a la mitad, se puede volver a correr: reconoce las issues que ya convirtió por el
escenario del título y no duplica nada.
