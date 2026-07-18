-- FinSim-Core graduation-project schema reference.
-- Review in Supabase SQL editor, enable RLS, then apply to your project.
-- This file documents required tables; the app can run locally without Supabase.

create table if not exists public.financial_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  current_savings numeric not null,
  monthly_income numeric not null,
  fixed_expense numeric default 0,
  variable_expense numeric default 0,
  target_emergency_months numeric default 3,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.expense_categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  category text not null,
  baseline numeric not null,
  monthly_volatility numeric default 0,
  annual_inflation_rate numeric default 0.02,
  income_elasticity numeric default 0,
  seasonal_factors numeric[] not null default array[1,1,1,1,1,1,1,1,1,1,1,1],
  minimum numeric,
  maximum numeric,
  enabled boolean default true,
  created_at timestamptz default now()
);

create table if not exists public.life_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  scenario_id uuid,
  name text not null,
  description text,
  start_month integer not null,
  end_month integer,
  one_time_amount numeric default 0,
  monthly_amount numeric default 0,
  income_multiplier numeric default 1,
  fixed_expense_multiplier numeric default 1,
  variable_expense_multiplier numeric default 1,
  target_expense_category text,
  source text default 'manual',
  created_at timestamptz default now()
);

create table if not exists public.loans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  principal numeric not null,
  apr numeric not null,
  months integer not null,
  start_month integer not null,
  note text,
  created_at timestamptz default now()
);

create table if not exists public.scenarios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  name text not null,
  profile jsonb not null,
  events jsonb default '[]'::jsonb,
  loans jsonb default '[]'::jsonb,
  random_shocks jsonb default '[]'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.simulation_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  scenario_id uuid,
  request jsonb not null,
  summary jsonb not null,
  created_at timestamptz default now()
);

create table if not exists public.ai_scenario_drafts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  source_text text not null,
  parsed_payload jsonb not null,
  accepted boolean default false,
  created_at timestamptz default now()
);

alter table public.financial_profiles enable row level security;
alter table public.expense_categories enable row level security;
alter table public.life_events enable row level security;
alter table public.loans enable row level security;
alter table public.scenarios enable row level security;
alter table public.simulation_runs enable row level security;
alter table public.ai_scenario_drafts enable row level security;

-- Example ownership policy. Repeat for each table, replacing table name.
-- create policy "Users can manage own financial_profiles"
-- on public.financial_profiles
-- for all
-- to authenticated
-- using ((select auth.uid()) = user_id)
-- with check ((select auth.uid()) = user_id);
