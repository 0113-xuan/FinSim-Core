-- FutureWallet Supabase schema v2: login and saved profiles, plans and events.
-- Run once in the Supabase SQL Editor. Replaces the outdated supabase_schema.sql.
-- Every table is owner-only through RLS; the backend must call Supabase with the
-- signed-in user's JWT, never with the service_role key.

-- profiles: one row of current finances per user
create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  monthly_income numeric not null check (monthly_income >= 0),      -- 每月實領收入
  cash_balance numeric not null,                                     -- 可動用現金
  fixed_expense numeric not null default 0 check (fixed_expense >= 0),       -- 每月固定支出（不含貸款）
  variable_expense numeric not null default 0 check (variable_expense >= 0), -- 每月變動支出
  investment_value numeric not null default 0 check (investment_value >= 0), -- 投資目前市值
  monthly_investment numeric not null default 0 check (monthly_investment >= 0),
  raise_rate numeric,                     -- 空值 = 調薪跟著通膨
  emergency_target_months numeric not null default 3,
  updated_at timestamptz not null default now()
);

-- debts: existing loans
create table public.debts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  monthly_payment numeric not null check (monthly_payment >= 0),
  remaining_months int not null check (remaining_months >= 0),
  created_at timestamptz not null default now()
);

-- plans: scenarios a user compares, e.g. "buy a car in two years"
create table public.plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  kind text not null default 'general' check (kind in ('general', 'vehicle')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- plan_events: events inside a plan; periods use YYYY-MM
create table public.plan_events (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.plans(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null check (type in ('one_time', 'range', 'salary_change', 'vehicle_purchase')),
  name text not null,
  start_period text not null check (start_period ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  end_period text check (end_period ~ '^\d{4}-(0[1-9]|1[0-2])$'),
  amount numeric,           -- 一次性金額，支出為負
  monthly_amount numeric,   -- 每月增減，支出為負
  new_salary numeric,       -- 換工作後的實領月薪
  details jsonb not null default '{}'::jsonb,  -- 購車等事件的完整參數
  created_at timestamptz not null default now(),
  check (end_period is null or end_period >= start_period)
);

create index on public.debts (user_id);
create index on public.plans (user_id);
create index on public.plan_events (plan_id);

-- Row level security: each user reads and writes only their own rows
alter table public.profiles enable row level security;
alter table public.debts enable row level security;
alter table public.plans enable row level security;
alter table public.plan_events enable row level security;

create policy "own rows" on public.profiles for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own rows" on public.debts for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own rows" on public.plans for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
-- An event may only be added to a plan the same user owns
create policy "own rows" on public.plan_events for all to authenticated
  using ((select auth.uid()) = user_id)
  with check (
    (select auth.uid()) = user_id
    and exists (select 1 from public.plans p where p.id = plan_id and p.user_id = (select auth.uid()))
  );
