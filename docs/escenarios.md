# Escenarios – Sistema de gestión de exoma clínico

Oct 8, 2026 · @Someone

# Introducción

El documento reúne 41 escenarios que cubren los requerimientos relevados en la entrevista, escritos con el modelo de escenarios de Leite y el vocabulario del LEL del sistema.

Convenciones usadas:

- Cada escenario tiene Título, Objetivo, Contexto, Actores, Recursos y Episodios.
- El Contexto indica la ubicación, el momento, las precondiciones y las restricciones del escenario.
- Los actores son sujetos del LEL y los recursos son objetos del LEL. Los estados del LEL se escriben con mayúscula inicial (por ejemplo, Turno sacado).
- Cada escenario tiene entre 3 y 6 episodios. Las alternativas se escriben como episodios condicionales ("Si…") y las referencias a otros escenarios van en MAYÚSCULAS.
- Cuando el paciente es menor, el responsable del paciente menor realiza en su nombre los escenarios del paciente.
- Restricciones generales: el sistema opera solo en el laboratorio central, es responsivo (computadora y celular), trabaja de lunes a viernes de 9 a 18 sin feriados y debe proteger los datos genéticos de los pacientes.
- Los supuestos son los mismos que figuran en la sección Observaciones del LEL.

| N.° | Escenario | Actor principal |
|---|---|---|
| E01 | Registrarse como médico tratante o gerente médico | Médico tratante, gerente médico |
| E02 | Registrarse como administrativo o bioinformático | Administrativo, bioinformático |
| E03 | Dar de alta usuario | Administrador general |
| E04 | Iniciar sesión | Usuario |
| E05 | Activar cuenta del paciente | Paciente |
| E06 | Dar de alta paciente | Médico tratante |
| E07 | Buscar síntoma | Médico tratante, gerente médico |
| E08 | Validar diagnóstico presuntivo | Sistema |
| E09 | Registrar familiograma | Médico tratante |
| E10 | Dar de alta estudio | Médico tratante |
| E11 | Consultar historial de estudios | Médico tratante, paciente |
| E12 | Solicitar reanálisis | Médico tratante |
| E13 | Emitir presupuesto | Administrativo |
| E14 | Pagar estudio | Paciente |
| E15 | Aplicar cupón | Paciente |
| E16 | Solicitar cobertura de obra social | Paciente |
| E17 | Autorizar cobertura | Administrativo |
| E18 | Solicitar reautorización | Paciente |
| E19 | Reservar turno de extracción | Paciente |
| E20 | Cancelar turno | Paciente |
| E21 | Recordar turno | Sistema |
| E22 | Registrar toma de muestra | Centro de extracción |
| E23 | Generar orden del día | Sistema |
| E24 | Retirar muestras | Transportista |
| E25 | Seguir ubicación de la muestra | Administrativo |
| E26 | Registrar llegada al laboratorio central | Transportista |
| E27 | Solicitar nueva extracción | Administrativo |
| E28 | Armar sample set | Sistema |
| E29 | Solicitar autorización ministerial | Sistema |
| E30 | Programar retiro | Administrativo |
| E31 | Despachar sample set | FedEx |
| E32 | Cargar datos crudos | Administrativo |
| E33 | Tomar estudio | Bioinformático |
| E34 | Registrar variante | Bioinformático |
| E35 | Informar resultado | Sistema |
| E36 | Dar de alta patología | Gerente médico |
| E37 | Generar cupón | Gerente médico |
| E38 | Asignar cupón | Médico tratante |
| E39 | Notificar | Sistema |
| E40 | Consultar chatbot | Paciente |
| E41 | Registrar operación financiera | Sistema |

# 1. Acceso y usuarios

## E01 · Registrarse como médico tratante o gerente médico

**Título:** Registrarse como médico tratante o gerente médico.

**Objetivo:** Que el médico tratante o el gerente médico obtenga acceso al sistema con su rol.

**Contexto:** Sitio del sistema, desde computadora o celular, en cualquier momento.
- **Precondición:** la persona no está registrada.
- **Restricción:** se asume que la matrícula ingresada es correcta.

**Actores:** Médico tratante, Gerente médico, Sistema.

**Recursos:** Credenciales de acceso, Módulo SNOMED.

**Episodios:**

1. El médico tratante o el gerente médico completa matrícula, nombre, apellido, teléfono y mail.
2. El médico tratante o el gerente médico selecciona sus especialidades desde el módulo SNOMED.
3. El médico tratante o el gerente médico indica su rol.
4. El sistema crea las credenciales de acceso con el rol indicado.

## E02 · Registrarse como administrativo o bioinformático

**Título:** Registrarse como administrativo o bioinformático.

**Objetivo:** Que el administrativo o el bioinformático obtenga acceso al sistema con su rol.

**Contexto:** Laboratorio central, en cualquier momento.
- **Precondición:** la persona no está registrada.

**Actores:** Administrativo, Bioinformático, Sistema.

**Recursos:** Credenciales de acceso, Notificación, Datos crudos.

**Episodios:**

