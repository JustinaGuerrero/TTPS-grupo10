-- Apigen v1: cambios que pidieron el PO y los docentes en la clase del 27/10
--
--   1. "Probablemente patogénica" no hace diagnóstico. La clasificación pasa a una tabla propia.
--   2. Las variantes se identifican por su nombre HGVS codificante: GEN:c.… (o c.… con contexto).
--   3. Genes recesivos de la lista ACMG: hallazgo secundario solo con dos variantes.
--   4. El gerente médico de cada grupo puede dar de alta patologías nuevas.
--   5. Genes de todo el genoma: la lista y sus variantes las carga cargar_clinvar_v2.py.
--
-- IMPORTANTE: esta migración rehace la tabla variante (queda vacía).
-- Después de aplicarla hay que correr carga/cargar_clinvar_v2.py.

---------------------------------------------------------------------------
-- 0. Lo que se reemplaza
---------------------------------------------------------------------------
drop view if exists public.variantes;
drop view if exists public.genes_hallazgos_secundarios;
drop function if exists public.hallazgos_secundarios(text[], text);
drop function if exists public.hallazgos_secundarios(text[], text[]);
drop function if exists public.confirma_diagnostico(text, text[]);
drop function if exists public.genes_por_patologia(text);
drop function if exists public._validar_variantes(text[]);
drop table if exists public.variante;

---------------------------------------------------------------------------
-- 1. Clasificación: la regla vive en una tabla, no en el script
---------------------------------------------------------------------------
create table public.clasificacion (
  id            smallint primary key,
  valor_clinvar text not null unique,
  clasificacion text not null
    check (clasificacion in ('patogenica', 'probablemente_patogenica', 'vus', 'benigna'))
);

-- Solo 'patogenica' confirma diagnóstico y cuenta como hallazgo secundario.
-- Para cambiar un criterio alcanza con un update en esta tabla.
insert into public.clasificacion (id, valor_clinvar, clasificacion) values
  (1, 'Pathogenic',                                   'patogenica'),
  (2, 'Pathogenic/Likely pathogenic',                 'patogenica'),  -- decisión del grupo
  (3, 'Likely pathogenic',                            'probablemente_patogenica'),
  (4, 'Uncertain significance',                       'vus'),
  (5, 'Conflicting classifications of pathogenicity', 'vus'),
  (6, 'Conflicting interpretations of pathogenicity', 'vus'),
  (7, 'Likely benign',                                'benigna'),
  (8, 'Benign/Likely benign',                         'benigna'),
  (9, 'Benign',                                       'benigna');

---------------------------------------------------------------------------
-- 3. Herencia de los genes ACMG (null = dominante: alcanza con una variante)
---------------------------------------------------------------------------
alter table public.gen
  add column herencia_acmg text check (herencia_acmg in ('recesiva', 'ligada_x'));

update public.gen set herencia_acmg = 'recesiva'
where simbolo in ('BTD', 'CYP27A1', 'HFE', 'GAA', 'RPE65', 'CASQ2', 'TRDN', 'MUTYH', 'ATP7B');

update public.gen set herencia_acmg = 'ligada_x'
where simbolo in ('GLA', 'OTC', 'ABCD1');

---------------------------------------------------------------------------
-- 2 y 5. Variantes: compactas, identificadas por gen + HGVS codificante
---------------------------------------------------------------------------
create table public.variante (
  clinvar_id       integer primary key,
  gen_simbolo      text not null references public.gen (simbolo),
  transcripto      text not null,          -- NM_000152.5
  hgvs_c           text not null,          -- c.-32-13T>G
  proteina         text,                   -- p.Asn409Ser (si ClinVar la informa)
  clasificacion_id smallint not null references public.clasificacion (id)
);

create index variante_gen_hgvs_idx on public.variante (gen_simbolo, hgvs_c);

---------------------------------------------------------------------------
-- 4. Patologías que da de alta el gerente médico de cada grupo
---------------------------------------------------------------------------
create table public.patologia_grupo (
  grupo_id text not null,
  codigo   text not null,
  nombre   text not null,
  creada   timestamptz not null default now(),
  primary key (grupo_id, codigo)
);

create table public.patologia_grupo_gen (
  grupo_id    text not null,
  codigo      text not null,
  gen_simbolo text not null references public.gen (simbolo),
  primary key (grupo_id, codigo, gen_simbolo),
  foreign key (grupo_id, codigo)
    references public.patologia_grupo (grupo_id, codigo) on delete cascade
);

