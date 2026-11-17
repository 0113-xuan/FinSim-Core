-- Run once in the Supabase SQL editor of an existing project (new projects get this from supabase_schema_v2.sql).
alter table public.plan_events drop constraint plan_events_type_check;
alter table public.plan_events add constraint plan_events_type_check
  check (type in ('one_time', 'range', 'salary_change', 'vehicle_purchase', 'home_purchase', 'marriage', 'child'));