1. El administrativo o el bioinformático completa nombre, apellido, teléfono y mail.
2. El administrativo o el bioinformático indica su rol.
3. El sistema crea las credenciales de acceso con el rol indicado.
4. Si el rol es bioinformático, el sistema lo agrega a los destinatarios de las notificaciones de datos crudos.

## E03 · Dar de alta usuario

**Título:** Dar de alta usuario.

**Objetivo:** Centralizar la gestión de usuarios como alternativa al auto registro.

**Contexto:** Laboratorio central, en cualquier momento.
- **Precondición:** el administrador general inició sesión.
- **Restricción:** por ahora los usuarios no pueden darse de baja ni modificar sus datos.

**Actores:** Administrador general, Usuario, Sistema.

**Recursos:** Credenciales de acceso, Notificación.

**Episodios:**

1. El administrador general elige el rol del nuevo usuario: médico tratante, gerente médico, administrativo, bioinformático o transportista.
2. El administrador general completa los datos que corresponden al rol.
3. El sistema crea las credenciales de acceso.
4. El sistema envía al nuevo usuario una notificación por mail con sus credenciales de acceso.

## E04 · Iniciar sesión

**Título:** Iniciar sesión.

**Objetivo:** Acceder al sistema protegiendo los datos genéticos de los pacientes.

**Contexto:** Cualquier dispositivo, computadora o celular, en cualquier momento.
- **Precondición:** el usuario tiene credenciales de acceso activas.

**Actores:** Usuario, Sistema.

**Recursos:** Credenciales de acceso.

**Episodios:**

1. El usuario ingresa su usuario y su contraseña.
2. El sistema valida las credenciales de acceso.
3. Si las credenciales no son válidas, el sistema rechaza el ingreso.
4. Si el dispositivo o la red son nuevos, el sistema envía un código de verificación al mail del usuario.
5. Si recibió un código, el usuario ingresa el código de verificación.
6. El sistema muestra la vista que corresponde al rol del usuario.

## E05 · Activar cuenta del paciente

**Título:** Activar cuenta del paciente.

**Objetivo:** Que el paciente reemplace la contraseña provisoria y acceda a su vista.

**Contexto:** Vista del paciente, en su primer ingreso.
- **Precondición:** el médico tratante dio de alta al paciente.

**Actores:** Paciente, Sistema.

**Recursos:** Credenciales de acceso, Notificación, Estudio.

**Episodios:**

1. El paciente recibe por mail su usuario y su contraseña provisoria.
2. El paciente ingresa al sistema con las credenciales provisorias.
3. El sistema solicita el cambio de contraseña.
4. El paciente define una contraseña nueva.
5. El sistema habilita la vista del paciente con sus estudios y sus avisos.

# 2. Alta clínica y estudio

## E06 · Dar de alta paciente

**Título:** Dar de alta paciente.

**Objetivo:** Registrar al paciente durante la consulta médica, porque puede que no vuelva.

**Contexto:** Consultorio del médico tratante, durante la consulta inicial.
- **Precondición:** el médico tratante inició sesión y el paciente no existe en el sistema.
- **Restricción:** todos los datos son obligatorios salvo el familiograma.

**Actores:** Médico tratante, Paciente, Sistema.

**Recursos:** Diagnóstico presuntivo, Patología lisosomal, Tipo de sospecha, Resumen de historia clínica, Síntoma, Familiograma, Credenciales de acceso.

**Episodios:**

1. El médico tratante carga DNI, nombre, apellido, fecha de nacimiento, teléfono y mail del paciente.
2. El médico tratante registra el diagnóstico presuntivo, con una o más patologías lisosomales, y el tipo de sospecha.
3. El médico tratante graba el resumen de historia clínica y el sistema lo transcribe a texto.
4. El médico tratante carga la lista de síntomas del paciente mediante BUSCAR SÍNTOMA.
5. Si el paciente informa familiares, el médico tratante realiza REGISTRAR FAMILIOGRAMA.
6. El sistema realiza VALIDAR DIAGNÓSTICO PRESUNTIVO y, si es válido, envía las credenciales de acceso al paciente.

## E07 · Buscar síntoma

**Título:** Buscar síntoma.

**Objetivo:** Que todos los médicos codifiquen los síntomas de igual forma, con la terminología SNOMED.

**Contexto:** Consultorio del médico tratante o laboratorio central, mientras se cargan los síntomas de un paciente, un familiar o una patología.
- **Precondición:** está en curso DAR DE ALTA PACIENTE, REGISTRAR FAMILIOGRAMA o DAR DE ALTA PATOLOGÍA.
- **Restricción:** los síntomas no se cargan como texto libre; el médico tratante o el gerente médico escribe parte del término y elige uno de SNOMED.

**Actores:** Médico tratante, Gerente médico, Sistema.

**Recursos:** Síntoma, Módulo SNOMED.

**Episodios:**