---------------------------------------------------------------------------
-- Vistas que leen los grupos
---------------------------------------------------------------------------
create view public.variantes with (security_invoker = true) as
  select v.gen_simbolo || ':' || v.hgvs_c as id,
         v.gen_simbolo                    as gen,
         v.transcripto,
         v.hgvs_c,
         v.proteina,
         c.clasificacion,
         c.valor_clinvar                  as clasificacion_clinvar,
         v.clinvar_id
  from public.variante v
  join public.clasificacion c on c.id = v.clasificacion_id;

create view public.genes_hallazgos_secundarios with (security_invoker = true) as
  select simbolo                              as gen,
         condicion_acmg                       as condicion,
         coalesce(herencia_acmg, 'dominante') as herencia
  from public.gen
  where es_hallazgo_secundario;

---------------------------------------------------------------------------
-- Seguridad: se lee todo, se escribe solo a través de alta_patologia
---------------------------------------------------------------------------
alter table public.clasificacion       enable row level security;
alter table public.variante            enable row level security;
alter table public.patologia_grupo     enable row level security;
alter table public.patologia_grupo_gen enable row level security;

create policy "lectura publica" on public.clasificacion       for select to anon, authenticated using (true);
create policy "lectura publica" on public.variante            for select to anon, authenticated using (true);
create policy "lectura publica" on public.patologia_grupo     for select to anon, authenticated using (true);
create policy "lectura publica" on public.patologia_grupo_gen for select to anon, authenticated using (true);

revoke all on public.clasificacion, public.variante, public.patologia_grupo,
              public.patologia_grupo_gen, public.variantes, public.genes_hallazgos_secundarios
  from anon, authenticated;

grant select on public.clasificacion, public.variante, public.patologia_grupo,
                public.patologia_grupo_gen, public.variantes, public.genes_hallazgos_secundarios
  to anon, authenticated;

---------------------------------------------------------------------------
-- Funciones internas
---------------------------------------------------------------------------

-- Genes de una patología: primero las 6 base, después las del grupo
create function public._genes_de_patologia(p_patologia text, p_grupo_id text default null)
returns text[] language plpgsql stable security definer set search_path = '' as $$
declare v_genes text[];
begin
  if exists (select 1 from public.patologia p where p.codigo = p_patologia) then
    select array_agg(pg.gen_simbolo order by pg.gen_simbolo) into v_genes
    from public.patologia_gen pg
    where pg.patologia_codigo = p_patologia;
  elsif p_grupo_id is not null and exists (
    select 1 from public.patologia_grupo g
    where g.grupo_id = p_grupo_id and g.codigo = p_patologia
  ) then
    select array_agg(gg.gen_simbolo order by gg.gen_simbolo) into v_genes
    from public.patologia_grupo_gen gg
    where gg.grupo_id = p_grupo_id and gg.codigo = p_patologia;
  else
    raise exception 'Patología inexistente: %', p_patologia;
  end if;
  return coalesce(v_genes, '{}');
end $$;

-- Traduce cada variante recibida a una fila de la tabla.
-- Formatos aceptados:
--   GAA:c.-32-13T>G             gen + HGVS codificante
--   c.-32-13T>G                 solo si hay genes de contexto (la patología)
--   NM_000152.5:c.-32-13T>G     transcripto + HGVS
--   NM_000152.5(GAA):c.-32-13T>G  como lo escribe ClinVar
-- Una variante repetida se devuelve repetida (homocigota).
create function public._resolver_variantes(p_variantes text[], p_genes_contexto text[] default null)
returns table (r_posicion int, r_entrada text, r_clinvar_id int, r_gen text,
               r_hgvs_c text, r_clasificacion text)
language plpgsql stable security definer set search_path = '' as $$
declare
  v_pos     bigint;
  v_entrada text;
  v_m       text[];
  v_tr      text;
  v_gen     text;
  v_c       text;
  v_cant    int;
  v_clases  int;
