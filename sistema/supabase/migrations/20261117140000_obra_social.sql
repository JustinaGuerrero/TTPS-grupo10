-- Cobertura de obra social: solicitar (E16), autorizar o rechazar (E17) y reautorización con una
-- resolución judicial (E18). Tablas coberturas y demandas_reautorizacion de docs/modelo-datos.md.

-- Pedido de cobertura de un estudio a la obra social del paciente. Uno por estudio: después de un
-- rechazo, la demanda de reautorización vuelve a poner este mismo pedido en pendiente.
create table public.coberturas (
  id                   bigint generated always as identity primary key,
  estudio_id           bigint not null unique references public.estudios (id) on delete restrict,
  obra_social_codigo   text not null references public.obras_sociales (codigo) on delete restrict,
  -- Porcentaje que informó la API al elegirla: no cambia aunque la API lo cambie después.
  porcentaje           numeric(5,2) not null check (porcentaje > 0 and porcentaje <= 100),
  estado               text not null default 'pendiente'
                       check (estado in ('pendiente', 'autorizada', 'rechazada')),
  -- Total del presupuesto por el porcentaje. Solo cuando está autorizada.
  importe_cubierto_usd numeric(10,2) check (importe_cubierto_usd > 0),
  solicitada_en        timestamptz not null default now(),
  -- Última respuesta de la obra social y el administrativo que la registró.
  respondida_en        timestamptz,
  respondida_por       bigint references public.usuarios (id) on delete restrict,
  constraint coberturas_importe_si_autorizada
    check ((estado = 'autorizada') = (importe_cubierto_usd is not null)),
  constraint coberturas_respuesta_registrada
    check (estado = 'pendiente' or (respondida_en is not null and respondida_por is not null))
);

create index coberturas_obra_social_idx on public.coberturas (obra_social_codigo);
create index coberturas_estado_idx on public.coberturas (estado);

-- PDF de la resolución judicial favorable que carga el paciente después de un rechazo (E18).
create table public.demandas_reautorizacion (
  id              bigint generated always as identity primary key,
  cobertura_id    bigint not null references public.coberturas (id) on delete restrict,
  resolucion_path text not null,
  cargada_en      timestamptz not null default now()
);

create index demandas_reautorizacion_cobertura_idx on public.demandas_reautorizacion (cobertura_id);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.coberturas              enable row level security;
alter table public.demandas_reautorizacion enable row level security;