1. El médico tratante o el gerente médico escribe parte del síntoma.
2. El sistema consulta el módulo SNOMED a medida que se escribe.
3. El sistema muestra los términos que coinciden con lo escrito.
4. El médico tratante o el gerente médico elige el síntoma.
5. El sistema agrega el síntoma a la lista.

## E08 · Validar diagnóstico presuntivo

**Título:** Validar diagnóstico presuntivo.

**Objetivo:** Impedir el alta de un paciente cuyo diagnóstico presuntivo no coincide con sus síntomas.

**Contexto:** Consultorio del médico tratante, durante DAR DE ALTA PACIENTE.
- **Precondición:** cada patología lisosomal tiene definidos su síntoma cardinal y sus síntomas secundarios.
- **Restricción:** el sistema no infiere la patología; solo controla la que eligió el médico tratante.

**Actores:** Sistema, Médico tratante.

**Recursos:** Diagnóstico presuntivo, Síntoma, Patología lisosomal.

**Episodios:**

1. El sistema obtiene el síntoma cardinal y los síntomas secundarios de cada patología del diagnóstico presuntivo.
2. El sistema compara esos síntomas con la lista de síntomas del paciente.
3. Si el paciente presenta el síntoma cardinal o al menos dos síntomas secundarios, el sistema acepta el alta.
4. Si no se cumple la regla, el sistema rechaza el alta.
5. Si rechaza el alta, el sistema informa la inconsistencia al médico tratante.
6. Si se rechazó el alta, el médico tratante corrige el diagnóstico presuntivo o la lista de síntomas.

## E09 · Registrar familiograma

**Título:** Registrar familiograma.

**Objetivo:** Identificar familiares con riesgo aumentado a los que conviene estudiar.

**Contexto:** Consultorio del médico tratante, durante DAR DE ALTA PACIENTE.
- **Precondición:** el paciente acepta informar a sus familiares.
- **Restricción:** es opcional; si el paciente no informa familiares, la sección queda vacía.

**Actores:** Médico tratante, Sistema.

**Recursos:** Familiar, Familiograma, API de familiograma, Síntoma, Patología lisosomal.

**Episodios:**

1. El médico tratante da de alta un familiar con su parentesco y su nombre.
2. El médico tratante carga los síntomas del familiar mediante BUSCAR SÍNTOMA.
3. El médico tratante indica si el familiar tiene diagnóstico de alguna patología lisosomal.
4. El médico tratante repite los episodios anteriores por cada familiar.
5. El sistema envía los familiares a la API de familiograma.
6. El sistema asocia al paciente el familiograma en PDF devuelto.

## E10 · Dar de alta estudio

**Título:** Dar de alta estudio.

**Objetivo:** Iniciar el circuito del exoma clínico para un paciente.

**Contexto:** Consultorio del médico tratante, durante la consulta con el paciente.
- **Precondición:** el médico tratante inició sesión.
- **Restricción:** solo un médico tratante puede dar de alta un estudio, y los estudios se atienden por orden de llegada, salvo los Pompe urgentes, que tienen prioridad.

**Actores:** Médico tratante, Administrativo, Sistema.

**Recursos:** Estudio, Gen, Hallazgo secundario, Diagnóstico presuntivo, API de bioinformática, Presupuesto.

**Episodios:**

1. El médico tratante selecciona al paciente; si no existe, realiza DAR DE ALTA PACIENTE.
2. El sistema obtiene de la API de bioinformática los genes asociados al diagnóstico presuntivo.
3. Si sospecha otra causa, el médico tratante agrega genes manualmente.
4. El médico tratante indica si el estudio evalúa hallazgos secundarios.
5. El sistema registra el estudio en estado Creado y avisa al administrativo para emitir el presupuesto.

## E11 · Consultar historial de estudios

**Título:** Consultar historial de estudios.

**Objetivo:** Ver los estudios de un paciente y el estado de cada uno.

**Contexto:** Vista del médico tratante o del paciente, en cualquier momento.
- **Precondición:** el paciente tiene al menos un estudio.
- **Restricción:** el paciente solo ve sus propios estudios.

**Actores:** Médico tratante, Paciente, Sistema.

**Recursos:** Estudio, Resultado del estudio.

**Episodios:**

1. El médico tratante o el paciente accede al historial de estudios del paciente.
2. El sistema muestra cada estudio con su estado actual.
3. El médico tratante o el paciente selecciona un estudio.
4. El sistema muestra el detalle del estudio y, si está Finalizado, el resultado del estudio.

## E12 · Solicitar reanálisis

**Título:** Solicitar reanálisis.

**Objetivo:** Analizar otros genes del mismo exoma sin nueva extracción ni nueva lectura del ADN.

**Contexto:** Consultorio del médico tratante, en cualquier momento.
- **Precondición:** el paciente tiene un estudio Finalizado.

**Actores:** Médico tratante, Bioinformático, Sistema.

**Recursos:** Estudio, Gen, Patología lisosomal, Datos crudos, API de bioinformática, Notificación.

**Episodios:**

