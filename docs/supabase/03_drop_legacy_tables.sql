-- 刪除六張舊表：users、financial_profiles、life_events、car_loans、simulation_sessions、simulation_results
-- 在 Supabase SQL Editor 依序執行：步驟 1 檢查 → 步驟 2 匯出 CSV（在 Table Editor 操作）→ 步驟 3 刪除 → 步驟 4 確認。
-- 只動 public schema 的六張舊表；auth.users（登入用）與 v2 四張表（profiles、debts、plans、plan_events）不受影響。


-- ===== 步驟 1：檢查（只讀，不會改任何東西）=====
-- 三個查詢都應該回傳 0 列。只要有任何一列，先停下來，把結果截圖給 Claude。

-- 1a. 有沒有 trigger 掛在 auth.users 或舊表上（例如註冊時自動寫入 public.users）
SELECT c.relnamespace::regnamespace AS schema_name, c.relname AS table_name,
       t.tgname AS trigger_name, t.tgfoid::regproc AS function_name
FROM pg_trigger AS t
JOIN pg_class AS c ON c.oid = t.tgrelid
WHERE NOT t.tgisinternal
  AND (c.oid = 'auth.users'::regclass
       OR (c.relnamespace = 'public'::regnamespace
           AND c.relname IN ('users', 'financial_profiles', 'life_events', 'car_loans',
                             'simulation_sessions', 'simulation_results')));

-- 1b. public schema 的 function 有沒有用到舊表的名字
SELECT p.oid::regprocedure AS function_name
FROM pg_proc AS p
WHERE p.pronamespace = 'public'::regnamespace
  AND p.prosrc ~* '(financial_profiles|life_events|car_loans|simulation_sessions|simulation_results|public\.users)';

-- 1c. 舊表以外有沒有其他物件（view、外鍵）依賴舊表
SELECT DISTINCT dependent.relname AS dependent_object, referenced.relname AS legacy_table
FROM pg_depend AS d
JOIN pg_rewrite AS r ON r.oid = d.objid
JOIN pg_class AS dependent ON dependent.oid = r.ev_class
JOIN pg_class AS referenced ON referenced.oid = d.refobjid
WHERE referenced.relnamespace = 'public'::regnamespace
  AND referenced.relname IN ('users', 'financial_profiles', 'life_events', 'car_loans',
                             'simulation_sessions', 'simulation_results')
  AND dependent.oid <> referenced.oid
UNION
SELECT con.conrelid::regclass::text, con.confrelid::regclass::text
FROM pg_constraint AS con
WHERE con.contype = 'f'
  AND con.confrelid IN (SELECT oid FROM pg_class
                        WHERE relnamespace = 'public'::regnamespace
                          AND relname IN ('users', 'financial_profiles', 'life_events', 'car_loans',
                                          'simulation_sessions', 'simulation_results'))
  AND con.conrelid NOT IN (SELECT oid FROM pg_class
                           WHERE relnamespace = 'public'::regnamespace
                             AND relname IN ('users', 'financial_profiles', 'life_events', 'car_loans',
                                             'simulation_sessions', 'simulation_results'));


-- ===== 步驟 2：匯出 =====
-- 在 Table Editor 逐張打開六張舊表 → 右上角 Export → Export table as CSV。
-- 存到 repo 以外的資料夾（例如 D:\project\FinSim-Core-legacy-backup\），不要放進 repo。
-- 確認六個 CSV 都有下載、筆數合理（10/31 盤點：users 6、financial_profiles 55、life_events 8、
-- car_loans 0、simulation_sessions 64、simulation_results 60），再進行步驟 3。


-- ===== 步驟 3：刪除（無法復原）=====
-- 不加 CASCADE：如果有步驟 1 沒發現的物件依賴舊表，整句會失敗，什麼都不會被刪。
DROP TABLE public.simulation_results, public.simulation_sessions, public.life_events,
           public.car_loans, public.financial_profiles, public.users;


-- ===== 步驟 4：確認 =====
-- 應該只剩 debts、plan_events、plans、profiles 四張。
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
