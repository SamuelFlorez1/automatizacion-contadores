-- =============================================================================
-- Despacho Contable Automatizado — schema inicial (Fase 1)
-- =============================================================================
-- Convenciones:
--   * timestamps en UTC, zona horaria negocio = America/Bogota se aplica en app
--   * PKs UUID (gen_random_uuid())
--   * multi-tenant por firm_id; RLS activa desde el día 1
--   * money = numeric(18,2); FX = numeric(18,6)
--   * status enums via CHECK para poder migrar rápido; ENUM real cuando se estabilice
-- =============================================================================

create extension if not exists "pgcrypto";
create extension if not exists "citext";

-- -----------------------------------------------------------------------------
-- Firms (despachos contables)
-- -----------------------------------------------------------------------------
create table if not exists firms (
    id            uuid primary key default gen_random_uuid(),
    name          text not null,
    nit           text not null unique,
    city          text not null default 'Bogotá',
    created_at    timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- Users (perfil ligado a auth.users de Supabase)
-- -----------------------------------------------------------------------------
create table if not exists users (
    id            uuid primary key references auth.users(id) on delete cascade,
    firm_id       uuid not null references firms(id) on delete cascade,
    email         citext not null unique,
    full_name     text,
    role          text not null check (role in ('firm_admin', 'accountant', 'client')),
    client_id     uuid, -- si role='client' apunta a clients.id (se agrega FK después)
    created_at    timestamptz not null default now()
);
create index if not exists users_firm_idx on users(firm_id);

-- -----------------------------------------------------------------------------
-- Clients (empresas atendidas por el despacho)
-- -----------------------------------------------------------------------------
create table if not exists clients (
    id                   uuid primary key default gen_random_uuid(),
    firm_id              uuid not null references firms(id) on delete cascade,
    legal_name           text not null,
    trade_name           text,
    nit                  text not null,
    nit_dv               int  not null check (nit_dv between 0 and 10),
    tax_regime           text not null check (tax_regime in ('simple', 'ordinario', 'no_responsable_iva')),
    iva_frequency        text check (iva_frequency in ('bimestral', 'cuatrimestral', 'no_aplica')),
    ica_city             text default 'Bogotá',
    ica_activity_code    text,           -- código CIIU o tarifa ICA
    is_gran_contribuyente boolean not null default false,
    is_agente_retencion  boolean not null default false,
    default_currency     text not null default 'COP' check (default_currency in ('COP', 'USD')),
    phone                text,
    email                citext,
    address              text,
    created_at           timestamptz not null default now(),
    unique (firm_id, nit)
);
create index if not exists clients_firm_idx on clients(firm_id);

alter table users
    add constraint users_client_fk
    foreign key (client_id) references clients(id) on delete set null;

-- -----------------------------------------------------------------------------
-- Documents (todo archivo entrante: XML, PDF, imagen)
-- -----------------------------------------------------------------------------
create table if not exists documents (
    id             uuid primary key default gen_random_uuid(),
    firm_id        uuid not null references firms(id) on delete cascade,
    client_id      uuid not null references clients(id) on delete cascade,
    source         text not null check (source in ('whatsapp', 'email', 'upload', 'seed')),
    channel_ref    text,                 -- messageId de WhatsApp, thread id de email, etc.
    dedupe_key     text not null,        -- hash de contenido + fuente para idempotencia
    kind           text not null check (kind in ('invoice_xml', 'invoice_pdf', 'invoice_image', 'bank_statement', 'other')),
    original_name  text,
    mime_type      text,
    storage_path   text,                 -- ruta en Supabase Storage
    size_bytes     bigint,
    sha256         text,
    status         text not null default 'received'
                     check (status in ('received', 'parsing', 'parsed', 'error', 'ignored')),
    error_detail   text,
    received_at    timestamptz not null default now(),
    parsed_at      timestamptz,
    unique (firm_id, dedupe_key)
);
create index if not exists documents_client_idx on documents(client_id, received_at desc);
create index if not exists documents_status_idx on documents(status) where status in ('received','parsing','error');

-- -----------------------------------------------------------------------------
-- Invoices (encabezado) + líneas
-- -----------------------------------------------------------------------------
create table if not exists invoices (
    id                 uuid primary key default gen_random_uuid(),
    firm_id            uuid not null references firms(id) on delete cascade,
    client_id          uuid not null references clients(id) on delete cascade,
    document_id        uuid unique references documents(id) on delete set null,
    direction          text not null check (direction in ('recibida', 'emitida')),
    supplier_nit       text,
    supplier_name      text,
    customer_nit       text,
    customer_name      text,
    invoice_number     text not null,
    cufe               text,             -- código único DIAN (facturación electrónica)
    issue_date         date not null,
    due_date           date,
    currency           text not null default 'COP' check (currency in ('COP','USD')),
    fx_rate_to_cop     numeric(18,6),    -- si currency='USD'
    subtotal           numeric(18,2) not null default 0,
    iva                numeric(18,2) not null default 0,
    ica                numeric(18,2) not null default 0,
    rete_fuente        numeric(18,2) not null default 0,
    rete_iva           numeric(18,2) not null default 0,
    rete_ica           numeric(18,2) not null default 0,
    other_taxes        numeric(18,2) not null default 0,
    total              numeric(18,2) not null default 0,
    total_cop          numeric(18,2) not null default 0, -- total * fx si USD
    puc_account        text,             -- cuenta PUC sugerida (Fase 3)
    is_deductible      boolean,          -- Fase 3
    classification_confidence numeric(4,3), -- 0..1
    payment_status     text not null default 'pending'
                        check (payment_status in ('pending','partial','paid','void')),
    notes              text,
    created_at         timestamptz not null default now(),
    unique (firm_id, supplier_nit, invoice_number, direction)
);
create index if not exists invoices_client_date_idx on invoices(client_id, issue_date desc);
create index if not exists invoices_payment_idx on invoices(client_id, payment_status);

create table if not exists invoice_lines (
    id           uuid primary key default gen_random_uuid(),
    invoice_id   uuid not null references invoices(id) on delete cascade,
    line_no      int  not null,
    description  text not null,
    quantity     numeric(18,4) not null default 1,
    unit_price   numeric(18,2) not null default 0,
    subtotal     numeric(18,2) not null default 0,
    iva_rate     numeric(5,2)  not null default 0,
    iva_amount   numeric(18,2) not null default 0,
    total        numeric(18,2) not null default 0,
    unique (invoice_id, line_no)
);

-- -----------------------------------------------------------------------------
-- Bank accounts + transactions + reconciliation matches
-- -----------------------------------------------------------------------------
create table if not exists bank_accounts (
    id           uuid primary key default gen_random_uuid(),
    firm_id      uuid not null references firms(id) on delete cascade,
    client_id    uuid not null references clients(id) on delete cascade,
    bank_name    text not null,
    account_type text not null check (account_type in ('ahorros','corriente','tarjeta_credito')),
    account_number_masked text not null,
    currency     text not null default 'COP' check (currency in ('COP','USD')),
    created_at   timestamptz not null default now()
);

create table if not exists bank_transactions (
    id             uuid primary key default gen_random_uuid(),
    firm_id        uuid not null references firms(id) on delete cascade,
    client_id      uuid not null references clients(id) on delete cascade,
    bank_account_id uuid not null references bank_accounts(id) on delete cascade,
    tx_date        date not null,
    description    text not null,
    reference      text,
    amount         numeric(18,2) not null,  -- signo: + ingreso / - egreso
    currency       text not null default 'COP',
    balance_after  numeric(18,2),
    dedupe_key     text not null,           -- hash línea CSV + cuenta
    match_status   text not null default 'unmatched'
                    check (match_status in ('unmatched','matched','review','ignored')),
    created_at     timestamptz not null default now(),
    unique (firm_id, dedupe_key)
);
create index if not exists bank_tx_client_date_idx on bank_transactions(client_id, tx_date desc);
create index if not exists bank_tx_status_idx on bank_transactions(match_status);

create table if not exists reconciliation_matches (
    id                uuid primary key default gen_random_uuid(),
    firm_id           uuid not null references firms(id) on delete cascade,
    client_id         uuid not null references clients(id) on delete cascade,
    bank_transaction_id uuid not null references bank_transactions(id) on delete cascade,
    invoice_id        uuid references invoices(id) on delete set null,
    match_type        text not null check (match_type in ('exact','fuzzy','manual','transfer_internal')),
    confidence        numeric(4,3) not null,
    matched_amount    numeric(18,2) not null,
    reason            text,
    created_by        uuid references users(id),
    created_at        timestamptz not null default now()
);
create index if not exists recon_bank_idx on reconciliation_matches(bank_transaction_id);
create index if not exists recon_invoice_idx on reconciliation_matches(invoice_id);

-- -----------------------------------------------------------------------------
-- Tax obligations (calculadas en Fase 4)
-- -----------------------------------------------------------------------------
create table if not exists tax_obligations (
    id             uuid primary key default gen_random_uuid(),
    firm_id        uuid not null references firms(id) on delete cascade,
    client_id      uuid not null references clients(id) on delete cascade,
    kind           text not null check (kind in (
        'iva_bimestral','iva_cuatrimestral',
        'rete_fuente','rete_iva','rete_ica',
        'ica_bogota','simple_bimestral','simple_anual',
        'renta_pj_cuota1','renta_pj_cuota2','renta_gc_cuota1','renta_gc_cuota2','renta_gc_cuota3'
    )),
    period_label   text not null,        -- 'ene-feb-2026', '2026-05', etc.
    period_start   date not null,
    period_end     date not null,
    due_date       date not null,
    amount         numeric(18,2) not null default 0,
    status         text not null default 'pending'
                    check (status in ('pending','filed','paid','overdue','waived')),
    filed_at       timestamptz,
    paid_at        timestamptz,
    calculation_snapshot jsonb,          -- detalles del cálculo para auditoría
    created_at     timestamptz not null default now(),
    unique (client_id, kind, period_label)
);
create index if not exists tax_obligations_due_idx on tax_obligations(due_date) where status in ('pending','overdue');

-- -----------------------------------------------------------------------------
-- Conversations + messages (agente WhatsApp — Fase 5)
-- -----------------------------------------------------------------------------
create table if not exists conversations (
    id           uuid primary key default gen_random_uuid(),
    firm_id      uuid not null references firms(id) on delete cascade,
    client_id    uuid references clients(id) on delete set null,
    channel      text not null check (channel in ('whatsapp','email','web')),
    external_id  text,                   -- id chat/thread en la plataforma
    phone        text,
    status       text not null default 'active' check (status in ('active','escalated','closed')),
    started_at   timestamptz not null default now(),
    last_message_at timestamptz,
    unique (channel, external_id)
);

create table if not exists messages (
    id              uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role            text not null check (role in ('user','assistant','system','tool')),
    content         text,
    tool_name       text,
    tool_input      jsonb,
    tool_output     jsonb,
    tokens_input    int,
    tokens_output   int,
    latency_ms      int,
    created_at      timestamptz not null default now()
);
create index if not exists messages_conv_idx on messages(conversation_id, created_at);

-- -----------------------------------------------------------------------------
-- Audit log (acciones sensibles)
-- -----------------------------------------------------------------------------
create table if not exists audit_log (
    id           bigserial primary key,
    firm_id      uuid not null,
    actor_user_id uuid,
    action       text not null,
    entity       text not null,
    entity_id    text,
    diff         jsonb,
    created_at   timestamptz not null default now()
);
create index if not exists audit_firm_idx on audit_log(firm_id, created_at desc);

-- =============================================================================
-- Row Level Security
-- =============================================================================
-- Helper: firm_id del usuario autenticado (leído desde JWT via public.users)
create or replace function auth_firm_id() returns uuid
language sql stable security definer
as $$
    select firm_id from public.users where id = auth.uid()
$$;

create or replace function auth_role() returns text
language sql stable security definer
as $$
    select role from public.users where id = auth.uid()
$$;

create or replace function auth_client_id() returns uuid
language sql stable security definer
as $$
    select client_id from public.users where id = auth.uid()
$$;

-- Habilitar RLS
alter table firms                    enable row level security;
alter table users                    enable row level security;
alter table clients                  enable row level security;
alter table documents                enable row level security;
alter table invoices                 enable row level security;
alter table invoice_lines            enable row level security;
alter table bank_accounts            enable row level security;
alter table bank_transactions        enable row level security;
alter table reconciliation_matches   enable row level security;
alter table tax_obligations          enable row level security;
alter table conversations            enable row level security;
alter table messages                 enable row level security;
alter table audit_log                enable row level security;

-- Policies genéricas: firm_admin/accountant ven todo su firm; client solo sus datos
-- (service_role bypassa RLS por defecto en Supabase)

-- Firms: usuarios ven su propio despacho
create policy firms_read on firms for select
    using (id = auth_firm_id());

-- Users: cada quien ve usuarios del mismo firm; los clientes solo se ven a sí mismos
create policy users_read on users for select
    using (
        firm_id = auth_firm_id()
        and (auth_role() in ('firm_admin','accountant') or id = auth.uid())
    );

-- Clients: staff ve todos los del firm; client solo el propio
create policy clients_read on clients for select
    using (
        firm_id = auth_firm_id()
        and (auth_role() in ('firm_admin','accountant') or id = auth_client_id())
    );

-- Patrón repetido para tablas transaccionales
do $$
declare
    t text;
begin
    foreach t in array array[
        'documents','invoices','bank_accounts','bank_transactions',
        'reconciliation_matches','tax_obligations','conversations'
    ]
    loop
        execute format($f$
            create policy %I_read on %I for select
                using (
                    firm_id = auth_firm_id()
                    and (auth_role() in ('firm_admin','accountant') or client_id = auth_client_id())
                );
        $f$, t, t);
    end loop;
end$$;

-- invoice_lines: heredan por join
create policy invoice_lines_read on invoice_lines for select
    using (exists (
        select 1 from invoices i
        where i.id = invoice_lines.invoice_id
          and i.firm_id = auth_firm_id()
          and (auth_role() in ('firm_admin','accountant') or i.client_id = auth_client_id())
    ));

-- messages: por conversación
create policy messages_read on messages for select
    using (exists (
        select 1 from conversations c
        where c.id = messages.conversation_id
          and c.firm_id = auth_firm_id()
          and (auth_role() in ('firm_admin','accountant') or c.client_id = auth_client_id())
    ));

-- audit_log: solo firm_admin
create policy audit_admin_read on audit_log for select
    using (firm_id = auth_firm_id() and auth_role() = 'firm_admin');

-- =============================================================================
-- Fin de migración 0001_init
-- =============================================================================
