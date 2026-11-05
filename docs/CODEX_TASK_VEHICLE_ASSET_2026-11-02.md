# 任務：車輛資產、折舊與負債納入淨資產

日期：2026-11-02。功能凍結日 11/15。完成後由 Claude 審查。

## 背景

- 淨資產目前等於「現金＋投資」。計畫裡買車時，頭期款或全額車價從現金扣掉，但車子本身沒有算成資產，所以購車當月淨資產會少掉整筆車價。
- 車貸只有每月還款，沒有記錄剩餘本金；計畫裡的既有貸款被送成「期間每月收支」事件，模擬引擎不知道它是負債。
- 儀表板的「淨值」已經扣掉既有貸款（每月還款 × 剩餘期數），但走勢圖的期初淨資產是現金＋投資，兩邊對不起來。例如測試帳號儀表板淨值 1,280,000，圖表期初卻是 1,400,000。
- 這次依 2026-10-12 教授會議「後續建議順序」第二階段：分開現金流與經濟成本，折舊先用可以調整的假設。

完成後的定義：

```text
淨資產 = 現金 + 投資市值 + 車輛估值 − 車貸剩餘本金 − 既有貸款剩餘應還
```

## 工作規則

- 從 `feat/planner-pages`（目前 HEAD `f0e7820`）建立新分支 `feat/vehicle-asset`。**不要 push**。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動，也不要 commit。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。目前基準：pytest 615 個通過、node 185 個通過。commit 結尾加上執行者自己的 `Co-Authored-By`。
- **購車流程的計算結果不可以改變**（`/decisions/vehicle*`、`vehicle.html`、`car-needs.html`）。現有的 vehicle 測試必須不修改就能通過；`vehicle_decision.run_timeline` 目前會移除 `investment_value`、`net_worth`，新增的每月欄位也要一併移除。
- 不可以手打任何歷史數值。折舊率是規劃假設，不是資料，必須標示為假設。

## 任務 A：折舊假設

- 在 `app/decision_assumptions.py` 新增 `annual_depreciation_rate`，預設 `0.15`，`unit="annual_rate"`，說明寫「車輛每年價值減少比例，規劃假設，非成交資料」。
- `/decisions/vehicle/assumptions` 會因此多一筆。這不算購車結果改變；如果現有 vehicle 測試因為假設清單筆數而失敗，停下來回報，不要改測試。
- 計畫的購車事件 `details` 新增選填 `annual_depreciation_rate`（0 到 1）。前端輸入為百分比，留空使用預設值，並在購車摘要的「使用預設值」中列出「折舊率」。

## 任務 B：計算引擎

`SimulationRequest`（`/simulate`、`/monte-carlo` 共用）新增：

| 欄位 | 預設 | 說明 |
| --- | --- | --- |
| `assets` | `[]` | 會折舊的資產，每筆 `name`、`start_month`、`value`（> 0）、`annual_depreciation_rate`（0 到 1） |

`ProfileInput` 新增：

| 欄位 | 預設 | 說明 |
| --- | --- | --- |
| `existing_debts` | `None` | 既有貸款，每筆 `name`、`monthly_payment`（≥ 0）、`remaining_months`（≥ 0 整數），與 `DecisionProfile` 相同結構 |

`simulate_finance` 每月計算：

1. **車輛估值**：從 `start_month` 當月起，`value × (1 − annual_depreciation_rate) ^ (已持有月數 / 12)`；購買當月已持有月數為 0。`start_month` 之前為 0。
2. **車貸剩餘本金**：每筆 `loans` 依本金、年利率、期數做等額本息攤還，當月還款後的剩餘本金。開始月份之前為 0，最後一期還完後為 0。
3. **既有貸款剩餘應還**：每筆 `monthly_payment × max(0, remaining_months − 已過月數)`，與儀表板相同的不折現定義。`simulate_finance` 已經會用 `existing_debts` 計算每月還款，不要重複扣款。

每月資料列新增 `asset_value`、`loan_balance`、`existing_debt_balance`；`net_worth` 改成上面的完整定義。摘要新增 `final_asset_value`、`final_loan_balance`、`final_existing_debt_balance`。

其他要求：

- 現金的計算方式**完全不變**；沒有 `assets`、`loans`、`existing_debts` 時，所有輸出必須和現在一樣。
- `/compare`、`/optimize`、舊的 scenario 流程如果帶 `loans`，淨資產也會扣掉剩餘本金。這是正確的新定義，在回報中列出受影響的端點即可。
- 數值四捨五入只在輸出時做；`round_output=False` 時保留未四捨五入的值。

## 任務 C：計畫購車轉換

