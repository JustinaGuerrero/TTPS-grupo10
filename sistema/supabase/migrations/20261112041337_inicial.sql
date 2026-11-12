-- Roles y usuarios del sistema.
-- Los 7 roles salen del símbolo Usuario del LEL (docs/lel.md).

create table public.roles (
  codigo text primary key,
  nombre text not null unique
);

create table public.usuarios (
  id              bigint generated always as identity primary key,
  email           text not null,
  hash_contrasena text not null,
  nombre          text not null,
  apellido        text not null,
  rol_codigo      text not null references public.roles (codigo),
  activo          boolean not null default true,
  creado_en       timestamptz not null default now(),
  actualizado_en  timestamptz not null default now()
);

-- Un mail por usuario, sin distinguir mayúsculas: Ana@x.com y ana@x.com son el mismo.
create unique index usuarios_email_unico on public.usuarios (lower(email));
create index usuarios_rol_idx on public.usuarios (rol_codigo);

-- Datos fijos
insert into public.roles (codigo, nombre) values
  ('paciente',              'Paciente'),
  ('medico_tratante',       'Médico tratante'),
  ('administrativo',        'Administrativo'),
  ('bioinformatico',        'Bioinformático'),
  ('transportista',         'Transportista'),
  ('gerente_medico',        'Gerente médico'),
  ('administrador_general', 'Administrador general');

-- Seguridad: RLS activado y sin políticas. La app se conecta como dueña de las tablas,
-- a la que RLS no afecta; la API pública de Supabase (anon, authenticated) no ve nada.
alter table public.roles    enable row level security;
alter table public.usuarios enable row level security;