begin
  for v_entrada, v_pos in
    select trim(e), o from unnest(coalesce(p_variantes, '{}')) with ordinality as x(e, o)
  loop
    v_tr := null; v_gen := null; v_c := null;

    if v_entrada ~ '^NM_[0-9]+\.[0-9]+(\([A-Za-z0-9._-]+\))?:c\.\S+$' then
      v_m   := regexp_match(v_entrada, '^(NM_[0-9]+\.[0-9]+)(?:\(([A-Za-z0-9._-]+)\))?:(c\.\S+)$');
      v_tr  := v_m[1];
      v_gen := v_m[2];
      v_c   := v_m[3];
    elsif v_entrada ~ '^[A-Za-z0-9._-]+:c\.\S+$' then
      v_m   := regexp_match(v_entrada, '^([A-Za-z0-9._-]+):(c\.\S+)$');
      v_gen := v_m[1];
      v_c   := v_m[2];
    elsif v_entrada ~ '^c\.\S+$' then
      if p_genes_contexto is null then
        raise exception 'Indicá el gen de la variante, por ejemplo GEN:%', v_entrada;
      end if;
      v_c := v_entrada;
    else
      raise exception 'Formato de variante inválido: % (usá GEN:c.… o c.…)', v_entrada;
    end if;

    -- Acepta el gen en mayúsculas o minúsculas
    if v_gen is not null then
      select g.simbolo into v_gen from public.gen g where upper(g.simbolo) = upper(v_gen) limit 1;
      if v_gen is null then
        raise exception 'Variante inexistente: %', v_entrada;
      end if;
    end if;

    select count(*), count(distinct v.clasificacion_id) into v_cant, v_clases
    from public.variante v
    where v.hgvs_c = v_c
      and (v_gen is null or v.gen_simbolo = v_gen)
      and (v_tr  is null or v.transcripto = v_tr)
      and (v_gen is not null or v_tr is not null or v.gen_simbolo = any(p_genes_contexto));

    if v_cant = 0 then
      raise exception 'Variante inexistente: %', v_entrada;
    end if;
    if v_clases > 1 then
      raise exception 'Variante ambigua: %. Indicá el transcripto, por ejemplo NM_…:%', v_entrada, v_c;
    end if;

    return query
      select v_pos::int, v_entrada, v.clinvar_id, v.gen_simbolo, v.hgvs_c, c.clasificacion
      from public.variante v
      join public.clasificacion c on c.id = v.clasificacion_id
      where v.hgvs_c = v_c
        and (v_gen is null or v.gen_simbolo = v_gen)
        and (v_tr  is null or v.transcripto = v_tr)
        and (v_gen is not null or v_tr is not null or v.gen_simbolo = any(p_genes_contexto))
      order by v.clinvar_id
      limit 1;
  end loop;
end $$;

---------------------------------------------------------------------------
-- Funciones públicas
---------------------------------------------------------------------------

-- genesPorPatologia
create function public.genes_por_patologia(p_patologia text, p_grupo_id text default null)
returns text[] language plpgsql stable security definer set search_path = '' as $$
begin
  return public._genes_de_patologia(p_patologia, p_grupo_id);
end $$;

-- confirmaDiagnostico: true si alguna variante es patogénica en un gen de la patología.
-- Alcanza con una (respuesta del PO, 27/10).
create function public.confirma_diagnostico(
  p_patologia text,
  p_variantes text[],
  p_grupo_id  text default null
)
returns boolean language plpgsql stable security definer set search_path = '' as $$
declare v_genes text[];
begin
  v_genes := public._genes_de_patologia(p_patologia, p_grupo_id);
  return exists (
    select 1
    from public._resolver_variantes(p_variantes, v_genes) r
    where r.r_clasificacion = 'patogenica'
      and r.r_gen = any(v_genes)
  );
end $$;

-- hallazgosSecundarios: variantes patogénicas en genes ACMG ajenos a las patologías sospechadas.
-- En genes recesivos hacen falta dos variantes (distintas, o la misma repetida).
create function public.hallazgos_secundarios(
  p_variantes          text[],
  p_excluir_patologias text[] default null,
  p_grupo_id           text   default null
)
returns table (variante text, gen text, hgvs_c text, clasificacion text,
               condicion text, herencia text, copias int)
language plpgsql stable security definer set search_path = '' as $$
#variable_conflict use_column
declare
  v_excluidos text[] := '{}';
  v_p         text;
begin
  foreach v_p in array coalesce(p_excluir_patologias, '{}') loop
    v_excluidos := v_excluidos || public._genes_de_patologia(v_p, p_grupo_id);
  end loop;

  return query
  with r as (
    select * from public._resolver_variantes(p_variantes, null)
  ),
  pat as (
    select r.r_gen as g, r.r_hgvs_c as c, count(*)::int as n
    from r
    where r.r_clasificacion = 'patogenica'
    group by r.r_gen, r.r_hgvs_c
  ),
  por_gen as (
    select pat.g, sum(pat.n)::int as total from pat group by pat.g
  )
  select pat.g || ':' || pat.c,
         pat.g,
         pat.c,
         'patogenica'::text,
         ge.condicion_acmg,
         coalesce(ge.herencia_acmg, 'dominante'),
         pat.n
  from pat
  join por_gen pg on pg.g = pat.g
  join public.gen ge on ge.simbolo = pat.g
  where ge.es_hallazgo_secundario
    and not (pat.g = any(v_excluidos))
    and (ge.herencia_acmg is distinct from 'recesiva' or pg.total >= 2)
  order by pat.g, pat.c;