1. El médico tratante realiza CONSULTAR HISTORIAL DE ESTUDIOS.
2. El médico tratante selecciona un estudio finalizado.
3. El médico tratante elige la nueva patología lisosomal o los nuevos genes a analizar.
4. El sistema obtiene de la API de bioinformática los genes de la nueva patología lisosomal.
5. El sistema devuelve el estudio a En área de bioinformática, con los mismos datos crudos.
6. El sistema notifica a los bioinformáticos.

# 3. Presupuesto, pago y cobertura

## E13 · Emitir presupuesto

**Título:** Emitir presupuesto.

**Objetivo:** Informar al paciente el costo del estudio antes del pago.

**Contexto:** Laboratorio central, después de que el médico tratante da de alta el estudio y antes del pago.
- **Precondición:** el estudio está en estado Creado.
- **Restricción:** el precio es fijo y no se puede modificar.

**Actores:** Administrativo, Paciente, Sistema.

**Recursos:** Presupuesto, Estudio, Gen, Notificación.

**Episodios:**

1. El administrativo consulta los estudios en estado Creado.
2. El sistema calcula el importe: 500 USD hasta 5 genes y 30 USD por cada gen adicional, con la extracción incluida.
3. El administrativo emite el presupuesto del estudio.
4. El sistema publica el presupuesto en la vista del paciente y cambia el estudio a Presupuestado.
5. El sistema notifica al paciente por mail y por aviso.

## E14 · Pagar estudio

**Título:** Pagar estudio.

**Objetivo:** Pagar el estudio de forma particular para habilitar la reserva del turno.

**Contexto:** Vista del paciente.
- **Precondición:** el estudio está Presupuestado.
- **Restricción:** un único pago, sin cuotas; por ahora el pago es simulado.

**Actores:** Paciente, Sistema.

**Recursos:** Presupuesto, Pago, Cupón de descuento, Registro financiero, Estudio, Notificación.

**Episodios:**

1. El paciente consulta el presupuesto del estudio.
2. El paciente elige pagar de forma particular.
3. Si tiene un cupón de descuento, el paciente realiza APLICAR CUPÓN.
4. El paciente confirma el pago simulado por el importe final.
5. El sistema realiza REGISTRAR OPERACIÓN FINANCIERA.
6. El sistema cambia el estudio a Habilitado para turno y notifica al paciente.

## E15 · Aplicar cupón

**Título:** Aplicar cupón.

**Objetivo:** Descontar del presupuesto el beneficio que el médico tratante otorgó al paciente.

**Contexto:** Vista del paciente, durante PAGAR ESTUDIO.
- **Precondición:** el médico tratante asignó un cupón de descuento al paciente.

**Actores:** Paciente, Sistema.

**Recursos:** Cupón de descuento, Módulo de cupones, Presupuesto, Pago.

**Episodios:**

1. El paciente sube el PDF del cupón o ingresa su código.
2. El sistema consulta al módulo de cupones si el cupón está vigente.
3. Si el cupón no está vigente, el sistema lo rechaza.
4. Si rechaza el cupón, el sistema informa el rechazo al paciente.
5. Si el cupón está vigente, el sistema aplica el descuento al presupuesto.
6. Si se confirma el pago, el sistema informa al módulo de cupones el uso del cupón para que lo venza.

## E16 · Solicitar cobertura de obra social

**Título:** Solicitar cobertura de obra social.

**Objetivo:** Que la obra social del paciente cubra el estudio.

**Contexto:** Vista del paciente, después de que se emite el presupuesto, cuando el paciente decide usar su obra social.
- **Precondición:** el estudio está Presupuestado.

**Actores:** Paciente, Administrativo, Sistema.

**Recursos:** API de obras sociales, Presupuesto, Estudio, Notificación.

**Episodios:**

1. El paciente elige usar la cobertura de su obra social.
2. El sistema consulta la API de obras sociales y muestra las obras sociales con su porcentaje de cobertura.
3. El paciente selecciona su obra social.
4. El sistema cambia el estudio a Pendiente de autorización.
5. El sistema envía una notificación al administrativo para que solicite la autorización a la obra social.

## E17 · Autorizar cobertura

**Título:** Autorizar cobertura.

**Objetivo:** Registrar la respuesta de la obra social para que el estudio avance o quede rechazado.

**Contexto:** Laboratorio central.
- **Precondición:** el estudio está Pendiente de autorización.
- **Restricción:** el administrativo tramita la autorización con la obra social por teléfono, fuera del sistema; una autorización equivale a un pago, porque la obra social transfiere dentro de las 24 h.

**Actores:** Administrativo, Obra social, Paciente, Sistema.

**Recursos:** Estudio, Registro financiero, Notificación.

**Episodios:**

1. Si la obra social autoriza, el administrativo registra la autorización.
2. Ante una autorización, el sistema realiza REGISTRAR OPERACIÓN FINANCIERA.
3. Ante una autorización, el sistema cambia el estudio a Habilitado para turno.
4. Si la obra social rechaza, el administrativo registra el rechazo.
5. Ante un rechazo, el sistema cambia el estudio a Rechazado por obra social.
6. El sistema envía una notificación al paciente con la respuesta de la obra social.

