-- Contrato del módulo de obras sociales (módulo 6, grupo 9, docs/apis/obras_sociales.md): la
-- solicitud se da de alta con el id de la obra social en el módulo, y la demanda de
-- reautorización se presenta sobre la misma solicitud. Cambia obras_sociales y
-- demandas_reautorizacion.

-- Id (UUID) de la obra social en el módulo. obras_sociales.codigo sigue siendo el código RNOS.
alter table public.obras_sociales add column id_modulo text;

-- Cuándo se subió la resolución judicial al módulo. Nulo mientras no salió (el módulo no
-- respondió): la tarea programada la vuelve a subir antes de leer la respuesta.
alter table public.demandas_reautorizacion add column presentada_en_modulo_en timestamptz;
