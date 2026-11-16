-- E03 Dar de alta usuario: provincias y perfil del transportista (docs/modelo-datos.md, 1 y 2).
-- El administrador general da de alta al transportista con su provincia: hay uno por provincia.

-- Las 24 jurisdicciones del país (23 provincias y la Ciudad Autónoma de Buenos Aires).
-- Datos fijos; también las usan los centros de extracción (E19) y la orden del día (E23).
create table public.provincias (
  id     bigint generated always as identity primary key,
  nombre text not null unique
);

insert into public.provincias (nombre) values
  ('Buenos Aires'),
  ('Catamarca'),
  ('Chaco'),
  ('Chubut'),
  ('Ciudad Autónoma de Buenos Aires'),
  ('Córdoba'),
  ('Corrientes'),
  ('Entre Ríos'),
  ('Formosa'),
  ('Jujuy'),
  ('La Pampa'),
  ('La Rioja'),
  ('Mendoza'),
  ('Misiones'),
  ('Neuquén'),
  ('Río Negro'),
  ('Salta'),
  ('San Juan'),
  ('San Luis'),
  ('Santa Cruz'),
  ('Santa Fe'),
  ('Santiago del Estero'),
  ('Tierra del Fuego, Antártida e Islas del Atlántico Sur'),
  ('Tucumán');

-- Perfil 1:1 de los usuarios con rol transportista. Nombre, apellido, mail y teléfono están en
-- usuarios. provincia_id único: un transportista por provincia (LEL, Transportista).
create table public.transportistas (
  usuario_id   bigint primary key references public.usuarios (id) on delete restrict,
  provincia_id bigint not null unique references public.provincias (id) on delete restrict,
  -- Última ubicación informada durante el recorrido (E25). Nulas hasta el primer informe.
  latitud      numeric(9, 6) check (latitud between -90 and 90),
  longitud     numeric(9, 6) check (longitud between -180 and 180),
  ubicacion_en timestamptz,
  creado_en    timestamptz not null default now(),
  constraint transportistas_ubicacion_completa check (
    (latitud is null and longitud is null and ubicacion_en is null)
    or (latitud is not null and longitud is not null and ubicacion_en is not null)
  )
);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.provincias     enable row level security;
alter table public.transportistas enable row level security;
