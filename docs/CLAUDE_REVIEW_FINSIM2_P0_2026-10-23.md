# FinSim 2.0 P0 工作報告 — Claude 獨立審查報告

審查日期：2026-10-23（Asia/Taipei）
審查對象：「FinSim 2.0 P0 最終工作報告」（日期 2026-10-22，基準 `d3483f4`）
審查 HEAD：`d1ca696`
審查方式：唯讀。未修改、未提交、未 reset／checkout 任何檔案；HEAD 匯出至 repo 外暫存區測試。

## 1. 結論

**有條件通過（需先處理 1 項 P1 再整合）。**

報告中的程式碼變更、測試數字與計算語意說法屬實；但已提交的 HEAD 無法獨立通過測試，且前端在 HEAD 單獨部署時會誤顯示壓力測試為「尚未判定」。

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| Commit 清單 | `a1de21d`、`e921c9f`、`c14d95c`、`c5da977`、`d1ca696` 的檔案內容與報告描述一致 |
| 工作區保護 | 原有 5 個修改檔（`vehicle_decision.py`、`vehicle.html`、`vehicle.js`、`test_vehicle_decision.py`、`test_vehicle_ui.js`）與 3 份未追蹤文件仍在，未被夾帶提交 |
| 全 Python 測試（工作區） | `python -m pytest -q`：**337 passed**，2 個既有 JWT `InsecureKeyLengthWarning` |
| 全 Node 測試（工作區） | `node --test tests/*.js`：**78 passed**，0 failed，0 skipped |
| 測試環境 | `AI_ENABLED=false`，Gemini／OpenAI／Supabase 變數皆清空 |
| 事件壓縮數學等價性 | 正確。`inflation_factor(month, rate) = (1+rate) ** ((month-1)//12)`，每 12 個月（從模擬月 1 起算）為一段；壓縮後每段使用同一係數、同一金額，購車月位於段中間時只計入該段剩餘月份 |
| 雙車 financial 分支 | 與 `simulate_vehicle_decision` 的 `baseline`、`metrics`、`constraints`、`ownership_costs` 使用完全相同的函式；僅省略回應未使用的壓力測試與價格上限搜尋 |
| 前端壓力判定邏輯 | `stressVerdict` 區分 `false`、`null/undefined`、`applicable=false`，邏輯與報告描述一致 |
| `git diff --check` | 通過（僅 LF→CRLF 提示） |

## 3. 發現

### P1 — 已提交 HEAD 單獨不可用（必須在整合前處理）

**證據**：以 `git archive HEAD` 匯出到暫存區後執行測試：

- Python：**331 個測試，7 failed、324 passed**
  - 失敗：`test_vehicle_p0_regression.py` 的 6 個 API 快照案例（`financed_defaults`、`cash_month13_inflation_offset`、`zero_budget_zero_apr_short_loan`、`month58_long_loan_expiring_debt`、`claude_wealthy_unemployment`、`no_feasible_price`）＋ `test_wealthy_unemployment_via_formal_api`
  - 錯誤：`KeyError: 'passed'`
- Node：75 passed，0 failed

**原因**：commit `a1de21d` 讓前端讀取 `stress.passed`，但 HEAD 的 `simulate_vehicle_decision` 沒有輸出壓力測試層級的 `passed` 欄位（HEAD 只有 constraint 層級的 `passed=`）。該欄位只存在於**尚未提交**的 `app/services/vehicle_decision.py` 修改中。

**後果**：若僅以 HEAD 部署或讓他人 checkout，前端 `s.passed === true/false` 皆不成立，所有適用的壓力情境都會顯示「N 種尚未判定」，標題顯示「部分壓力測試尚未判定，請重新評估」。

**說明**：原報告有警告「單獨 checkout HEAD 不能視為相同已驗收版本」，但未指出實際會有 7 個測試失敗與上述畫面後果。

**建議**：整合／Review 前，將相關的未提交後端修改（失業後端判定、stress `passed` 欄位、cent 搜尋）整理為獨立 commit，使 HEAD 自身通過全部測試；或把 P0 回歸測試與快照調整到可在該 commit 序列下通過。

### P2 — 前端 `unknown` 狀態無樣式

`static/vehicle.js` 設定 `riskHeadline.dataset.state` 為 `'unknown'`，但 `static/vehicle.css` 只定義 `[data-state="failed"]`，`unknown` 與 `passed` 外觀無差異。功能不受影響，建議補樣式以免使用者看不出「尚未判定」。

### P2 — `.git` 內的備份目錄

報告提到原始檔副本放在 `.git/p0-final-start-20261022/`。該目錄不被 Git 追蹤，日後清理 `.git` 或重新 clone 時會遺失，若仍需要請移到 repo 外。

## 4. 未驗證項目

- **效能數字**（單車 3.6 秒→0.53 秒、雙車 7.5 秒→0.04 秒、改善 85%／99%）：未重跑 `scripts/benchmark_vehicle_p0.py`，僅確認腳本與前後 JSON（`docs/p0-final-before.json`、`docs/p0-final-after.json`）存在。
- **Playwright 瀏覽器驗收與截圖**（1365×900、390×844）：未檢視報告所稱的 Temp 截圖。
- **cProfile 呼叫次數**（67,210,502→6,982,022）：未重現。
- 正式環境冷啟動、並發與 p95：報告本身亦聲明未驗收。

## 5. 建議下一步

1. 處理 P1：讓 HEAD 自身通過 337／78 測試（拆出獨立的後端修正 commit）。
2. 補 `unknown` 狀態樣式（P2）。
3. 以上完成後，再交 Claude Review 並進入 AI 選車問卷開發。

## 6. 附註

- 審查期間在本機啟動過一個 `python main.py` 開發伺服器（port 8000，使用 repo 的 `.env`）；該背景程序已隨前一個 session 結束而停止，審查本身未依賴它。
- 本審查未呼叫任何外部服務。