## E18 · Solicitar reautorización

**Título:** Solicitar reautorización.

**Objetivo:** Destrabar un estudio rechazado cuando la justicia falla a favor del paciente.

**Contexto:** Vista del paciente.
- **Precondición:** el estudio está Rechazado por obra social y el paciente tiene una resolución judicial favorable.

**Actores:** Paciente, Administrativo, Sistema.

**Recursos:** Demanda de reautorización, Estudio, Notificación.

**Episodios:**

1. El paciente carga una demanda de reautorización asociada al estudio.
2. El paciente sube el PDF de la resolución judicial favorable.
3. El sistema cambia el estudio a Pendiente de autorización.
4. El sistema avisa al administrativo que hay una reautorización pendiente.
5. El administrativo realiza AUTORIZAR COBERTURA.

# 4. Turnos y extracción

## E19 · Reservar turno de extracción

**Título:** Reservar turno de extracción.

**Objetivo:** Que el paciente acuda a un centro de extracción a tomarse la muestra.

**Contexto:** Vista del paciente, una vez confirmado el pago o la autorización de la obra social, o cuando se solicita una nueva extracción.
- **Precondición:** el estudio está Habilitado para turno o en Requiere nueva extracción.
- **Restricción:** turnos de 15 minutos, un paciente por turno, de lunes a viernes de 9 a 18 y sin feriados.

**Actores:** Paciente, Sistema.

**Recursos:** Turno de extracción, Orden de extracción, Consentimiento informado, Mapa, Estudio.

**Episodios:**

1. El paciente consulta en un mapa los centros de extracción.
2. El paciente elige el centro de extracción que le queda más cerca.
3. El sistema muestra los turnos libres de ese centro.
4. El paciente reserva un turno libre.
5. El sistema cambia el estudio a Turno sacado.
6. El sistema envía al paciente la orden de extracción y el consentimiento informado.

## E20 · Cancelar turno

**Título:** Cancelar turno.

**Objetivo:** Liberar un turno al que el paciente no puede asistir.

**Contexto:** Vista del paciente, en cualquier momento antes de la fecha del turno.
- **Precondición:** el estudio está en Turno sacado.
- **Restricción:** cancelar no tiene costo y la inasistencia no se penaliza.

**Actores:** Paciente, Sistema.

**Recursos:** Turno de extracción, Turnero, Estudio.

**Episodios:**

1. El paciente consulta su turno de extracción.
2. El paciente cancela el turno.
3. El sistema libera el turno en el turnero del centro de extracción.
4. El sistema cambia el estudio a Habilitado para turno.
5. El paciente realiza RESERVAR TURNO DE EXTRACCIÓN cuando pueda asistir.

## E21 · Recordar turno

**Título:** Recordar turno.

**Objetivo:** Evitar que el paciente olvide su turno de extracción.

**Contexto:** Antes de la fecha del turno.
- **Precondición:** el estudio está en Turno sacado.

**Actores:** Sistema, Paciente.

**Recursos:** Turno de extracción, Notificación.

**Episodios:**

1. El sistema identifica los turnos de extracción próximos.
2. El sistema envía al paciente un recordatorio por mail con la fecha, la hora y el centro de extracción.
3. El sistema publica el recordatorio en la lista de avisos del paciente.

## E22 · Registrar toma de muestra

**Título:** Registrar toma de muestra.

**Objetivo:** Informar al laboratorio central, sin intervención de personas, que la muestra está lista para retirar.

**Contexto:** Centro de extracción, de lunes a viernes de 9 a 18.
- **Precondición:** el estudio está en Turno sacado y el paciente asiste.
- **Restricción:** el centro de extracción no opera el sistema.

**Actores:** Paciente, Centro de extracción, Sistema.

**Recursos:** Muestra, Orden de extracción, Consentimiento informado, Bot de mensajería, Estudio, Orden del día.

**Episodios:**

1. El paciente presenta la orden de extracción.
2. El paciente entrega el consentimiento informado firmado.
3. El centro de extracción toma la muestra de sangre.
4. El centro de extracción envía el mensaje de muestra tomada al bot de mensajería.
5. El sistema cambia el estudio a Listo para retirar.
6. El sistema incluye el centro de extracción en la próxima orden del día de su provincia.

# 5. Logística de muestras

## E23 · Generar orden del día

**Título:** Generar orden del día.

**Objetivo:** Que cada transportista sepa qué centros de extracción visitar y en qué orden.

**Contexto:** Cada mañana hábil, de lunes a viernes y sin feriados.
- **Precondición:** existe al menos un estudio Listo para retirar.
- **Restricción:** el orden del recorrido es fijo y no se puede modificar.

**Actores:** Sistema, Transportista.

**Recursos:** Orden del día, Módulo de optimización de recorridos, Estudio.

**Episodios:**

1. El sistema reúne, por provincia, los centros de extracción con estudios Listo para retirar.
2. El sistema envía las direcciones de esos centros al módulo de optimización de recorridos.
3. El sistema recibe el orden del recorrido.
4. El sistema asigna la orden del día al transportista de la provincia.
5. El transportista recibe la orden del día.