- `/planner/vehicle-events` 的回應新增 `assets`：每台車一筆，`start_month` 為購買月份，`value` 為車價，折舊率為使用者填的值或預設值。
- 每台車的摘要 `vehicles[]` 新增：
  - `depreciation_in_horizon`：購買到模擬結束的價值減少
  - `ending_vehicle_value`：模擬結束時的車輛估值
  - `interest_in_horizon`：模擬期間內實際支付的車貸利息
  - `ownership_cost_in_horizon`：模擬期間內的持有成本（已含通膨調整的金額加總）
  - `economic_cost_in_horizon`：前三項加總
- `NOTE` 補一句「車輛估值依固定折舊率計算，不是成交價，Monte Carlo 不抽樣。」

## 任務 D：Monte Carlo

- `assets` 與 `existing_debts` 原樣傳入每次試驗，折舊不抽樣。
- 期末淨資產分位數、以今日購買力計算的淨資產自動包含車輛與負債，算法不變。
- 有 `assets` 時，`sampling_note` 加上「車輛估值依固定折舊率計算，不抽樣。」
- 現金指標（最低現金、第一次現金小於 0、現金不足機率）定義不變。

## 任務 E：前端

- `static/planner-model.js`：
  - 既有貸款改送 `profile.existing_debts`，不再轉成 range 事件。剩餘期數 0 的貸款照舊略過並警告；超過模擬期間不再需要「截斷」警告，因為剩餘應還會反映在期末負債。
  - `vehicleDetails` 支援 `annual_depreciation_rate`。
- `static/shell.js` 的 `prepareSimulation`：把 `/planner/vehicle-events` 回傳的 `assets` 放進 request。
- `static/shell-model.js` 的 `chartData`：期初淨資產改成 `financialSummary(profile, debts).netWorth`，和儀表板一致。需要的話把 `debts` 傳進去。
- `static/plan.html`、`static/plan-page.js`：
  - 購車事件表單新增「折舊率（%／年，選填）」。
  - 購車摘要每台車顯示：期末車輛估值、期間內折舊、期間內車貸利息、期間內持有成本、經濟成本。現金負擔（一次支出、每月車貸、持有成本）維持原樣，**兩者分開顯示**，並加一句「經濟成本是價值減少與費用，不是另一筆現金支出」。
  - 頁面上淨資產的說明改成完整定義。
- `static/dashboard.html`：計畫卡片說明裡的淨資產定義同步更新。

## 必要的測試

- **折舊手算**：車價 800,000、年折舊 15%，購買當月（已持有 0 個月）估值 800,000；已持有 12 個月時 800,000 × 0.85 = 680,000；已持有 24 個月時 800,000 × 0.85² = 578,000。算式寫在測試註解中。
- **現金購車**：購車當月淨資產的變化只等於當月持有成本，加上車價以外的一次性費用（如果有），不會少掉整筆車價。
- **貸款購車**：本金 600,000、年利率 2.5%、60 期，第 1、2 期與最後一期的剩餘本金和手算一致，最後一期為 0；購車當月淨資產的變化只等於當月持有成本，加上當月車貸還款中的利息部分（第一期若不在購車當月則為 0）。
- **既有貸款**：每月 5,000、剩 24 期，第 1 個月月底剩餘應還 115,000，第 24 個月為 0，第 30 個月仍為 0；每月現金扣款和現在相同，沒有重複扣款。
- **相容性**：沒有 `assets`、`loans`、`existing_debts` 時，`simulate_finance` 的每月資料列除了新欄位為 0 之外，和改動前完全相同。
- **購車流程不變**：現有 vehicle 測試不修改即通過；`run_timeline` 的資料列沒有新欄位。
- **Monte Carlo**：有車時各次試驗的車輛估值相同；`real_net_worth_percentiles` 用含車輛與負債的淨資產計算。
- **前端**：`chartData` 期初淨資產等於 `financialSummary(...).netWorth`；`buildSimulationRequest` 送出 `existing_debts`，不再產生貸款的 range 事件；折舊率欄位的百分比轉換正確。

## 不在本任務範圍

二手車成交資料校準、依車型或品牌的折舊率、賣車事件與處分所得、稅務、房貸或其他資產、前端視覺改版、`index.html` 舊頁面。發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. API 欄位的新增、修改清單，以及淨資產定義改變後受影響的端點。
3. 用測試帳號的例子（月收入 60,000、現金 900,000、投資 500,000、每月投資 3,000、學貸每月 5,000 剩 24 期、2027-09 貸款買 809,000 的車、頭期 200,000、60 期、2.5%）列出：購車前一個月與購車當月的淨資產、期末車輛估值、經濟成本。
4. 測試指令與結果（通過數量、失敗數量）。
5. 沒有完成或刻意保留的部分，以及原因。
