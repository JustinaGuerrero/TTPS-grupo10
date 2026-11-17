-- E04: combinaciones de dispositivo/red confiables y códigos de verificación de un solo uso.

create table public.dispositivos_confiables (
  id                 bigint generated always as identity primary key,
  usuario_id         bigint not null references public.usuarios (id) on delete cascade,
  huella_hash        text not null,
  creado_en          timestamptz not null default now(),
  ultimo_ingreso_en  timestamptz not null default now(),
  constraint dispositivos_usuario_huella_key unique (usuario_id, huella_hash)
);

create table public.codigos_verificacion (
  id          bigint generated always as identity primary key,
  usuario_id  bigint not null references public.usuarios (id) on delete cascade,
  codigo_hash text not null,
  huella_hash text not null,
  intentos    smallint not null default 0,
  expira_en   timestamptz not null,
  usado_en    timestamptz,
  creado_en   timestamptz not null default now(),
  constraint codigo_verificacion_intentos_check check (intentos between 0 and 5)
);

create index codigos_usuario_huella_creado_idx
  on public.codigos_verificacion (usuario_id, huella_hash, creado_en);

alter table public.dispositivos_confiables enable row level security;
alter table public.codigos_verificacion   enable row level security;
