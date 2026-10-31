-- AI-Finance-Sim inventory, observed 2026-10-31 (Asia/Taipei).
-- Phase 1: SELECT statements only. No application row contents are returned.
-- Row counts are statement-time observations, not a locked backup snapshot.
-- Function bodies, view bodies, trigger arguments, keys and connection settings are not read.

-- 01_context
SELECT current_user AS inventory_role,
       r.rolsuper AS is_superuser,
       r.rolbypassrls AS bypasses_rls,
       (SELECT count(*) FROM auth.users) AS auth_user_count,
       to_regclass('storage.buckets') IS NOT NULL AS storage_buckets_exists
FROM pg_catalog.pg_roles AS r
WHERE r.rolname = current_user;

-- 02_tables
SELECT c.relname AS table_name,
       CASE c.relkind WHEN 'r' THEN 'table' WHEN 'p' THEN 'partitioned_table'
                      WHEN 'f' THEN 'foreign_table' END AS object_kind,
       c.relispartition AS is_partition,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced,
       pg_catalog.pg_get_userbyid(c.relowner) AS owner_role
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'f')
ORDER BY c.relname;

-- 03_columns
SELECT table_name, ordinal_position, column_name, data_type,
       udt_schema, udt_name, is_nullable, column_default,
       is_identity, identity_generation, is_generated, generation_expression
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

-- 04_constraints
SELECT c.relname AS table_name, con.conname AS constraint_name,
       con.contype AS constraint_type,
       pg_catalog.pg_get_constraintdef(con.oid, true) AS definition,
       con.convalidated AS validated,
       con.condeferrable AS deferrable,
       con.condeferred AS initially_deferred
FROM pg_catalog.pg_constraint AS con
JOIN pg_catalog.pg_class AS c ON c.oid = con.conrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND con.contype IN ('p', 'f', 'u', 'c')
ORDER BY c.relname, con.conname;

-- 05_policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- 06_views
SELECT c.relname AS view_name,
       CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized_view' END AS object_kind,
       pg_catalog.pg_get_userbyid(c.relowner) AS owner_role,
       c.reloptions AS options
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('v', 'm')
ORDER BY c.relname;

-- 07_functions
SELECT p.proname AS function_name,
       pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_arguments,
       pg_catalog.pg_get_function_result(p.oid) AS return_type,
       p.prokind AS function_kind, l.lanname AS language,
       p.prosecdef AS security_definer, p.provolatile AS volatility,
       pg_catalog.pg_get_userbyid(p.proowner) AS owner_role,
       e.extname AS extension_name
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
JOIN pg_catalog.pg_language AS l ON l.oid = p.prolang
LEFT JOIN pg_catalog.pg_depend AS d ON d.classid = 'pg_catalog.pg_proc'::regclass
                                  AND d.objid = p.oid AND d.deptype = 'e'
LEFT JOIN pg_catalog.pg_extension AS e ON e.oid = d.refobjid
WHERE n.nspname = 'public'
ORDER BY p.proname, identity_arguments;

-- 08_triggers
SELECT c.relname AS table_name, t.tgname AS trigger_name,
       t.tgenabled AS enabled_state,
       pn.nspname AS function_schema, p.proname AS function_name,
       pg_catalog.pg_get_function_identity_arguments(p.oid) AS function_arguments
FROM pg_catalog.pg_trigger AS t
JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_proc AS p ON p.oid = t.tgfoid
JOIN pg_catalog.pg_namespace AS pn ON pn.oid = p.pronamespace
WHERE n.nspname = 'public' AND NOT t.tgisinternal
ORDER BY c.relname, t.tgname;

-- 09_indexes
SELECT tablename, indexname, indexdef
FROM pg_catalog.pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 10_grants
SELECT table_name, grantee, privilege_type, is_grantable
FROM information_schema.table_privileges
WHERE table_schema = 'public'
ORDER BY table_name, grantee, privilege_type;

-- 11_row_counts
SELECT 'car_loans' AS table_name, count(*) AS row_count FROM public.car_loans
UNION ALL SELECT 'financial_profiles', count(*) FROM public.financial_profiles
UNION ALL SELECT 'life_events', count(*) FROM public.life_events
UNION ALL SELECT 'simulation_results', count(*) FROM public.simulation_results
UNION ALL SELECT 'simulation_sessions', count(*) FROM public.simulation_sessions
UNION ALL SELECT 'users', count(*) FROM public.users
ORDER BY table_name;

-- 12_storage_buckets
SELECT name AS bucket_name FROM storage.buckets ORDER BY name;

-- 13_column_types
SELECT c.relname AS table_name, a.attname AS column_name,
       pg_catalog.format_type(a.atttypid, a.atttypmod) AS full_type
FROM pg_catalog.pg_attribute AS a
JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'f', 'v', 'm')
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum;
