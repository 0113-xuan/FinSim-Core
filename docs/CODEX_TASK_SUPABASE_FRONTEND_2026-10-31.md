# Codex 任務：前端直接串接 Supabase（登入、財務資料、計畫與事件）

日期：2026-10-31。完成後由 Claude 審查。

## 背景

- Supabase 專案 AI-Finance-Sim 已經建立 v2 的四張表：`profiles`、`debts`、`plans`、`plan_events`。結構見 `docs/supabase_schema_v2.sql`，都有 RLS，每個人只能讀寫自己的資料。
- 架構決定：**前端用 supabase-js 直接登入與讀寫資料，後端只負責計算**。後端不連 Supabase。
- 這次新增一個獨立頁面 `static/planner.html`。舊的 `index.html`、`vehicle.html`、`car-needs.html` 不要修改。
- 畫面先求能用、樣式簡單，沿用 `static/style.css`。完整的視覺改版是之後的任務。

## 工作規則

- 從 `chore/supabase-migration` 建立新分支 `feat/supabase-frontend`。**不要 push**。
- 不讀 `.env`，不在任何地方輸出 key。前端只能用 anon key，絕對不能出現 service_role key。
- 只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- 這次不用 Supabase MCP，也不要修改資料庫。

## 任務 A：後端提供前端設定

- 新增 `GET /config/public`，回傳 `{"supabase_url": ..., "supabase_anon_key": ..., "configured": true/false}`，值來自現有的 `SUPABASE_URL`、`SUPABASE_ANON_KEY` 環境變數。任一個沒設定時 `configured` 為 `false`，兩個值回傳空字串。
- 只能回傳這三個欄位，不可以回傳其他設定。
- 測試：有設定與沒設定兩種情況，以及回應只包含這三個欄位。

## 任務 B：移除舊的暫存登入

- 刪除 `main.py` 的 `/auth/register`、`/auth/login`、`GET/POST /financial-profile`，以及 `USERS`、`PROFILES` 兩個字典。
- 用 `git grep` 確認 `app/security/auth.py`、`JWT_SECRET`、`jwt_expire_minutes` 是否還有其他地方使用。沒有的話一併刪除，包括 `.env.example` 與 `app/config.py` 中的相關設定。`requirements.txt` 裡只被它們使用的套件也一起移除。
- 刪除或改寫對應的測試（例如 `tests/test_api.py` 中的註冊與受保護端點測試）。
- `CONFIRMED_DEMO_PROFILES` 與 AI 草稿流程屬於 `index.html`，保持不動。

## 任務 C：資料對應模組 `static/planner-model.js`

純函式，不碰 DOM 和網路，用和 `static/car-needs-state.js` 相同的方式匯出（Node 用 `module.exports`，瀏覽器掛在 `globalThis.PlannerModel`）。

`buildSimulationRequest({ profile, debts, events, startPeriod, months })` 回傳給 `/simulate`、`/monte-carlo` 的請求內容：

**月份換算**：`startPeriod` 是模擬起始月（YYYY-MM），即第 1 個月。任一 YYYY-MM 換算成 `月份 = 與 startPeriod 相差的月數 + 1`。

**profile**

| `profiles` 欄位 | 請求欄位 |
| --- | --- |
| `monthly_income` | `profile.salary` |
| `cash_balance` | `profile.balance` |
| `fixed_expense` | `profile.fixed_expense` |
| `variable_expense` | `profile.variable_expense` |
| `raise_rate` | `profile.raise_rate`（空值就不送，讓後端用通膨率） |
| `emergency_target_months` | `profile.target_emergency_months` |

- **不要送 `inflation_rate`**，讓後端使用預設值。
- `monthly_investment` 大於 0 時，轉成一筆每月支出事件：`{type: "range", name: "每月投資", start_month: 1, end_month: months, monthly_amount: -monthly_investment}`。
- `investment_value` 不送進計算，因為投資帳戶是下一個任務。

**debts**：每筆 `remaining_months > 0` 的貸款轉成 `{type: "range", name, start_month: 1, end_month: min(remaining_months, months), monthly_amount: -monthly_payment}`。`remaining_months = 0` 的略過。

**plan_events**

| type | 轉換結果 |
| --- | --- |
| `one_time` | `{type: "one_time", name, month: 換算(start_period), amount}` |
| `range` | `{type: "range", name, start_month: 換算(start_period), end_month: 換算(end_period) 或 months, monthly_amount}`。**不要同時送 `amount`**，引擎會把 range 的 `amount` 也算成每月金額，造成重複計算 |
| `salary_change` | `{type: "salary_change", name, start_month: 換算(start_period), new_salary}` |
| `vehicle_purchase` | 這次不處理，略過 |

