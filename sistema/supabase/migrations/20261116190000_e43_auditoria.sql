-- Registro de cambios (E43, G16): una fila por cada campo que cambia en un paciente, un estudio o
-- un sample set. La guarda registrar() de src/core/auditoria dentro de la transacción de quien
-- cambia el dato. El cambio de estado de un estudio no se duplica acá: ya está en historial_estados.

create table public.auditoria (
  id             bigint generated always as identity primary key,
  -- Sin clave foránea: apunta a pacientes, estudios o sample_sets según `entidad`.
  entidad        text not null check (entidad in ('paciente', 'estudio', 'sample_set')),
  entidad_id     bigint not null,
  accion         text not null check (accion in ('alta', 'modificacion', 'baja', 'estado')),
  campo          text not null check (btrim(campo) <> ''),
  -- Los valores se guardan como texto. Nulos en un alta (no había) o una baja (ya no hay).
  valor_anterior text,
  valor_nuevo    text,
  -- Nulo cuando el cambio lo hace el sistema (tareas programadas, bot, FedEx).
  usuario_id     bigint references public.usuarios (id) on delete restrict,
  creado_en      timestamptz not null default now(),
  detalle        text
);

-- El historial de una entidad, del más nuevo al más viejo.
create index auditoria_entidad_idx on public.auditoria (entidad, entidad_id, creado_en);
-- La lista del administrador general filtra por usuario y por fecha.
create index auditoria_usuario_idx on public.auditoria (usuario_id);
create index auditoria_creado_en_idx on public.auditoria (creado_en);

-- El registro nunca se modifica ni se borra.
create function public.auditoria_solo_insertar() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'El registro de cambios solo se inserta: no se modifica ni se borra.';
end;
$$;

create trigger auditoria_inmutable
  before update or delete on public.auditoria
  for each row execute function public.auditoria_solo_insertar();

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.auditoria enable row level security;