## E24 · Retirar muestras

**Título:** Retirar muestras.

**Objetivo:** Trasladar las muestras desde los centros de extracción al laboratorio central.

**Contexto:** Centros de extracción de la provincia, durante el recorrido.
- **Precondición:** el transportista recibió la orden del día.
- **Restricción:** no hay límite de muestras por transportista.

**Actores:** Transportista, Centro de extracción, Sistema.

**Recursos:** Muestra, Orden del día, Estudio.

**Episodios:**

1. El transportista llega al siguiente centro de extracción de la orden del día.
2. El centro de extracción entrega las muestras al transportista.
3. El transportista registra el retiro de las muestras.
4. El sistema cambia esos estudios a En camino al laboratorio central.
5. El transportista repite los episodios en cada centro hasta completar la orden del día.

## E25 · Seguir ubicación de la muestra

**Título:** Seguir ubicación de la muestra.

**Objetivo:** Saber en todo momento por dónde va una muestra en traslado.

**Contexto:** Laboratorio central, mientras el estudio está En camino al laboratorio central.

**Actores:** Transportista, Administrativo, Sistema.

**Recursos:** Muestra, Estudio, Mapa.

**Episodios:**

1. El transportista informa su ubicación durante el recorrido.
2. El administrativo busca el estudio de un paciente.
3. El sistema identifica al transportista que lleva la muestra.
4. El sistema muestra en un mapa la ubicación del transportista.

## E26 · Registrar llegada al laboratorio central

**Título:** Registrar llegada al laboratorio central.

**Objetivo:** Confirmar la recepción de las muestras en el laboratorio central.

**Contexto:** Laboratorio central, de lunes a viernes de 9 a 18.
- **Precondición:** el transportista completó la orden del día.
- **Restricción:** se asume que toda muestra retirada llega.

**Actores:** Transportista, Administrativo, Sistema.

**Recursos:** Muestra, Laboratorio central, Estudio.

**Episodios:**

1. El transportista entrega las muestras en el laboratorio central.
2. El transportista registra la llegada con todas las muestras recolectadas.
3. El sistema cambia esos estudios a En laboratorio central.
4. El administrativo registra el volumen de cada muestra.
5. Si una muestra tiene menos de 2 ml, el administrativo realiza SOLICITAR NUEVA EXTRACCIÓN.
6. El sistema realiza ARMAR SAMPLE SET con las muestras válidas.

## E27 · Solicitar nueva extracción

**Título:** Solicitar nueva extracción.

**Objetivo:** Reemplazar una muestra que no sirve, sin costo para el paciente.

**Contexto:** Laboratorio central.
- **Precondición:** la muestra tiene menos de 2 ml o el laboratorio de secuenciación informó ADN insuficiente.
- **Restricción:** se mantiene el mismo estudio y no se cobra.

**Actores:** Administrativo, Sistema, Paciente, Médico tratante.

**Recursos:** Muestra, Estudio, Notificación.

**Episodios:**

1. El administrativo registra que la muestra es insuficiente e indica el motivo.
2. El sistema cambia el estudio a Requiere nueva extracción.
3. El sistema notifica al paciente y al médico tratante.
4. El paciente realiza RESERVAR TURNO DE EXTRACCIÓN sin un nuevo pago.

# 6. Envío a Corea

## E28 · Armar sample set

**Título:** Armar sample set.

**Objetivo:** Enviar las muestras a Corea en paquetes de 10 para obtener el envío gratuito.

**Contexto:** Laboratorio central, de forma automática al registrarse la llegada de muestras.
- **Precondición:** existe al menos un estudio En laboratorio central.
- **Restricción:** un sample set cerrado no admite más muestras; si no llega a 10, se espera al día siguiente.

**Actores:** Sistema.

**Recursos:** Sample set, Muestra, Pompe urgente, Estudio, Diagnóstico presuntivo.

**Episodios:**

1. El sistema agrega cada muestra En laboratorio central al sample set en armado.
2. El sistema identifica como Pompe urgente todo estudio con diagnóstico presuntivo de Pompe en un paciente menor de 4 meses.
3. Si el sample set llega a 10 muestras, el sistema lo cierra.
4. Si el sample set contiene un Pompe urgente, el sistema lo cierra aunque esté incompleto.
5. El sistema cambia los estudios del sample set cerrado a Pendiente de autorización ministerial.
6. El sistema realiza SOLICITAR AUTORIZACIÓN MINISTERIAL.

## E29 · Solicitar autorización ministerial

**Título:** Solicitar autorización ministerial.

**Objetivo:** Cumplir la exigencia del Ministerio de Salud de autorizar la salida de muestras al exterior.

**Contexto:** Laboratorio central, al cerrarse un sample set.
- **Restricción:** el PDF de autorización debe coincidir con las muestras del paquete, porque se controla en la aduana.

**Actores:** Sistema, Ministerio de Salud, Administrativo.

