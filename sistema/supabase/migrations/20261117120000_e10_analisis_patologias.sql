-- Patologías que evalúa un análisis (E10): en el análisis inicial son una copia del diagnóstico
-- presuntivo del paciente; en un reanálisis (E12), la patología nueva, o ninguna si es solo por genes.
-- El resultado por patología lo carga E35 con el endpoint 7 de Apigen.
create table public.analisis_patologias (
  analisis_id  bigint not null references public.analisis (id) on delete restrict,
  patologia_id bigint not null references public.patologias (id) on delete restrict,
  resultado    text check (resultado in ('positivo', 'portador', 'negativo')),
  primary key (analisis_id, patologia_id)
);

create index analisis_patologias_patologia_idx on public.analisis_patologias (patologia_id);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.analisis_patologias enable row level security;