- 開始月份早於第 1 個月、或晚於 `months` 的事件要略過；結束月份超過 `months` 的截到 `months`。
- 函式同時回傳 `warnings` 陣列，列出每筆被略過或截斷的事件與原因，讓畫面顯示。
- 金額正負號照資料庫原樣：支出為負、收入為正，不要自行轉換。

另外提供 `periodToMonth(startPeriod, period)`、`monthToPeriod(startPeriod, month)` 兩個工具函式。

測試 `tests/test_planner_model.js` 至少涵蓋：

- 每一列對應表都正確，`raise_rate` 為空值時請求中沒有這個欄位，請求中沒有 `inflation_rate`。
- range 事件只有 `monthly_amount`，沒有 `amount`。
- 跨年的月份換算，例如 startPeriod 2026-11 時，2027-02 是第 4 個月。
- 早於起始月、晚於期間、結束月被截斷這三種情況都會產生對應的 warning。
- 貸款剩 0 期時略過；`monthly_investment` 為 0 時不產生事件。
- `vehicle_purchase` 被略過並產生 warning。

## 任務 D：頁面 `static/planner.html` 與 `static/planner.js`

- 用 CDN 載入 supabase-js v2，**版本要寫死成確切版號**（例如 `@supabase/supabase-js@2.45.4`，請先確認該版本存在），不能寫 `@2` 或 `latest`。
- 開啟頁面時呼叫 `/config/public`。`configured` 為 `false` 時，顯示「尚未設定 Supabase」並停用登入。

畫面分成五個區塊，全部用繁體中文：

1. **登入**：email 與密碼的註冊、登入、登出。註冊後如果沒有拿到 session（Supabase 需要確認信），顯示「請到信箱點確認連結後再登入」。用 `onAuthStateChange` 切換登入前後的畫面。
2. **我的財務資料**：`profiles` 的所有欄位，用 upsert 儲存。第一次登入、還沒有資料時，顯示空白表單並提示要先填寫。`raise_rate` 留空代表「跟著通膨」，要在欄位旁寫明。
3. **現有貸款**：`debts` 的新增、列表、刪除。
4. **計畫與事件**：`plans` 的新增、列表、刪除，選擇一個計畫後顯示它的 `plan_events`，可以新增與刪除。新增事件的表單依 type 顯示對應欄位：one_time 顯示金額，range 顯示每月金額與起訖月，salary_change 顯示新月薪。type 只提供這三種。
5. **模擬結果**：選擇期間（60、120、240 個月），按「執行模擬」後用 `buildSimulationRequest` 組出請求，呼叫 `/simulate` 和 `/monte-carlo`（`simulations: 300`、`seed: 42`）。
   - 顯示：最低現金與發生月份、第一次現金小於 0 的月份（沒有就顯示「未出現」）、最低緊急預備金月數、期末現金、現金不足機率與它的定義文字、期末現金的 p5、p50、p95。
   - 月份一律用 YYYY-MM 顯示。
   - 欄位名稱以後端實際回傳為準，先讀 `app/core/simulation.py` 與 `app/core/monte_carlo.py`，不要猜。
   - 顯示 `warnings`，以及一行說明：「投資市值尚未納入計算；每月投資金額視為現金支出」。

其他要求：

- 所有寫入都要帶 `user_id: session.user.id`。
- 每個 Supabase 操作都要處理錯誤，在畫面上顯示錯誤訊息，不要只寫在 console。
- 起始月用台北時間的當月。

## 任務 E：文件

- README 的 Supabase 段落改成：`planner.html` 用 Supabase 登入與存資料；需要在 `.env` 設定 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`；並移除關於記憶體登入、JWT 的說明。
- README「Existing Platform Features」裡的 `high-risk month distribution` 已經不存在，順便刪掉。

## 不在本任務範圍

投資帳戶計算、歷史資料 Monte Carlo、購車事件存進 `plan_events`、視覺改版、LLM 解釋、RAG、舊資料表處理。發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. 新增、刪除的 API 與檔案。
3. 測試指令與結果（通過數量、失敗數量）。
4. 使用者要自己在 Supabase 後台或 `.env` 做的設定。
5. 沒有完成或刻意保留的部分，以及原因。
