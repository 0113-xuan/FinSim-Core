# Codex 任務：把購車決策接進 planner

日期：2026-11-01。完成後由 Claude 審查。

## 背景

- 專題主軸改為**多種人生事件**。購車是第一個「有預設值、不用手動拆帳」的事件，之後的買房、結婚、生小孩等事件會沿用這次的做法。
- 現在 planner 選了「購車計畫」只是一個標籤，`vehicle_purchase` 事件在模擬時會被跳過。使用者只能手動把頭期款、車貸、養車費拆成好幾筆事件，貸款月付也要自己算。
- 原本的購車決策（`vehicle.html`、`/decisions/vehicle`）已經能算車貸、持有成本、壓力測試和可負擔車價。這次**沿用後端既有的計算**，不要在前端重寫車貸或成本公式。

## 工作規則

- 從 `feat/historical-monte-carlo` 建立新分支 `feat/planner-vehicle-event`。**不要 push**。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- **購車決策的計算結果不可以改變**（`/decisions/vehicle*`、`vehicle.html`、`car-needs.html`）。現有的 vehicle 測試必須不修改就能通過。
- 不要修改資料庫結構。`plan_events` 已經支援 `type = 'vehicle_purchase'`，完整參數存在 `details`（jsonb）。

## 任務 A：後端把購車事件換算成計算用的事件

新增 `POST /planner/vehicle-events`。

**請求**

```json
{
  "start_period": "2026-11",
  "months": 240,
  "inflation_rate": null,
  "vehicles": [
    {"name": "買車", "purchase_period": "2027-03", "details": { ... }}
  ]
}
```

`details` 的欄位（數字用一般數值，不是 `SourcedDecimal`）：

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `vehicle_catalog_id` | 否 | 車款清單的 id，自訂車款時不送 |
| `purchase_price` | 是 | 車價，大於 0 |
| `payment_method` | 是 | `cash` 或 `financed` |
| `down_payment` | 貸款時必填 | 可以是 0 |
| `loan_term_months` | 貸款時必填 | 正整數 |
| `annual_interest_rate` | 貸款時必填 | 小數，例如 0.025 |
| `annual_insurance`、`annual_tax`、`annual_maintenance_budget`、`monthly_fuel_or_energy`、`monthly_parking` | 否 | 沒填就用 `app/decision_assumptions.py` 的 `ASSUMPTIONS` 預設值 |

**做法**

- 把每台車組成 `ScenarioRequest`（`horizon_months` = `months`，`target_period` = `purchase_period`），呼叫既有的 `build_scenario`，取得 events 和 loans。**不要另外寫車貸公式**。
- 持有成本要照 `run_timeline` 的方式，每 12 個月調整一次通膨。請把 `run_timeline` 裡拆年度、乘通膨的那段抽成共用函式，兩邊都使用，並確保購車決策的結果不變。
- 通膨率：請求有提供 `inflation_rate` 就用它，沒有就用 `load_market_history().annual_inflation_rate`。
- 購買月份必須落在第 1 到 `months` 個月，否則回 422，訊息用繁體中文。
- 欄位錯誤（例如現金購買卻填了貸款條件、頭期款大於車價）回 422，訊息用繁體中文。

**回應**

```json
{
  "events": [...],
  "loans": [...],
  "vehicles": [
    {"name": "買車", "purchase_month": 5, "one_time_cash": 300000,
     "monthly_loan_payment": 9500.12, "total_loan_interest": 70007.2,
     "first_year_monthly_ownership_cost": 6833.33,
     "defaults_used": ["annual_insurance", "monthly_parking"]}
  ],
  "inflation_rate_used": 0.0134,
  "note": "購車持有成本以固定通膨率每年調整；Monte Carlo 的抽樣通膨不套用在購車成本上。"
}
```

`events` 和 `loans` 要能直接放進 `/simulate`、`/monte-carlo` 的請求。

## 任務 B：`static/planner-model.js`

- `buildSimulationRequest` 不再跳過 `vehicle_purchase`。改為回傳 `{request, warnings, vehicles}`，其中 `vehicles` 是 `[{name, purchase_period, details}]`。
- 購買月份早於第 1 個月或晚於 `months` 的購車事件，和其他事件一樣略過並產生 warning。
- 刪除「本次尚不支援購車事件」的 warning。
- 同步更新 `tests/test_planner_model.js`。

## 任務 C：planner 頁

**新增購車事件**

