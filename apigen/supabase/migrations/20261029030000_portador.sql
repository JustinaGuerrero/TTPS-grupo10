-- Apigen v1.1: portador en el diagnóstico
--
-- En una patología recesiva (Pompe, Gaucher, MPS 1, ASMD), con una sola variante
-- patogénica la persona es PORTADORA: no está enferma, pero puede transmitirla.
-- Para confirmar hacen falta las dos copias del gen afectadas: dos variantes
-- patogénicas distintas en el gen, o la misma repetida (homocigota).
-- En las ligadas al X (Fabry, MPS 2) alcanza con una.

---------------------------------------------------------------------------
-- Herencia en las patologías de los grupos
---------------------------------------------------------------------------
alter table public.patologia_grupo
  add column herencia text not null default 'autosomica_recesiva'
  check (herencia in ('autosomica_recesiva', 'autosomica_dominante', 'ligada_al_x'));

---------------------------------------------------------------------------
-- Interna: herencia de una patología (base o del grupo)
---------------------------------------------------------------------------
create function public._herencia_de_patologia(p_patologia text, p_grupo_id text default null)
returns text language plpgsql stable security definer set search_path = '' as $$
declare v_herencia text;
begin
  select p.herencia into v_herencia from public.patologia p where p.codigo = p_patologia;
  if v_herencia is null and p_grupo_id is not null then
    select g.herencia into v_herencia from public.patologia_grupo g
    where g.grupo_id = p_grupo_id and g.codigo = p_patologia;
  end if;
  if v_herencia is null then
    raise exception 'Patología inexistente: %', p_patologia;
  end if;
  return v_herencia;
end $$;

---------------------------------------------------------------------------
-- Nueva: resultado del diagnóstico (positivo, portador o negativo)
---------------------------------------------------------------------------
create function public.resultado_diagnostico(
  p_patologia text,
  p_variantes text[],
  p_grupo_id  text default null
)
returns text language plpgsql stable security definer set search_path = '' as $$
declare
  v_genes    text[];
  v_herencia text;
  v_copias   int;
begin
  v_genes    := public._genes_de_patologia(p_patologia, p_grupo_id);
  v_herencia := public._herencia_de_patologia(p_patologia, p_grupo_id);

  -- Máximo de copias patogénicas en un mismo gen de la patología.
  -- Una variante repetida (homocigota) cuenta dos veces.
  select coalesce(max(x.n), 0) into v_copias
  from (
    select r.r_gen, count(*)::int as n
    from public._resolver_variantes(p_variantes, v_genes) r
    where r.r_clasificacion = 'patogenica'
      and r.r_gen = any(v_genes)
    group by r.r_gen
  ) x;

  if v_copias = 0 then
    return 'negativo';
  elsif v_herencia = 'autosomica_recesiva' and v_copias < 2 then
    return 'portador';
  else
    return 'positivo';
  end if;
end $$;

---------------------------------------------------------------------------
-- confirmaDiagnostico: true solo si el resultado es positivo
---------------------------------------------------------------------------
create or replace function public.confirma_diagnostico(
  p_patologia text,
  p_variantes text[],
  p_grupo_id  text default null
)
returns boolean language plpgsql stable security definer set search_path = '' as $$
begin
  return public.resultado_diagnostico(p_patologia, p_variantes, p_grupo_id) = 'positivo';
end $$;

---------------------------------------------------------------------------
-- listar_patologias: ahora también devuelve la herencia
---------------------------------------------------------------------------
drop function public.listar_patologias(text);

create function public.listar_patologias(p_grupo_id text default null)
returns table (codigo text, nombre text, herencia text, genes text[], de_grupo boolean)
language plpgsql stable security definer set search_path = '' as $$
#variable_conflict use_column
begin
  return query
  select p.codigo, p.nombre, p.herencia, array_agg(pg.gen_simbolo order by pg.gen_simbolo), false
  from public.patologia p
  join public.patologia_gen pg on pg.patologia_codigo = p.codigo
  group by p.codigo, p.nombre, p.herencia
  union all
  select g.codigo, g.nombre, g.herencia, array_agg(gg.gen_simbolo order by gg.gen_simbolo), true
  from public.patologia_grupo g
  join public.patologia_grupo_gen gg on gg.grupo_id = g.grupo_id and gg.codigo = g.codigo
  where g.grupo_id = p_grupo_id
  group by g.codigo, g.nombre, g.herencia
  order by 5, 1;
end $$;

---------------------------------------------------------------------------
-- alta_patologia: ahora recibe la herencia (por defecto, recesiva)
---------------------------------------------------------------------------
drop function public.alta_patologia(text, text, text, text[]);

create function public.alta_patologia(
  p_grupo_id text,
  p_codigo   text,
  p_nombre   text,
  p_genes    text[],
  p_herencia text default 'autosomica_recesiva'
)
returns table (codigo text, nombre text, herencia text, genes text[])
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
  if p_herencia is null or p_herencia not in ('autosomica_recesiva', 'autosomica_dominante', 'ligada_al_x') then
    raise exception 'Herencia inválida: % (autosomica_recesiva, autosomica_dominante o ligada_al_x)', p_herencia;
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

  insert into public.patologia_grupo (grupo_id, codigo, nombre, herencia)
  values (p_grupo_id, p_codigo, trim(p_nombre), p_herencia)
  on conflict (grupo_id, codigo) do update set nombre = excluded.nombre, herencia = excluded.herencia;

  delete from public.patologia_grupo_gen gg
  where gg.grupo_id = p_grupo_id and gg.codigo = p_codigo;

  insert into public.patologia_grupo_gen (grupo_id, codigo, gen_simbolo)
  select p_grupo_id, p_codigo, unnest(v_genes);

  return query select p_codigo, trim(p_nombre), p_herencia, v_genes;
end $$;

---------------------------------------------------------------------------
-- Permisos
---------------------------------------------------------------------------
revoke execute on function public._herencia_de_patologia(text, text) from public, anon, authenticated;

revoke execute on function public.resultado_diagnostico(text, text[], text)       from public;
revoke execute on function public.confirma_diagnostico(text, text[], text)        from public;
revoke execute on function public.listar_patologias(text)                         from public;
revoke execute on function public.alta_patologia(text, text, text, text[], text)  from public;

grant execute on function public.resultado_diagnostico(text, text[], text)      to anon, authenticated;
grant execute on function public.confirma_diagnostico(text, text[], text)       to anon, authenticated;
grant execute on function public.listar_patologias(text)                        to anon, authenticated;
grant execute on function public.alta_patologia(text, text, text, text[], text) to anon, authenticated;

notify pgrst, 'reload schema';