**Recursos:** CCB, Sample set, Estudio, Notificación.

**Episodios:**

1. El sistema genera el CCB con los pacientes del sample set.
2. El sistema envía el CCB a la API del Ministerio de Salud.
3. El Ministerio de Salud devuelve el PDF de autorización.
4. El sistema asocia el CCB y el PDF de autorización a cada estudio del sample set.
5. El sistema cambia el sample set a Pendiente de retiro y sus estudios a Pendiente de envío.
6. El sistema avisa al administrativo que el sample set está listo para programar el retiro.

## E30 · Programar retiro

**Título:** Programar retiro.

**Objetivo:** Coordinar con FedEx el retiro del sample set.

**Contexto:** Laboratorio central.
- **Precondición:** el sample set está Pendiente de retiro.
- **Restricción:** el retiro se programa de lunes a viernes de 9 a 18, y cada sample set es un paquete aparte.

**Actores:** Administrativo, FedEx, Sistema.

**Recursos:** Sample set.

**Episodios:**

1. El administrativo consulta los sample sets pendientes de retiro.
2. El administrativo elige un día y una hora hábiles para el retiro.
3. El administrativo envía a FedEx el día, la hora y la URL del sample set.
4. El sistema cambia el sample set a Retiro programado.

## E31 · Despachar sample set

**Título:** Despachar sample set.

**Objetivo:** Actualizar sin intervención los estados cuando FedEx retira el paquete.

**Contexto:** Laboratorio central, en el día y la hora programados.
- **Precondición:** el sample set está en Retiro programado.

**Actores:** FedEx, Sistema.

**Recursos:** Sample set, Estudio.

**Episodios:**

1. FedEx retira el sample set en el día y la hora programados.
2. FedEx invoca la URL del sample set.
3. El sistema cambia el sample set a Despachado.
4. El sistema cambia todos los estudios del sample set a En viaje a Corea.

# 7. Análisis y resultados

## E32 · Cargar datos crudos

**Título:** Cargar datos crudos.

**Objetivo:** Poner los datos crudos a disposición del equipo de bioinformática.

**Contexto:** Laboratorio central, cuando llegan los datos crudos del laboratorio de secuenciación.
- **Precondición:** el estudio está En viaje a Corea.
- **Restricción:** los datos crudos llegan por estudio y no por sample set; por ahora se simulan como un archivo de texto con A, C, T y G.

**Actores:** Laboratorio de secuenciación, Administrativo, Bioinformático, Sistema.

**Recursos:** Datos crudos, Estudio, ADN, Notificación.

**Episodios:**

1. El laboratorio de secuenciación envía los datos crudos de un estudio.
2. Si el laboratorio de secuenciación informa ADN insuficiente, el administrativo realiza SOLICITAR NUEVA EXTRACCIÓN.
3. Si el ADN es suficiente, el administrativo carga los datos crudos en el estudio.
4. Si el ADN es suficiente, el sistema cambia el estudio a En área de bioinformática.
5. Si el ADN es suficiente, el sistema notifica a todos los bioinformáticos.

## E33 · Tomar estudio

**Título:** Tomar estudio.

**Objetivo:** Que un solo bioinformático analice cada estudio y que los demás lo sepan.

**Contexto:** Laboratorio central.
- **Precondición:** hay estudios En área de bioinformática.
- **Restricción:** los bioinformáticos se reparten los estudios entre ellos.

**Actores:** Bioinformático, Sistema.

**Recursos:** Estudio, Pompe urgente.

**Episodios:**

1. El bioinformático consulta la lista de estudios En área de bioinformática.
2. El sistema ordena la lista con los Pompe urgentes primero y el resto por orden de llegada.
3. El bioinformático toma un estudio.
4. El sistema cambia el estudio a En análisis y lo quita de la lista de los demás bioinformáticos.

## E34 · Registrar variante

**Título:** Registrar variante.

**Objetivo:** Dejar constancia de las variantes encontradas en los genes solicitados.

**Contexto:** Laboratorio central.
- **Precondición:** el bioinformático tomó el estudio y lo analizó con su pipeline, fuera del sistema.

**Actores:** Bioinformático, Sistema.

**Recursos:** Gen, Variante genética, Hallazgo secundario, API de bioinformática, Estudio.

**Episodios:**

1. El bioinformático elige un gen de los solicitados en el estudio.
2. El sistema consulta a la API de bioinformática las variantes conocidas de ese gen.
3. El bioinformático selecciona la variante encontrada.
4. El sistema registra la variante con su clasificación: patogénica, benigna o VUS.
5. El bioinformático repite los episodios por cada gen con variantes, incluidos los de hallazgos secundarios.
6. El bioinformático finaliza el análisis y el sistema realiza INFORMAR RESULTADO.

## E35 · Informar resultado

**Título:** Informar resultado.

**Objetivo:** Comunicar el diagnóstico al médico tratante y al paciente.

**Contexto:** Laboratorio central, al finalizar el análisis.
- **Precondición:** el bioinformático registró las variantes del estudio.