- 事件類型加一個「購車」。選了之後顯示以下欄位：
  - **車款**：下拉選單，資料來自 `GET /decisions/vehicle/catalog`，最後一個選項是「自訂車款」。選了清單中的車款就自動填入車價，使用者仍可修改。
  - **購買月份**：沿用現有的開始月份欄位。
  - **車價**。
  - **付款方式**：現金或貸款。選貸款才顯示頭期款、貸款期數（月）、年利率。**年利率在畫面上用 %**，例如輸入 2.5，存成 0.025。
  - **持有成本（選填）**：保險（年）、稅費（年）、保養（年）、油電（月）、停車（月）。輸入框的 placeholder 寫「留空使用預設 20,000／年」這類文字，數字從 `GET /decisions/vehicle/assumptions` 讀，不要寫死。
- 存進 `plan_events`：`type: 'vehicle_purchase'`，`details` 只放使用者實際填的欄位（留空的不放），`amount`、`monthly_amount`、`new_salary` 為 null。
- 事件列表顯示，例如：`買車｜2027-03｜車價 NT$849,000，貸款 60 期`。刪除「購車事件（尚未納入計算）」的文字。

**執行模擬**

- `vehicles` 不是空的時候，先呼叫 `/planner/vehicle-events`，把回傳的 `events`、`loans` 加進請求，再呼叫 `/simulate` 和 `/monte-carlo`。
- 結果區塊新增「購車」小節，每台車顯示：購車當月一次支出、每月車貸、總利息、第一年每月持有成本，以及哪些成本用了預設值。下面再顯示回應中的 `note`。

## 任務 D：購車分析（沿用原本的購車決策）

- 事件列表中每一筆購車事件旁邊加一個「購車分析」按鈕，呼叫既有的 `POST /decisions/vehicle`。請求格式參考 `static/vehicle.js` 的 `buildRequest`，用 planner 的資料組出來：
  - **profile**：`salary` 用 `monthly_income`，`fixed_expense`、`variable_expense` 照原樣，`balance` 用 `cash_balance`。`required_monthly_debt` 設為 0，`existing_debts` 用 `debts`（`name`、`monthly_payment`、`remaining_months`）。`raise_rate` 留空就不送。
  - **scenario**：`horizon_months: 60`，`target_period` 用購買月份，`payload` 用這筆事件的 `details`。數字欄位包成 `{value, source: 'user_provided'}`，留空的持有成本不送，讓後端套用預設值。
  - `start_period` 用台北時間的當月。
- 原本的購車決策規定購買月份必須在第 1 到 58 個月。超出範圍時，按鈕停用，並在旁邊說明原因。
- 分析結果顯示在該筆事件下方：
  - 是否通過所有財務限制。
  - 每月車貸、總利息、購車當月一次支出。
  - 最低現金與發生月份。
  - **最高可負擔車價**：`affordability.maximum_affordable_vehicle_price`。沒有數值時依 `status` 顯示原因。
  - 四項壓力測試是否通過，使用中文名稱。
- 下方加一行說明：「這個分析只看這台車和現有貸款，不包含計畫中的其他事件與投資。」並附上連到 `vehicle.html` 的「完整購車分析」連結。

## 必要的測試

- **計算一致**：同一份財務資料、同一台車、通膨率和調薪率都明確設為 0.02、沒有投資時，用 `/planner/vehicle-events` 換算後跑 `/simulate` 60 個月，每月現金要和 `/decisions/vehicle` 的 `timeline.scenario` 完全相同。
- **現金購車**與**貸款購車**都能正確換算。貸款月付要等於 `/decisions/vehicle` 回傳的 `monthly_loan_payment`。
- **預設值**：持有成本留空時，用的是 `ASSUMPTIONS` 的數字，而且會列在 `defaults_used`。
- **錯誤處理**：購買月份超出範圍、貸款缺欄位、頭期款大於車價，都回 422 和中文訊息。
- **planner-model**：購車事件會放進 `vehicles`，超出範圍時會略過並產生 warning。
- 現有的 vehicle 測試不修改，全部通過。
- 用瀏覽器實際操作一次：新增購車事件、執行模擬、按購車分析。Supabase 可以用模擬資料，但 `/planner/vehicle-events`、`/simulate`、`/monte-carlo`、`/decisions/vehicle` 都要打真的後端。

## 不在本任務範圍

其他人生事件範本（買房、結婚、生小孩等）、修改已存在的事件、A/B 車款比較、敏感度分析、`car-needs.html` 的 AI 需求推薦、前端視覺改版、`index.html` 舊頁面。發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. 新增、修改的 API 與檔案。
3. 「計算一致」測試用的輸入，以及兩邊的期末現金。
4. 測試指令與結果（通過數量、失敗數量）。
5. 沒有完成或刻意保留的部分，以及原因。
