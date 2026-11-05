# Codex 任務：P5 核心計算清理

日期：2026-10-30。交辦人：專案主要開發者。完成後由 Claude 審查，審查通過才推送。

## 背景

FutureWallet（FinSim-Core）已確定以下方向：刪除 FSI 且不換成其他加權總分、不再使用「破產」一詞、薪資預設跟著通膨調整。本任務只做這些核心清理，讓現有計算可以在口試中被解釋與驗證。

## 工作規則

- 從 `feat/supabase-schema-v2` 建立新分支 `fix/p5-core-cleanup`，所有工作在這個分支上進行。
- **不要 push**，也不要合併到其他分支。
- 不要讀取或輸出 `.env` 及任何 API key。
- 只 `git add` 你修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的報告與根目錄的 `futurewallet-flow.html` 不要動。
- 每個任務一個 commit，訊息沿用 repo 慣例（`fix:`、`refactor:`、`test:`），結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- 每個 commit 前執行 `python -m pytest -q`，以及 repo 現有的 JS 測試（`tests/*.js`，執行方式見 `docs/P4_TEAM_TEST_GUIDE.md`）。全部通過才 commit。
- 購車流程（`/decisions/vehicle*`、`vehicle.html`、`car-needs.html`）的計算結果，除了任務 C、D 明確要求的部分，不可以改變。

## 任務 A：刪除 FSI

目標：程式、API 回應、前端、測試中都不再有 FSI 或由 FSI 推出的風險等級。

範圍（以 `git grep -n -i -E "fsi|classify_risk|risk_level|risk_classification"` 為準）：

- 刪除 `app/core/fsi.py`。
- `app/core/simulation.py`：每月資料列移除 `fsi`、`risk_level`；摘要移除 `max_fsi`、`avg_fsi`、`high_risk_months`、`first_risk_month`、`risk_level`。移除 `evaluate_legacy_risk` 參數，並同步修改 `app/services/vehicle_decision.py` 的呼叫。
- 摘要改為保留或新增這些現金指標：`minimum_cash_balance`、`minimum_cash_month`、`first_negative_cash_month`（從未小於 0 時為 `null`）、`minimum_emergency_fund_months`。
- `app/core/monte_carlo.py`：移除 `avg_max_fsi`、`high_risk_month_distribution`、`risk_classification`、每條樣本路徑的 `fsi`。
- `app/core/advisor.py`：移除加權分數（`score`）。方案比較改為並列各方案的指標；需要預設排序時，先依現金不足機率由低到高，再依期末現金中位數由高到低，並在回應中用一個欄位寫明這條排序規則。
- `app/services/optimizer.py`、`app/services/report_generator.py`、`app/core/transparency.py`、`app/schemas.py`、`static/app.js`、`static/index.html`、`static/transparency.js`：移除 FSI 相關欄位與顯示。
- 更新或刪除相關測試，並新增測試確認 API 回應不含 `fsi` 字樣。

驗收：`git grep -n -i "fsi"` 在 `app/`、`static/`、`tests/` 底下沒有結果（測試中「確認不含 FSI」的斷言除外）。

## 任務 B：移除「破產」用詞與指標

- `app/core/monte_carlo.py`：刪除 `bankrupt_probability`。把 `probability_negative_balance` 改名為 `probability_cash_shortfall`，定義為「模擬期間任一月底現金小於 0 的試驗比例」，並在回應中附上這段定義文字。
- `app/schemas.py` 的 `bankruptcy_probability_below` 改名為 `cash_shortfall_probability_below`，`optimizer.py` 同步修改。
- 前端（`static/index.html`、`static/app.js`）的「破產機率」改為「現金不足機率」，對應的 id 一併改名。
- `advisor.py`、`report_generator.py` 的文字不得出現「破產」。

驗收：`git grep -n -i "bankrupt\|破產"` 在 `app/`、`static/`、`tests/` 底下沒有結果（測試斷言除外）。

## 任務 C：修正換工作後不再調薪

問題：`app/core/events.py` 的 `get_income_for_month` 遇到 `salary_change` 後，薪資固定為 `new_salary`，之後不再調薪。

修正規則：`salary_change` 生效後，收入 = `new_salary × (1 + raise_rate) ^ (自生效月份起已滿的年數)`。生效前維持原本的計算。

測試至少涵蓋：

- 第 13 個月換工作，第 13–24 個月等於 `new_salary`，第 25 個月起套用一次調薪。
- `raise_rate = 0` 時，換工作後的薪資保持不變。
- 兩次 `salary_change` 時，以較晚的那次為準。

## 任務 D：薪資預設跟著通膨

規則：使用者沒有提供 `raise_rate` 時，有效調薪率等於有效通膨率；使用者有提供時，一律使用使用者的值。

- `app/schemas.py` 的 `ProfileInput.raise_rate` 預設改為 `None`，計算時再解析成有效值。
- `app/decision_assumptions.py` 的 `raise_rate` 說明改為「預設等於通膨率」。`vehicle_decision.resolve` 在使用者未提供時填入有效通膨率，來源標為 `system_assumption`；假設清單與前端顯示的值必須是實際使用的數字。
- `app/core/monte_carlo.py`：**不要重新設計抽樣方式**（改用台灣歷史資料是下一個任務）。這次只做到：
  - 使用者提供的 `raise_rate` 或 `inflation_rate` 不可以被隨機值覆蓋。
  - 使用者未提供 `raise_rate` 時，每次試驗的調薪率等於該次試驗抽到的通膨率。
  - 回應中加入 `sampling_note`，寫明目前的抽樣範圍是暫時設定、沒有資料來源。
- 新增測試：未提供 `raise_rate` 時，確定性模擬的第 13 個月收入 = 原薪資 × (1 + 通膨率)。

## 不在本任務範圍

Supabase 登入與資料表串接、投資帳戶、台灣歷史資料與新的 Monte Carlo、RAG、前端改版。發現這些範圍內的問題時，寫進回報，不要修改。

## 完成後的回報

在對話中回報以下內容，不需要另外建立檔案：

1. 每個 commit 的 hash 與一句話說明。
2. API 欄位的增減與改名清單（前後端都要對得上）。
3. 測試指令與結果（通過數量、失敗數量）。
4. 沒有完成或刻意保留的部分，以及原因。
