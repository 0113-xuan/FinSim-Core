-- 開啟 RLS 但不建立 policy，anon 和 authenticated 就無法讀寫這些表，資料本身保持不變。
alter table public.users enable row level security;
alter table public.financial_profiles enable row level security;
alter table public.life_events enable row level security;
alter table public.car_loans enable row level security;
alter table public.simulation_sessions enable row level security;
alter table public.simulation_results enable row level security;
