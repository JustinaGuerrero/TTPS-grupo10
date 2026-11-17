-- E06 y E09: diagnóstico presuntivo, síntomas y familiares del paciente.

alter table public.usuarios
  add column debe_cambiar_contrasena boolean not null default false;

create table public.paciente_sintomas (
  paciente_id    bigint not null references public.pacientes (id) on delete restrict,
  termino_codigo text not null references public.terminos_snomed (codigo) on delete restrict,
  primary key (paciente_id, termino_codigo)
);

create table public.diagnosticos_presuntivos (
  paciente_id  bigint not null references public.pacientes (id) on delete restrict,
  patologia_id bigint not null references public.patologias (id) on delete restrict,
  primary key (paciente_id, patologia_id)
);

create table public.familiares (
  id                    bigint generated always as identity primary key,
  paciente_id           bigint not null references public.pacientes (id) on delete restrict,
  parentesco            text not null,
  nombre                text not null,
  dni                   text,
  paciente_vinculado_id bigint references public.pacientes (id) on delete restrict,
  vinculado_en          timestamptz,
  creado_en             timestamptz not null default now()
);

create index familiares_paciente_idx on public.familiares (paciente_id);
create index familiares_dni_idx on public.familiares (dni) where dni is not null;

create table public.familiar_sintomas (
  familiar_id    bigint not null references public.familiares (id) on delete restrict,
  termino_codigo text not null references public.terminos_snomed (codigo) on delete restrict,
  primary key (familiar_id, termino_codigo)
);

create table public.familiar_patologias (
  familiar_id  bigint not null references public.familiares (id) on delete restrict,
  patologia_id bigint not null references public.patologias (id) on delete restrict,
  primary key (familiar_id, patologia_id)
);

alter table public.paciente_sintomas       enable row level security;
alter table public.diagnosticos_presuntivos enable row level security;
alter table public.familiares              enable row level security;
alter table public.familiar_sintomas       enable row level security;
alter table public.familiar_patologias     enable row level security;
