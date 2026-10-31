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

待處理：六張舊表沒有 RLS，anon/authenticated 有讀寫權限。

依使用者最新指示，六張舊表保持原樣，不改名、不搬移、不改權限；取消原訂備份、資料遷移與清理 SQL。
v2 四張表另外使用既有 `docs/supabase_schema_v2.sql` 的完整原始內容建立。
