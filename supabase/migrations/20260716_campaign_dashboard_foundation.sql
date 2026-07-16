create extension if not exists pgcrypto;

create table if not exists public.clients (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ad_accounts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  snapchat_ad_account_id text not null unique,
  account_name text not null,
  currency text,
  timezone text,
  attribution_window text,
  default_delivery_type text not null default 'unknown' check (default_delivery_type in ('app', 'web', 'mixed', 'unknown')),
  stats_field_map jsonb not null default '{"amount_spent":"spend","app_installs":"app_installs","sign_ups_total":"sign_ups","purchases_total":"purchases"}'::jsonb,
  is_active boolean not null default true,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  ad_account_id uuid not null references public.ad_accounts(id) on delete cascade,
  snapchat_campaign_id text not null,
  name text not null,
  status text,
  objective text,
  delivery_type text not null default 'unknown' check (delivery_type in ('app', 'web', 'mixed', 'unknown')),
  optimization_goal text,
  raw jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ad_account_id, snapchat_campaign_id)
);

create table if not exists public.campaign_stats_daily (
  id bigserial primary key,
  ad_account_id uuid not null references public.ad_accounts(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  snapchat_campaign_id text not null,
  stat_date date not null,
  attribution_window text,
  currency text,
  amount_spent numeric(18,6) not null default 0,
  app_installs numeric(18,4) not null default 0,
  sign_ups_total numeric(18,4) not null default 0,
  purchases_total numeric(18,4) not null default 0,
  metrics jsonb not null default '{}'::jsonb,
  finalized_data_end_time timestamptz,
  synced_at timestamptz not null default now(),
  unique (ad_account_id, snapchat_campaign_id, stat_date, attribution_window)
);

create table if not exists public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null default 'campaign_daily',
  status text not null check (status in ('running', 'success', 'failed')),
  client_slug text,
  ad_account_id uuid references public.ad_accounts(id) on delete set null,
  date_start date,
  date_end date,
  refresh_days integer,
  rows_upserted integer not null default 0,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists idx_ad_accounts_client on public.ad_accounts(client_id);
create index if not exists idx_campaigns_account on public.campaigns(ad_account_id);
create index if not exists idx_campaign_stats_lookup on public.campaign_stats_daily(ad_account_id, stat_date);
create index if not exists idx_campaign_stats_campaign on public.campaign_stats_daily(snapchat_campaign_id, stat_date);
create index if not exists idx_sync_runs_started on public.sync_runs(started_at desc);

create or replace view public.campaign_dashboard as
select
  csd.id,
  c.slug as client_slug,
  c.name as client_name,
  aa.account_name,
  aa.snapchat_ad_account_id,
  csd.stat_date,
  coalesce(camp.name, csd.snapchat_campaign_id) as name,
  camp.status,
  camp.objective,
  camp.delivery_type,
  camp.optimization_goal,
  csd.attribution_window,
  csd.currency,
  csd.amount_spent,
  csd.app_installs,
  case when csd.app_installs > 0 then csd.amount_spent / csd.app_installs else null end as cost_per_install,
  csd.sign_ups_total,
  case when csd.sign_ups_total > 0 then csd.amount_spent / csd.sign_ups_total else null end as cost_per_sign_up,
  csd.purchases_total,
  case when csd.purchases_total > 0 then csd.amount_spent / csd.purchases_total else null end as cost_per_purchase,
  csd.finalized_data_end_time,
  csd.synced_at
from public.campaign_stats_daily csd
join public.ad_accounts aa on aa.id = csd.ad_account_id
join public.clients c on c.id = aa.client_id
left join public.campaigns camp on camp.id = csd.campaign_id;

alter table public.clients enable row level security;
alter table public.ad_accounts enable row level security;
alter table public.campaigns enable row level security;
alter table public.campaign_stats_daily enable row level security;
alter table public.sync_runs enable row level security;
