-- Notificaciones (sesión 6 de docs/guia-agentes.md, decisión S11, E39).
-- Tabla de docs/modelo-datos.md, sección 8: paso 3 del orden sugerido.
-- Cada fila es un aviso de la lista de pendientes del usuario. La guarda notificar() de
-- src/core/notificaciones, que además manda el mail. En Python el modelo se llama Aviso.

create table public.notificaciones (
  id              bigint generated always as identity primary key,
  usuario_id      bigint not null references public.usuarios (id) on delete restrict,
  asunto          text not null check (btrim(asunto) <> ''),
  mensaje         text not null check (btrim(mensaje) <> ''),
  -- Ruta de la tarea pendiente dentro del sistema, por ejemplo /estudios/42.
  link            text not null check (link like '/%'),
  estudio_id      bigint references public.estudios (id) on delete restrict,
  creada_en       timestamptz not null default now(),
  -- Nulo si el mail no salió (por ejemplo, falló el servidor de mail).
  mail_enviado_en timestamptz,
  leida_en        timestamptz
);

-- La lista de avisos sin leer del usuario y el contador del layout.
create index notificaciones_usuario_leida_idx on public.notificaciones (usuario_id, leida_en);
create index notificaciones_estudio_idx on public.notificaciones (estudio_id);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.notificaciones enable row level security;
