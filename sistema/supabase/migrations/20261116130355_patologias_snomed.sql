-- E07, E08, E36: términos SNOMED, patologías y sus síntomas.
-- Salen de docs/modelo-datos.md. Las 5 patologías base de Apigen se cargan en seeds.py.

create table public.terminos_snomed (
  codigo  text primary key,
  termino text not null,
  tipo    text not null check (tipo in ('sintoma', 'especialidad'))
);

create table public.patologias (
  id             bigint generated always as identity primary key,
  codigo_apigen  text not null unique,
  nombre         text not null unique,
  activa         boolean not null default true,
  creado_por     bigint not null references public.usuarios (id) on delete restrict,
  creado_en      timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create table public.patologia_sintomas (
  patologia_id   bigint not null references public.patologias (id) on delete restrict,
  termino_codigo text not null references public.terminos_snomed (codigo) on delete restrict,
  es_cardinal    boolean not null default false,
  primary key (patologia_id, termino_codigo)
);

-- Un solo síntoma cardinal por patología. Que el cardinal no esté también entre los
-- secundarios lo garantiza la clave primaria (patologia_id, termino_codigo).
create unique index patologia_sintomas_un_cardinal
  on public.patologia_sintomas (patologia_id) where es_cardinal;

-- Seguridad: RLS activado y sin políticas, igual que en la migración inicial.
alter table public.terminos_snomed   enable row level security;
alter table public.patologias        enable row level security;
alter table public.patologia_sintomas enable row level security;