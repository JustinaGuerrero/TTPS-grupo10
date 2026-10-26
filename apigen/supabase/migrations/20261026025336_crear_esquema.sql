-- Tablas
create table public.patologia (
  codigo   text primary key,
  nombre   text not null,
  herencia text not null check (herencia in ('autosomica_recesiva', 'ligada_al_x'))
);

create table public.gen (
  simbolo                text primary key,
  es_hallazgo_secundario boolean not null default false,
  condicion_acmg         text
);

create table public.patologia_gen (
  patologia_codigo text not null references public.patologia (codigo),
  gen_simbolo      text not null references public.gen (simbolo),
  primary key (patologia_codigo, gen_simbolo)
);

create table public.variante (
  clinvar_id            text primary key,
  gen_simbolo           text not null references public.gen (simbolo),
  nombre                text not null,
  clasificacion_clinvar text not null,
  clasificacion         text not null check (clasificacion in ('patogenica', 'benigna', 'vus')),
  es_patogenica         boolean not null,
  actualizada           date not null default current_date
);

create index variante_gen_idx on public.variante (gen_simbolo);

-- Vistas que leen los grupos
create view public.variantes with (security_invoker = true) as
  select clinvar_id, gen_simbolo as gen, nombre, clasificacion, clasificacion_clinvar
  from public.variante;

create view public.genes_hallazgos_secundarios with (security_invoker = true) as
  select simbolo as gen, condicion_acmg as condicion
  from public.gen
  where es_hallazgo_secundario;

-- Seguridad: se lee todo, no se escribe nada
alter table public.patologia     enable row level security;
alter table public.gen           enable row level security;
alter table public.patologia_gen enable row level security;
alter table public.variante      enable row level security;

create policy "lectura publica" on public.patologia     for select to anon, authenticated using (true);
create policy "lectura publica" on public.gen           for select to anon, authenticated using (true);
create policy "lectura publica" on public.patologia_gen for select to anon, authenticated using (true);
create policy "lectura publica" on public.variante      for select to anon, authenticated using (true);

revoke all on public.patologia, public.gen, public.patologia_gen, public.variante,
              public.variantes, public.genes_hallazgos_secundarios
  from anon, authenticated;

grant select on public.patologia, public.gen, public.patologia_gen, public.variante,
                public.variantes, public.genes_hallazgos_secundarios
  to anon, authenticated;