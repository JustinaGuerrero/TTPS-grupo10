-- Apigen v1.2: se saca la Mucopolisacaridosis tipo 2 (MPS2), pedido del profesor (10/11)
--
-- Se borran la patología, su gen (IDS) y todas las variantes de IDS.
-- Quedan 5 patologías base. cargar_clinvar_v2.py tampoco vuelve a cargar IDS.

---------------------------------------------------------------------------
-- Si una patología de un grupo usa IDS, no se borra nada: hay que avisarle antes
---------------------------------------------------------------------------
do $$
declare v_pat text;
begin
  select gg.grupo_id || '/' || gg.codigo into v_pat
  from public.patologia_grupo_gen gg
  where gg.gen_simbolo = 'IDS'
  limit 1;
  if v_pat is not null then
    raise exception 'La patología % usa el gen IDS: avisen a ese grupo antes de sacarlo', v_pat;
  end if;
end $$;

---------------------------------------------------------------------------
-- Variantes, patología y gen (en ese orden, por las claves foráneas)
---------------------------------------------------------------------------
delete from public.variante      where gen_simbolo = 'IDS';
delete from public.patologia_gen where patologia_codigo = 'MPS2';
delete from public.patologia     where codigo = 'MPS2';
delete from public.gen           where simbolo = 'IDS';

notify pgrst, 'reload schema';
