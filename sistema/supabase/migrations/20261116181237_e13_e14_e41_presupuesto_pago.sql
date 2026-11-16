-- E13, E14, E41: presupuesto, pago particular y registro financiero.
-- Tablas de docs/modelo-datos.md (sección 5), completas: obras_sociales, cupones, presupuestos,
-- pagos y asientos_financieros. cupones y obras_sociales están acá solo porque pagos y
-- asientos_financieros las referencian; sus pantallas son de otros issues. coberturas y
-- demandas_reautorizacion las crea el issue de obra social.

-- Copia de las obras sociales que eligieron los pacientes. El listado vigente viene de la API.
create table public.obras_sociales (
  codigo text primary key check (codigo <> ''),
  nombre text not null
);

-- Cupón de descuento. El módulo de cupones es el que manda sobre el estado (supuesto O15:
-- el descuento es un porcentaje).
create table public.cupones (
  id                     bigint generated always as identity primary key,
  codigo                 text not null unique,
  descuento_porcentaje   numeric(5,2) not null
    check (descuento_porcentaje > 0 and descuento_porcentaje <= 100),
  pdf_path               text not null,
  estado                 text not null check (estado in ('vigente', 'utilizado')),
  generado_por           bigint not null references public.usuarios (id) on delete restrict,
  generado_en            timestamptz not null default now(),
  medico_tratante_id     bigint references public.medicos (usuario_id) on delete restrict,
  asignado_a_medico_en   timestamptz,
  paciente_id            bigint references public.pacientes (id) on delete restrict,
  asignado_a_paciente_en timestamptz,
  utilizado_en           timestamptz,
  -- El médico tratante asigna el cupón al paciente: antes tiene que tenerlo el médico.
  constraint cupones_paciente_requiere_medico
    check (paciente_id is null or medico_tratante_id is not null)
);

create index cupones_generado_por_idx on public.cupones (generado_por);
create index cupones_medico_tratante_idx on public.cupones (medico_tratante_id);
create index cupones_paciente_idx on public.cupones (paciente_id);

-- Un presupuesto por estudio. El precio es fijo: 500 USD hasta 5 genes y 30 USD por cada gen
-- adicional del análisis inicial (supuesto O13).
create table public.presupuestos (
  id             bigint generated always as identity primary key,
  estudio_id     bigint not null unique references public.estudios (id) on delete restrict,
  cantidad_genes smallint not null check (cantidad_genes > 0),
  total_usd      numeric(10,2) not null check (total_usd > 0),
  emitido_por    bigint not null references public.usuarios (id) on delete restrict,
  emitido_en     timestamptz not null default now()
);

create index presupuestos_emitido_por_idx on public.presupuestos (emitido_por);

-- Un pago de cada tipo por estudio, sin cuotas. Con cobertura parcial hay uno de obra social y
-- otro particular por la diferencia.
create table public.pagos (
  id            bigint generated always as identity primary key,
  estudio_id    bigint not null references public.estudios (id) on delete restrict,
  tipo          text not null check (tipo in ('particular', 'obra_social')),
  importe_usd   numeric(10,2) not null check (importe_usd > 0),
  cupon_id      bigint unique references public.cupones (id) on delete restrict,
  descuento_usd numeric(10,2) not null default 0 check (descuento_usd >= 0),
  pagado_en     timestamptz not null default now(),
  constraint pagos_un_pago_de_cada_tipo unique (estudio_id, tipo),
  -- Sin cupón no hay descuento.
  constraint pagos_descuento_con_cupon check (cupon_id is not null or descuento_usd = 0)
);

-- Un asiento por cada operación económica. Solo se insertan: ver el trigger de abajo.
create table public.asientos_financieros (
  id                 bigint generated always as identity primary key,
  tipo               text not null check (tipo in (
    'presupuesto_emitido',
    'pago_particular',
    'cobertura_obra_social',
    'descuento_cupon',
    'cobro_obra_social'
  )),
  estudio_id         bigint not null references public.estudios (id) on delete restrict,
  pago_id            bigint references public.pagos (id) on delete restrict,
  obra_social_codigo text references public.obras_sociales (codigo) on delete restrict,
  -- Siempre positivo: el tipo indica el sentido.
  importe_usd        numeric(10,2) not null check (importe_usd > 0),
  creado_en          timestamptz not null default now(),
  constraint asientos_obra_social_segun_tipo check (
    (tipo in ('cobertura_obra_social', 'cobro_obra_social')) = (obra_social_codigo is not null)
  ),
  constraint asientos_pago_segun_tipo check (
    tipo in ('presupuesto_emitido', 'cobro_obra_social') or pago_id is not null
  )
);

create index asientos_financieros_estudio_idx on public.asientos_financieros (estudio_id);
create index asientos_financieros_pago_idx on public.asientos_financieros (pago_id);
create index asientos_financieros_obra_social_idx
  on public.asientos_financieros (obra_social_codigo);
create index asientos_financieros_tipo_idx on public.asientos_financieros (tipo);

-- Los asientos nunca se modifican ni se borran (E41).
create function public.asientos_financieros_solo_insertar() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'Los asientos financieros solo se insertan: no se modifican ni se borran.';
end;
$$;

create trigger asientos_financieros_inmutables
  before update or delete on public.asientos_financieros
  for each row execute function public.asientos_financieros_solo_insertar();

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.obras_sociales       enable row level security;
alter table public.cupones              enable row level security;
alter table public.presupuestos         enable row level security;
alter table public.pagos                enable row level security;
alter table public.asientos_financieros enable row level security;
