-- Estudio y máquina de estados (sesión 5 de docs/guia-agentes.md).
-- Tablas de docs/modelo-datos.md, pasos 5 y 6 del orden sugerido, cada una completa: perfil de
-- médico, pacientes, estudios, historial de estados y análisis con sus genes.
-- Quedan para su escenario las que dependen de patologias (E36) o de terminos_snomed:
-- analisis_patologias, diagnosticos_presuntivos, paciente_sintomas y familiares.

-- Teléfono del usuario (E01, E02, E06). Nulo para el administrador general.
alter table public.usuarios add column telefono text;

-- Perfil 1:1 de los usuarios con rol medico_tratante o gerente_medico (E01).
-- Nombre, apellido, mail y teléfono están en usuarios.
create table public.medicos (
  usuario_id bigint primary key references public.usuarios (id) on delete restrict,
  matricula  text not null unique,
  creado_en  timestamptz not null default now()
);

-- Paciente (E06). Nombre, apellido, mail y teléfono están en su usuario, que usa también el
-- responsable del paciente menor.
create table public.pacientes (
  id                       bigint generated always as identity primary key,
  usuario_id               bigint not null unique references public.usuarios (id) on delete restrict,
  dni                      text not null unique,
  fecha_nacimiento         date not null,
  tipo_sospecha            text not null check (tipo_sospecha in ('clinica', 'familiar')),
  resumen_historia_clinica text not null,
  resumen_audio_path       text,
  familiograma_path        text,
  medico_tratante_id       bigint not null references public.medicos (usuario_id) on delete restrict,
  creado_en                timestamptz not null default now()
);

create index pacientes_medico_tratante_idx on public.pacientes (medico_tratante_id);

-- Los 16 estados del estudio del LEL. En Python, la fuente es EstadoEstudio
-- (src/core/estudios/estados.py); las dos listas tienen que coincidir.
create domain public.estado_estudio as text
  constraint estado_estudio_valido check (value in (
    'creado',
    'presupuestado',
    'pendiente_autorizacion',
    'rechazado_obra_social',
    'habilitado_turno',
    'turno_sacado',
    'listo_para_retirar',
    'en_camino_laboratorio',
    'en_laboratorio_central',
    'pendiente_autorizacion_ministerial',
    'pendiente_envio',
    'en_viaje_corea',
    'en_area_bioinformatica',
    'en_analisis',
    'finalizado',
    'requiere_nueva_extraccion'
  ));

-- Un solo estudio por paciente (observación O20): una sospecha nueva va por reanálisis.
-- El estado lo cambia solo cambiar_estado() de src/core/estudios.
create table public.estudios (
  id                        bigint generated always as identity primary key,
  paciente_id               bigint not null unique references public.pacientes (id) on delete restrict,
  medico_tratante_id        bigint not null references public.medicos (usuario_id) on delete restrict,
  estado                    public.estado_estudio not null,
  pompe_urgente             boolean not null default false,
  datos_crudos_path         text,
  datos_crudos_cargados_en  timestamptz,
  datos_crudos_cargados_por bigint references public.usuarios (id) on delete restrict,
  creado_en                 timestamptz not null default now(),
  actualizado_en            timestamptz not null default now(),
  -- Código legible para la orden de extracción, el bot y el CCB: EX-2026-00042.
  codigo                    text not null unique generated always as (
    'EX-'
    || extract(year from creado_en at time zone 'America/Argentina/Buenos_Aires')::integer::text
    || '-' || lpad(id::text, greatest(5, length(id::text)), '0')
  ) stored
);

create index estudios_estado_idx on public.estudios (estado);
create index estudios_medico_tratante_idx on public.estudios (medico_tratante_id);
create index estudios_datos_crudos_cargados_por_idx on public.estudios (datos_crudos_cargados_por);

-- Una fila por cada cambio de estado, con fecha y usuario (decisión S9).
-- usuario_id es nulo cuando el cambio lo dispara el sistema (bot, FedEx, tareas programadas).
create table public.historial_estados (
  id              bigint generated always as identity primary key,
  estudio_id      bigint not null references public.estudios (id) on delete restrict,
  estado_anterior public.estado_estudio,
  estado_nuevo    public.estado_estudio not null,
  usuario_id      bigint references public.usuarios (id) on delete restrict,
  motivo          text,
  creado_en       timestamptz not null default now(),
  -- Solo la primera fila, la del alta en Creado, no tiene estado anterior. Ninguna transición
  -- vuelve a Creado.
  constraint historial_estados_primera_fila
    check ((estado_anterior is null) = (estado_nuevo = 'creado'))
);

create index historial_estados_estudio_idx on public.historial_estados (estudio_id, creado_en);
create index historial_estados_usuario_idx on public.historial_estados (usuario_id);

-- Cada vuelta de análisis del exoma: la inicial, que se crea con el estudio, y un reanálisis
-- por cada pedido de E12, sobre los mismos datos crudos.
create table public.analisis (
  id                           bigint generated always as identity primary key,
  estudio_id                   bigint not null references public.estudios (id) on delete restrict,
  numero                       smallint not null check (numero > 0),
  tipo                         text not null check (tipo in ('inicial', 'reanalisis')),
  evalua_hallazgos_secundarios boolean not null,
  solicitado_por               bigint not null references public.usuarios (id) on delete restrict,
  solicitado_en                timestamptz not null default now(),
  disponible_en                timestamptz,
  bioinformatico_id            bigint references public.usuarios (id) on delete restrict,
  tomado_en                    timestamptz,
  finalizado_en                timestamptz,
  resultado                    text check (resultado in ('positivo', 'portador', 'negativo')),
  resultado_path               text,
  fecha_reevaluacion           date,
  constraint analisis_numero_unico unique (estudio_id, numero),
  constraint analisis_inicial_es_el_primero check ((numero = 1) = (tipo = 'inicial'))
);

-- Un solo análisis abierto por estudio.
create unique index analisis_uno_abierto_por_estudio
  on public.analisis (estudio_id) where finalizado_en is null;
create index analisis_solicitado_por_idx on public.analisis (solicitado_por);
create index analisis_bioinformatico_idx on public.analisis (bioinformatico_id);

-- Genes que se evalúan en un análisis. El catálogo y la relación patología–gen son de Apigen.
create table public.analisis_genes (
  analisis_id     bigint not null references public.analisis (id) on delete restrict,
  gen_simbolo     text not null check (gen_simbolo <> '' and gen_simbolo = btrim(gen_simbolo)),
  agregado_a_mano boolean not null,
  primary key (analisis_id, gen_simbolo)
);

-- Seguridad: igual que en la migración inicial, RLS activado y sin políticas.
alter table public.medicos           enable row level security;
alter table public.pacientes         enable row level security;
alter table public.estudios          enable row level security;
alter table public.historial_estados enable row level security;
alter table public.analisis          enable row level security;
alter table public.analisis_genes    enable row level security;
