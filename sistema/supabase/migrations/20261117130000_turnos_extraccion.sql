-- E19 Reservar turno de extracción, E20 Cancelar turno y E21 Recordar turno: feriados, centros de
-- extracción y turnos de extracción (docs/modelo-datos.md, secciones 2 y 6).

-- Días sin turnos, sin orden del día y sin retiros de FedEx (E19, E23, E30). Son datos fijos: los
-- feriados nacionales de cada año se agregan con una migración nueva.
create table public.feriados (
  fecha       date primary key,
  descripcion text not null
);

-- Feriados nacionales de 2026 (inamovibles y trasladables, en el día al que se trasladaron).
-- Los días no laborables con fines turísticos (23/3, 10/7 y 7/12) no son feriados: hay turnos.
insert into public.feriados (fecha, descripcion) values
  ('2026-01-01', 'Año Nuevo'),
  ('2026-02-16', 'Carnaval'),
  ('2026-02-17', 'Carnaval'),
  ('2026-03-24', 'Día Nacional de la Memoria por la Verdad y la Justicia'),
  ('2026-04-02', 'Día del Veterano y de los Caídos en la Guerra de Malvinas'),
  ('2026-04-03', 'Viernes Santo'),
  ('2026-05-01', 'Día del Trabajador'),
  ('2026-05-25', 'Día de la Revolución de Mayo'),
  ('2026-06-15', 'Paso a la Inmortalidad del General Martín Miguel de Güemes'),
  ('2026-06-20', 'Paso a la Inmortalidad del General Manuel Belgrano'),
  ('2026-07-09', 'Día de la Independencia'),
  ('2026-08-17', 'Paso a la Inmortalidad del General José de San Martín'),
  ('2026-10-12', 'Día del Respeto a la Diversidad Cultural'),
  ('2026-11-23', 'Día de la Soberanía Nacional'),
  ('2026-12-08', 'Día de la Inmaculada Concepción de María'),
  ('2026-12-25', 'Navidad');

-- Centros donde se toma la muestra de sangre. No operan el sistema: el centro avisa por el bot de
-- mensajería (E22). El horario (lunes a viernes de 9 a 18) es el mismo para todos y no se guarda.
-- Los centros de prueba los carga `flask seeds`.
create table public.centros_extraccion (
  id               bigint generated always as identity primary key,
  nombre           text not null,
  -- Se manda al módulo de optimización de recorridos (E23).
  direccion        text not null,
  localidad        text not null,
  -- Define qué transportista lo visita (E23).
  provincia_id     bigint not null references public.provincias (id) on delete restrict,
  -- Para mostrarlo en el mapa (E19).
  latitud          numeric(9, 6) not null check (latitud between -90 and 90),
  longitud         numeric(9, 6) not null check (longitud between -180 and 180),
  telefono         text not null,
  -- Chat desde el que el centro escribe al bot de mensajería (E22).
  telegram_chat_id text not null unique,
  activo           boolean not null default true
);

create index centros_extraccion_provincia on public.centros_extraccion (provincia_id);

-- La franja de 15 minutos que reservó el paciente en un centro. El turnero no tiene tabla: son las
-- franjas posibles del centro menos los turnos ocupados.
create table public.turnos_extraccion (
  id                      bigint generated always as identity primary key,
  estudio_id              bigint not null references public.estudios (id) on delete restrict,
  centro_id               bigint not null references public.centros_extraccion (id) on delete restrict,
  -- Comienzo de la franja. Core controla que sea de lunes a viernes, de 9 a 18 y fuera de feriados.
  inicio                  timestamptz not null,
  -- ausente: el paciente no fue y no llegó el mensaje de muestra tomada (supuesto O7, E22).
  estado                  text not null default 'reservado'
                          check (estado in ('reservado', 'cancelado', 'asistido', 'ausente')),
  reservado_en            timestamptz not null default now(),
  cancelado_en            timestamptz,
  -- E21: el recordatorio sale una sola vez por turno.
  recordatorio_enviado_en timestamptz,
  -- Franjas en punto: 9:00, 9:15, 9:30… (Argentina no tiene husos de media hora).
  constraint turnos_extraccion_franja check (
    extract(second from inicio) = 0 and extract(minute from inicio)::int % 15 = 0
  ),
  constraint turnos_extraccion_cancelado check ((estado = 'cancelado') = (cancelado_en is not null))
);

-- Un paciente por franja (E19): si dos pacientes reservan la misma franja de un centro a la vez,
-- el segundo choca contra este índice.
create unique index turnos_extraccion_franja_ocupada
  on public.turnos_extraccion (centro_id, inicio)
  where estado in ('reservado', 'asistido');

-- Un turno vigente por estudio.
create unique index turnos_extraccion_vigente_por_estudio
  on public.turnos_extraccion (estudio_id)
  where estado = 'reservado';

-- Recordatorios (E21) e inasistencias (O7): turnos reservados por fecha.
create index turnos_extraccion_reservados_por_inicio
  on public.turnos_extraccion (inicio)
  where estado = 'reservado';

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.feriados           enable row level security;
alter table public.centros_extraccion enable row level security;
alter table public.turnos_extraccion  enable row level security;