**Actores:** Sistema, Médico tratante, Paciente.

**Recursos:** Resultado del estudio, Variante genética, Notificación, Estudio, Gen, Diagnóstico presuntivo.

**Episodios:**

1. El sistema determina si el estudio es positivo, es decir, si hay una variante patogénica en los genes del diagnóstico presuntivo.
2. El sistema genera el resultado del estudio en PDF con la plantilla del laboratorio.
3. El sistema cambia el estudio a Finalizado.
4. El sistema notifica el resultado al médico tratante y al paciente por mail y por aviso.
5. El médico tratante y el paciente descargan el resultado del estudio.

# 8. Gestión médica

## E36 · Dar de alta patología

**Título:** Dar de alta patología.

**Objetivo:** Definir las patologías lisosomales y los síntomas que validan el diagnóstico presuntivo.

**Contexto:** Laboratorio central.
- **Restricción:** la relación patología–gen la mantiene la API de bioinformática, no el sistema.

**Actores:** Gerente médico, Sistema.

**Recursos:** Patología lisosomal, Síntoma.

**Episodios:**

1. El gerente médico carga el nombre de la patología lisosomal.
2. El gerente médico selecciona el síntoma cardinal mediante BUSCAR SÍNTOMA.
3. El gerente médico selecciona los síntomas secundarios mediante BUSCAR SÍNTOMA.
4. El sistema guarda la patología para su uso en VALIDAR DIAGNÓSTICO PRESUNTIVO.
5. Cuando lo necesite, el gerente médico modifica el síntoma cardinal o los síntomas secundarios.

## E37 · Generar cupón

**Título:** Generar cupón.

**Objetivo:** Que el laboratorio otorgue descuentos a través de los médicos tratantes.

**Contexto:** Laboratorio central.

**Actores:** Gerente médico, Sistema.

**Recursos:** Cupón de descuento, Módulo de cupones, Notificación.

**Episodios:**

1. El gerente médico define el descuento y la cantidad de cupones.
2. El sistema solicita los cupones al módulo de cupones.
3. El sistema recibe los cupones en PDF, con código QR o código numérico.
4. El gerente médico asigna los cupones a un médico tratante.
5. El sistema notifica al médico tratante los cupones recibidos.

## E38 · Asignar cupón

**Título:** Asignar cupón.

**Objetivo:** Que el médico tratante decida a qué pacientes beneficiar con sus cupones.

**Contexto:** Consultorio del médico tratante.
- **Precondición:** el médico tratante tiene cupones disponibles.
- **Restricción:** cada médico tratante recibe una cantidad limitada de cupones.

**Actores:** Médico tratante, Paciente, Sistema.

**Recursos:** Cupón de descuento, Notificación.

**Episodios:**

1. El médico tratante consulta sus cupones disponibles.
2. El médico tratante elige un cupón y un paciente.
3. El médico tratante asigna el cupón al paciente.
4. El sistema envía una notificación al paciente.
5. El sistema deja el cupón disponible en la vista del paciente.

# 9. Comunicación y registro

## E39 · Notificar

**Título:** Notificar.

**Objetivo:** Que cada usuario se entere de lo que tiene pendiente sin depender de llamados telefónicos.

**Contexto:** Ante cada evento del circuito que requiere una acción o informa una novedad.
- **Restricción:** no se usan WhatsApp ni SMS, por su costo.

**Actores:** Sistema, Usuario.

**Recursos:** Notificación.

**Episodios:**

1. El sistema detecta un evento que requiere avisar a un usuario, por ejemplo un cambio de estado.
2. El sistema envía una notificación por mail.
3. El sistema publica un aviso en la lista de pendientes del usuario.
4. El usuario consulta sus avisos y accede a la tarea pendiente.

## E40 · Consultar chatbot

**Título:** Consultar chatbot.

**Objetivo:** Responder las dudas del paciente sobre las patologías lisosomales.

**Contexto:** Vista del paciente, en cualquier momento.
- **Restricción:** el chatbot no deriva la consulta a una persona.

**Actores:** Paciente, Sistema.

**Recursos:** Chatbot de pacientes.

**Episodios:**

1. El paciente escribe una pregunta en la interfaz del sistema.
2. El sistema delega la pregunta al chatbot de pacientes.
3. El sistema muestra la respuesta al paciente.

## E41 · Registrar operación financiera

**Título:** Registrar operación financiera.

**Objetivo:** Conservar desde el inicio la información de caja y deuda para el futuro tablero de control.

**Contexto:** Ante cada operación económica del circuito, durante PAGAR ESTUDIO o AUTORIZAR COBERTURA.

**Actores:** Sistema.

**Recursos:** Registro financiero, Pago, Cupón de descuento.

**Episodios:**

1. El sistema registra cada pago particular con su importe, el paciente y la fecha.
2. El sistema registra el descuento aplicado con cada cupón de descuento.
3. El sistema registra el importe que cubre la obra social al autorizarse la cobertura.
4. El sistema conserva los registros para consultar la caja y la deuda por obra social y por paciente.
