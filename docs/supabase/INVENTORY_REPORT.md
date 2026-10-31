# Supabase 既有資料簡短盤點

專案：AI-Finance-Sim。盤點日期：2026-10-31（Asia/Taipei）。
結構與筆數查詢記錄於 `01_inventory.sql`；未讀取使用者資料列內容。

| public 既有表 | 筆數 |
| --- | ---: |
| car_loans | 0 |
| financial_profiles | 55 |
| life_events | 8 |
| simulation_results | 60 |
| simulation_sessions | 64 |
| users | 6 |
| 合計 | 193 |

已處理（2026-10-31）：已執行 `02_lock_legacy_tables.sql`，六張舊表全部啟用 RLS，未建立任何 policy，封鎖 anon/authenticated 的資料列讀寫；六張表的筆數與盤點時一致。

六張舊表不改名、不搬移、不刪除資料，既有表層級授權未調整；原訂備份、資料遷移與清理 SQL 維持取消。
v2 四張表另外使用既有 `docs/supabase_schema_v2.sql` 的完整原始內容建立。
本次驗證 v2 四張表皆維持 RLS 啟用、各一個 policy，完整 policy 定義與執行前相同。
