-- E22 Registrar toma de muestra: mensajes del bot de mensajería, muestras, órdenes del día, sus
-- paradas y sample sets (docs/modelo-datos.md, secciones 6 y 7). La lógica de las órdenes del día
-- (E23, E24) y de los sample sets (E28 a E31) es de otros issues: acá van solo las tablas.

-- Sample set: lote de hasta 10 muestras que viaja a Corea (E28 a E31). Sus estados siguen siempre
-- el mismo orden y cada uno tiene la fecha en que empezó, así que no lleva historial aparte.
create table public.sample_sets (
  id                     bigint generated always as identity primary key,
  estado                 text not null default 'en_armado'
                         check (estado in (
                           'en_armado', 'cerrado', 'pendiente_retiro', 'retiro_programado',
                           'despachado'
                         )),
  creado_en              timestamptz not null default now(),
  cerrado_en             timestamptz,
  -- Excel con los pacientes del sample set (E29).
  ccb_path               text,
  -- PDF de autorización del Ministerio de Salud.
  autorizacion_path      text,
  autorizado_en          timestamptz,
  -- Día y hora hábiles del retiro de FedEx (E30).
  retiro_programado_para timestamptz,
  retiro_programado_en   timestamptz,
  retiro_programado_por  bigint references public.usuarios (id) on delete restrict,
  -- Parte secreta y aleatoria de la URL que invoca FedEx (E31).
  token_retiro           text unique,
  despachado_en          timestamptz
);

-- Un solo sample set en armado a la vez (E28).
create unique index sample_sets_uno_en_armado
  on public.sample_sets ((true))
  where estado = 'en_armado';

-- Orden del día: los centros de una provincia que el transportista recorre una mañana hábil (E23).
create table public.ordenes_del_dia (
  id               bigint generated always as identity primary key,
  transportista_id bigint not null references public.transportistas (usuario_id) on delete restrict,
  fecha            date not null,
  generada_en      timestamptz not null default now(),
  -- Llegada al laboratorio central con todas las muestras (E26).
  llegada_en       timestamptz,
  constraint ordenes_del_dia_una_por_dia unique (transportista_id, fecha)
);

-- Cada centro de la orden del día, en el orden fijo que devuelve el módulo de optimización de
-- recorridos (E23). retirado_en: cuándo el transportista registró el retiro (E24).
create table public.paradas_orden_del_dia (
  orden_del_dia_id bigint not null references public.ordenes_del_dia (id) on delete restrict,
  posicion         smallint not null check (posicion >= 1),
  centro_id        bigint not null references public.centros_extraccion (id) on delete restrict,
  retirado_en      timestamptz,
  primary key (orden_del_dia_id, posicion),
  constraint paradas_orden_del_dia_centro_unico unique (orden_del_dia_id, centro_id)
);

create index paradas_orden_del_dia_centro on public.paradas_orden_del_dia (centro_id);

-- Muestra: el tubo de sangre de una extracción. Un estudio tiene una por cada extracción (una
-- nueva extracción, E27, agrega otra); la vigente es la última. El volumen no se registra en el
-- sistema (G15): lo controla el laboratorio de Corea.
create table public.muestras (
  id                  bigint generated always as identity primary key,
  -- Coincide con el estudio del turno (control en core).
  estudio_id          bigint not null references public.estudios (id) on delete restrict,
  turno_id            bigint not null unique
                      references public.turnos_extraccion (id) on delete restrict,
  -- Llegada del mensaje de muestra tomada al bot (E22).
  tomada_en           timestamptz not null,
  -- Orden con la que la retiró el transportista (E24). Nula hasta el retiro.
  orden_del_dia_id    bigint references public.ordenes_del_dia (id) on delete restrict,
  -- Nulo hasta que entra en un sample set (E28).
  sample_set_id       bigint references public.sample_sets (id) on delete restrict,
  -- La muestra no sirve: volumen (menos de 2 ml) o ADN insuficiente, según avisa el laboratorio.
  insuficiente_motivo text check (insuficiente_motivo in ('volumen', 'adn')),
  insuficiente_en     timestamptz,
  constraint muestras_insuficiente check (
    (insuficiente_motivo is null) = (insuficiente_en is null)
  )
);

create index muestras_estudio on public.muestras (estudio_id);
create index muestras_orden_del_dia on public.muestras (orden_del_dia_id);
create index muestras_sample_set on public.muestras (sample_set_id);

-- Cada update que recibe el bot de mensajería por el webhook de Telegram (E22). Se guarda aunque
-- no se pueda procesar, para que el administrativo revise los que fallaron.
create table public.mensajes_bot (
  id                 bigint generated always as identity primary key,
  -- Evita procesar dos veces el mismo update. `flask bot simular` usa ids negativos.
  telegram_update_id bigint not null unique,
  -- Nulos si el update no trae un mensaje con texto (un sticker, un mensaje editado…).
  chat_id            text,
  texto              text,
  -- Nulo si el chat no es de un centro conocido.
  centro_id          bigint references public.centros_extraccion (id) on delete restrict,
  -- Nulo si el código del estudio no se reconoció.
  estudio_id         bigint references public.estudios (id) on delete restrict,
  recibido_en        timestamptz not null default now(),
  procesado_en       timestamptz,
  -- Motivo, si no se pudo procesar. Nulo si se procesó bien.
  error              text
);

create index mensajes_bot_recibido_en on public.mensajes_bot (recibido_en);
create index mensajes_bot_con_error on public.mensajes_bot (recibido_en) where error is not null;
create index mensajes_bot_centro on public.mensajes_bot (centro_id);
create index mensajes_bot_estudio on public.mensajes_bot (estudio_id);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.sample_sets           enable row level security;
alter table public.ordenes_del_dia       enable row level security;
alter table public.paradas_orden_del_dia enable row level security;
alter table public.muestras              enable row level security;
alter table public.mensajes_bot          enable row level security;