end $$;

-- Lista de patologías: las 6 base más las del grupo que pregunta
create function public.listar_patologias(p_grupo_id text default null)
returns table (codigo text, nombre text, genes text[], de_grupo boolean)
language plpgsql stable security definer set search_path = '' as $$
#variable_conflict use_column
begin
  return query
  select p.codigo, p.nombre, array_agg(pg.gen_simbolo order by pg.gen_simbolo), false
  from public.patologia p
  join public.patologia_gen pg on pg.patologia_codigo = p.codigo
  group by p.codigo, p.nombre
  union all
  select g.codigo, g.nombre, array_agg(gg.gen_simbolo order by gg.gen_simbolo), true
  from public.patologia_grupo g
  join public.patologia_grupo_gen gg on gg.grupo_id = g.grupo_id and gg.codigo = g.codigo
  where g.grupo_id = p_grupo_id
  group by g.codigo, g.nombre
  order by 4, 1;
end $$;

-- Alta (o modificación) de una patología del grupo. La usa el gerente médico.
create function public.alta_patologia(
  p_grupo_id text,
  p_codigo   text,
  p_nombre   text,
  p_genes    text[]
)
returns table (codigo text, nombre text, genes text[])
language plpgsql volatile security definer set search_path = '' as $$
#variable_conflict use_column
declare
  v_g     text;
  v_canon text;
  v_genes text[] := '{}';
begin
  if coalesce(trim(p_grupo_id), '') = '' or length(p_grupo_id) > 40 then
    raise exception 'p_grupo_id inválido';
  end if;
  if p_codigo is null or p_codigo !~ '^[A-Z0-9_]{2,30}$' then
    raise exception 'Código inválido: % (mayúsculas, números o _, de 2 a 30 caracteres)', p_codigo;
  end if;
  if exists (select 1 from public.patologia p where p.codigo = p_codigo) then
    raise exception 'El código % es de una patología base y no se puede modificar', p_codigo;
  end if;
  if coalesce(trim(p_nombre), '') = '' then
    raise exception 'Falta el nombre de la patología';
  end if;
  if coalesce(cardinality(p_genes), 0) = 0 then
    raise exception 'La patología necesita al menos un gen';
  end if;

  foreach v_g in array p_genes loop
    select g.simbolo into v_canon from public.gen g where upper(g.simbolo) = upper(trim(v_g)) limit 1;
    if v_canon is null then
      raise exception 'Gen inexistente: %', v_g;
    end if;
    if not (v_canon = any(v_genes)) then
      v_genes := v_genes || v_canon;
    end if;
  end loop;

  insert into public.patologia_grupo (grupo_id, codigo, nombre)
  values (p_grupo_id, p_codigo, trim(p_nombre))
  on conflict (grupo_id, codigo) do update set nombre = excluded.nombre;

  delete from public.patologia_grupo_gen gg
  where gg.grupo_id = p_grupo_id and gg.codigo = p_codigo;

  insert into public.patologia_grupo_gen (grupo_id, codigo, gen_simbolo)
  select p_grupo_id, p_codigo, unnest(v_genes);

  return query select p_codigo, trim(p_nombre), v_genes;
end $$;

---------------------------------------------------------------------------
-- Permisos de las funciones: las internas no se exponen
---------------------------------------------------------------------------
revoke execute on function public._genes_de_patologia(text, text)   from public, anon, authenticated;
revoke execute on function public._resolver_variantes(text[], text[]) from public, anon, authenticated;

revoke execute on function public.genes_por_patologia(text, text)                 from public;
revoke execute on function public.confirma_diagnostico(text, text[], text)        from public;
revoke execute on function public.hallazgos_secundarios(text[], text[], text)     from public;
revoke execute on function public.listar_patologias(text)                         from public;
revoke execute on function public.alta_patologia(text, text, text, text[])        from public;

grant execute on function public.genes_por_patologia(text, text)             to anon, authenticated;
grant execute on function public.confirma_diagnostico(text, text[], text)    to anon, authenticated;
grant execute on function public.hallazgos_secundarios(text[], text[], text) to anon, authenticated;
grant execute on function public.listar_patologias(text)                     to anon, authenticated;
grant execute on function public.alta_patologia(text, text, text, text[])    to anon, authenticated;

notify pgrst, 'reload schema';
