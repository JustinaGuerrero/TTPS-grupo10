-- Auxiliar: rechaza ids de variante que no existen (decisión 8)
create function public._validar_variantes(p_variantes text[])
returns void language plpgsql stable security definer set search_path = '' as $$
declare v_falta text;
begin
  select x.id into v_falta
  from unnest(p_variantes) as x(id)
  where not exists (select 1 from public.variante v where v.clinvar_id = x.id)
  limit 1;
  if v_falta is not null then
    raise exception 'Variante inexistente: %', v_falta;
  end if;
end $$;

-- genesPorPatologia
create function public.genes_por_patologia(p_patologia text)
returns text[] language plpgsql stable security definer set search_path = '' as $$
declare v_genes text[];
begin
  if not exists (select 1 from public.patologia where codigo = p_patologia) then
    raise exception 'Patología inexistente: %', p_patologia;
  end if;
  select array_agg(gen_simbolo order by gen_simbolo) into v_genes
  from public.patologia_gen
  where patologia_codigo = p_patologia;
  return v_genes;
end $$;

-- confirmaDiagnostico
create function public.confirma_diagnostico(p_patologia text, p_variantes text[])
returns boolean language plpgsql stable security definer set search_path = '' as $$
begin
  if not exists (select 1 from public.patologia where codigo = p_patologia) then
    raise exception 'Patología inexistente: %', p_patologia;
  end if;
  perform public._validar_variantes(p_variantes);
  return exists (
    select 1
    from public.variante v
    join public.patologia_gen pg on pg.gen_simbolo = v.gen_simbolo
    where pg.patologia_codigo = p_patologia
      and v.clinvar_id = any(p_variantes)
      and v.es_patogenica
  );
end $$;

-- hallazgosSecundarios
create function public.hallazgos_secundarios(p_variantes text[], p_excluir_patologia text default null)
returns table (clinvar_id text, gen text, nombre text, clasificacion text, condicion text)
language plpgsql stable security definer set search_path = '' as $$
#variable_conflict use_column
begin
  perform public._validar_variantes(p_variantes);
  return query
    select v.clinvar_id, v.gen_simbolo, v.nombre, v.clasificacion, g.condicion_acmg
    from public.variante v
    join public.gen g on g.simbolo = v.gen_simbolo
    where v.clinvar_id = any(p_variantes)
      and v.es_patogenica
      and g.es_hallazgo_secundario
      and v.gen_simbolo not in (
        select pg.gen_simbolo from public.patologia_gen pg
        where pg.patologia_codigo = p_excluir_patologia
      );
end $$;

-- Permisos: la auxiliar no se expone, las otras tres sí
revoke execute on function public._validar_variantes(text[]) from public, anon, authenticated;
revoke execute on function public.genes_por_patologia(text) from public;
revoke execute on function public.confirma_diagnostico(text, text[]) from public;
revoke execute on function public.hallazgos_secundarios(text[], text) from public;

grant execute on function public.genes_por_patologia(text) to anon, authenticated;
grant execute on function public.confirma_diagnostico(text, text[]) to anon, authenticated;
grant execute on function public.hallazgos_secundarios(text[], text) to anon, authenticated;