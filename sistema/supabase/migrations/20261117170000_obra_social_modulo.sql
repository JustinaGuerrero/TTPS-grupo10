-- Autorización de la obra social desde su módulo (módulo 6, G22): el sistema da de alta el
-- estudio en el módulo de obras sociales y toma de ahí la respuesta. Cambia coberturas, de la
-- migración de obra social.

-- Id que devuelve el módulo al dar de alta el estudio. Nulo mientras el alta no salió (el módulo no
-- respondió): la tarea programada la reintenta. Una demanda de reautorización da de alta el
-- estudio otra vez y lo reemplaza.
alter table public.coberturas add column id_estudio_modulo text;

-- La respuesta la puede registrar el módulo (respondida_por nulo) o un administrativo, a mano,
-- cuando el módulo no responde.
alter table public.coberturas drop constraint coberturas_respuesta_registrada;
alter table public.coberturas add constraint coberturas_respuesta_registrada
  check (estado = 'pendiente' or respondida_en is not null);
