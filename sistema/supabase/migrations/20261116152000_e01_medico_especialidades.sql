-- E01: especialidades SNOMED elegidas por médicos tratantes y gerentes médicos.
create table public.medico_especialidades (
  medico_id     bigint not null references public.medicos (usuario_id) on delete restrict,
  termino_codigo text not null references public.terminos_snomed (codigo) on delete restrict,
  primary key (medico_id, termino_codigo)
);

-- Seguridad: RLS activado y sin políticas, igual que en las migraciones anteriores.
alter table public.medico_especialidades enable row level security;
