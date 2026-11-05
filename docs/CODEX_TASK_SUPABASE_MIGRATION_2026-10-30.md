# Codex 任務：整理既有 Supabase 並遷移到 v2

日期：2026-10-30。Codex 透過 Supabase MCP 直接操作資料庫。每個階段結束都要停下來，由使用者與 Claude 審查後才繼續。

## 背景

- 新的資料表設計在 `docs/supabase_schema_v2.sql`：`profiles`、`debts`、`plans`、`plan_events`，全部啟用 RLS，每人只能存取自己的資料。
- 使用者原本的 Supabase 專案已經有資料表和資料，內容未知。可能來自舊的 `docs/supabase_schema.sql`（已刪除，可用 `git show feat/supabase-schema-v2~1:docs/supabase_schema.sql` 查看），也可能有其他手動建立的表。
- 目標：在不遺失資料的前提下，讓 Supabase 符合 v2 設計；舊的東西先備份、改名，確認新版正常後才刪除。

## 連線方式

- 透過 Codex 的 Supabase 外掛操作，只操作專案 AI-Finance-Sim。連不上就停下來回報，不要改用其他方式連線。
- 外掛本身可以寫入，沒有唯讀模式，所以階段 1、2 和 3-1 要自己遵守唯讀：
  - 只能用讀取的工具，例如 `list_tables`、`list_extensions`、`list_migrations`，以及只含 `select` 的 `execute_sql`。
  - 不可以呼叫 `apply_migration`、`create_branch`、`deploy_edge_function`、`merge_branch`、`reset_branch`、`delete_branch`、`pause_project`、`restore_project` 等會改變專案的工具。
  - `execute_sql` 不可以包含 `insert`、`update`、`delete`、`create`、`alter`、`drop`、`truncate`、`grant`、`revoke`。
- 階段 3-2 等使用者在對話中說「開始遷移」後，才可以執行寫入，而且只能執行審查過的 SQL 檔。

## 安全規則（必須遵守）

- 不讀 `.env`。不要在對話、檔案、commit 或日誌中輸出任何 key、token、密碼或連線字串。
- 不查詢或輸出個人資料：`auth.users` 只能查數量，使用者資料表只能查筆數與欄位結構，不要 `select *` 列出內容。
- 不修改 `auth`、`storage` 等 Supabase 內建 schema。
- 寫入動作只能在階段 3 執行，而且只能執行 Claude 審查過、commit 在 repo 裡的 SQL 檔，不能臨時改寫或另外加指令。
- `drop`、`delete`、`truncate` 只能出現在 `05_cleanup_legacy.sql`，而且必須等使用者在對話中明確說「執行清理」才可以執行。
- 任何一步出錯就停下來回報錯誤訊息，不要自行嘗試其他修法。
- 不要 push。從 `fix/p5-core-cleanup` 建立新分支 `chore/supabase-migration`。只 `git add` 你建立或修改的檔案，commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。

## 階段 1：盤點（唯讀）

用 MCP 查詢並整理以下內容，同時把用到的查詢存成 `docs/supabase/01_inventory.sql`，方便之後重查：

1. `public` schema 裡每張表的名稱與資料筆數。
2. 每張表的欄位：名稱、型別、是否可為空值、預設值。
3. 主鍵、外鍵、唯一鍵與 check 約束。
4. 每張表是否啟用 RLS，以及現有的 policy。
5. `public` schema 裡的 view、function、trigger。
6. `auth.users` 的帳號數量。
7. `storage.buckets` 的名稱（如果存在）。

## 階段 2：分析報告

建立 `docs/supabase/INVENTORY_REPORT.md`，用一張表列出每個既有物件：

| 物件 | 筆數 | 和 v2 的關係 | 建議 | 理由 |
| --- | --- | --- | --- | --- |

- 「和 v2 的關係」：同名衝突、可以對應到 v2 的某張表、或無關。**特別檢查 `profiles` 是否已存在**，這是很常見的表名。
- 「建議」只能是：保留、遷移到 v2 後改名為 `legacy_*`、備份後待刪除。
- 有資料要搬時，逐欄寫出對應關係，以及無法確定的地方。例如舊的 `monthly_income` 是稅前還是實領無法從結構判斷，就標示「需使用者確認」，不要自行猜測。
- 如果發現 v2 設計需要調整，寫在報告裡說明原因，先不要改 `supabase_schema_v2.sql`。

階段 1、2 完成後 commit，回報報告重點，然後**停止**，等使用者與 Claude 確認。

## 階段 3：遷移

### 3-1 撰寫 SQL（先不要執行）

建立以下檔案，每個檔案都要能重複執行而不出錯（使用 `if not exists`、`if exists` 等）：

- `02_backup.sql`：建立 `backup_20261030` schema，把每張有資料的既有表完整複製一份（`create table ... as select * from ...`）。
- `03_migrate_to_v2.sql`：包在一個交易（`begin; ... commit;`）裡。同名衝突的舊表改名為 `legacy_*`，建立 v2 的資料表、索引、RLS 與 policy，最後依報告確認過的對應關係搬移資料。這個檔案不可以有 `drop table` 或 `delete`。
- `04_verify.sql`：唯讀檢查，包括備份筆數和原表一致、v2 四張表都存在、四張表都啟用 RLS、每張表都有 policy、搬移後的筆數符合預期。
- `05_cleanup_legacy.sql`：刪除 `legacy_*` 表與 `backup_20261030` schema。開頭註明「確認新版運作正常後才執行」。

commit 後**停止**，等 Claude 審查 SQL。

### 3-2 執行（審查通過、使用者說「開始遷移」之後）

1. 執行 `02_backup.sql`，回報每張備份表的筆數。
2. 執行 `03_migrate_to_v2.sql`。
3. 執行 `04_verify.sql`，回報每一項檢查的結果。
4. 停止。`05_cleanup_legacy.sql` 等使用者明確說「執行清理」才執行。

## 每個階段的回報

1. commit hash。
2. 新增或修改的檔案。
3. 實際執行過的 SQL 檔與結果（3-2 階段）。
4. 需要使用者確認或回答的問題。
