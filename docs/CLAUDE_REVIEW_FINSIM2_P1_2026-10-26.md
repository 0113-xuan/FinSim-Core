# FinSim 2.0 P1 選車問卷 — Claude 獨立審查報告

審查日期：2026-10-26（Asia/Taipei）
審查對象：「FinSim 2.0 P1 選車問卷補齊與驗收」（日期 2026-10-25）
審查 HEAD：`a9eb20f`（與報告一致）
審查方式：唯讀。未修改、未提交、未 reset／checkout 任何既有檔案。測試時 `AI_ENABLED=false`，Gemini／OpenAI／Supabase 變數皆清空。僅以 Node 直接呼叫狀態模組做探測，未啟動伺服器、未呼叫任何外部服務。

## 1. 結論

**有條件通過：功能與資料契約基本屬實，無 P0／P1；有 4 項 P2 建議在 P2 階段開始前處理，另有 1 項提交風險需要注意。**

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD | `a9eb20f8a0a48ce0feb9a14e4abf52289c279019`，與報告相符 |
| 全 Python 測試 | `python -m pytest -q -p no:cacheprovider`：**339 passed**，2 個既有 JWT 短金鑰警告 |
| 全 Node 測試 | `node --test tests/*.js`：**90 passed**，0 failed，0 skipped |
| 未改財務引擎／正式 API | `git status` 中沒有 `app/` 變更；已追蹤檔案只有 `static/vehicle.html` 一處修改（新增「幫我選車」連結） |
| 無 AI／外部請求 | `car-needs.js`、`car-needs-state.js`、`car-needs.html` 中唯一的 `fetch` 是 `GET /decisions/vehicle/catalog`；沒有 `/ai/`、沒有 `innerHTML`、沒有 `localStorage`／`sessionStorage`、沒有 `eval` |
| 資料欄位對應 | `financial_profile` 的 `salary`、`fixed_expense`、`variable_expense`、`balance`、`required_monthly_debt`、`existing_debts`、`raise_rate`、`inflation_rate` 與 `app/decision_schemas.py` 的 `DecisionProfile` 欄位名完全相同 |
| `min_seats` 語意 | 表單標籤為「主要乘車人數（含駕駛）」，因此 `min_seats = usual_passengers` 正確 |
| null／空陣列契約 | `initialAnswers` 以 `null`／`[]` 為預設；`serialize` 對隱藏分支輸出 null（停車為 `none` 時 `monthly_parking=null`；選項不含 BEV 時充電欄位 null；未勾選財務資料時 `financial_profile=null`；非貸款時 `down_payment`／`interest`／`term` 皆 null） |
| 自有車位不補 0 | `monthly_parking` 在 `parking_type='own'` 時為選填，未填即 null |
| Mock 否定處理 | 長輩接送、保養費、後座舒適對「不／沒／無需／不用／不在意」等字樣在同一子句內不產生候選；套用前會用目前文字重新驗證候選，不能偽造候選 |
| 套用衝突保護 | 偏好 SUV 時不能套用「排除 SUV」；持有年限與第二步不同時拒絕套用 |
| 整合測試 | `tests/test_car_needs_integration.py` 驗證入口連結、4 個靜態資源都能由既有 FastAPI 提供、catalog 與根路徑轉址仍可用 |
| 提交範圍 | 沒有 commit、沒有 push；P1 檔案皆為未追蹤 |

## 3. 發現

### P2-1 — 貸款購車可在沒有頭期款與期數的情況下通過驗證

實測：`payment_method='financed'`、僅填年利率 1.1，未填 `down_payment` 與 `loan_term_months`，`validate(answers, 1)` 回傳 `{}`（無錯誤）。原因是這兩個欄位只列入 `fields`（驗範圍），沒有列入 `required`。

後果：使用者可確認並匯出 `status: confirmed`、`recommendation_handoff.status: ready_for_p2` 的資料，但貸款條件不完整。報告說 P2／P3 會再做後端驗證，所以不阻擋 P1，但建議問卷端就要求貸款購車必填頭期款、年利率與期數，避免下游收到「已確認卻不可計算」的快照。

### P2-2 — 年利率轉小數會產生浮點雜訊

`serialize` 以 `annual_interest_rate / 100` 轉換。實測 `1.1 → 0.011000000000000001`，`0.7 → 0.006999999999999999`（`3 → 0.03`、`2.5 → 0.025` 正常）。後端以 float 接收不會出錯，但之後若做完整 JSON 快照比對或雜湊會不穩定。建議輸出時取整，例如 `Number((rate / 100).toFixed(6))`。

### P2-3 — Mock 規則有兩個會誤判的字面案例（需使用者逐項確認，影響有限）

以文字「我不是很在意保養費低，五年後我要出國」實測：
- 「保養費較低」被列為候選。否定正規式只涵蓋 `不在意／不需要／不用／無需`，不涵蓋「不是很在意」。
- 「預計持有 5 年」被列為候選，證據只有「五年後」。「五年後我要出國」不一定代表持有 5 年，標籤「預計持有 5 年」超出原文證據。

因為候選必須由使用者逐項套用，且報告已明講這是有限字面樣本，不屬於缺陷；但五年這條的標籤建議改成較保守的描述（例如「文中提到五年後」），或移除，避免 P3 換成真實 LLM 時沿用過度推論的設計。

### P2-4 — 已追蹤的 `vehicle.html` 連結指向尚未提交的頁面

`static/vehicle.html` 的修改（新增 `<a href="/car-needs.html">幫我選車</a>`）是唯一的已追蹤檔案變更，但 `car-needs.html`、`car-needs.js`、`car-needs-state.js`、`car-needs.css` 全部是未追蹤檔案。若只提交 `vehicle.html`，會在 HEAD 上產生指向 404 的入口。請把 `vehicle.html` 與 4 個 `static/car-needs*` 檔案、兩個測試檔與 `tests/browser/` 放在同一個 commit。這與 P0 階段「相依修改未提交」是同一型態的風險，建議問卷驗收後立即提交，而不是留到 P2 之後。

### 附註（非缺陷）

- 報告所述的 `/favicon.ico` 404 屬既有問題，與本功能無關。
- 同時有兩份 P1 工作報告（`FINSIM_2_P1_WORK_REPORT_2026-10-23.md` 與 `2026-10-25.md`）皆為未追蹤，提交前建議決定保留哪一份。

## 4. 未驗證項目

- **Playwright 桌面／手機流程**（1440×1000、390×844）、鍵盤操作、下載 JSON、無橫向溢位、截圖：我沒有重跑。該流程需要 `npx --yes` 下載外部套件並啟動伺服器，未在本次唯讀審查中執行。我只確認 `tests/browser/car_needs.pw.js`（86 行）存在，且報告中的 Node／Python 測試數字可重現。
- **UI 的實際外觀與無障礙描述**（錯誤提示 `aria-describedby` 清除過期 reference）：只檢視狀態模組與測試，未實際渲染頁面。
- **`car-needs.js` 的完整 DOM 行為**：只檢查有無危險 API（`innerHTML`、外部請求），沒有逐行審查渲染邏輯。
- 真實 LLM、車款推薦、五年現金支出排序：報告明確說尚未串接，本次不適用。

## 5. 建議下一步

1. 把問卷相關檔案與 `vehicle.html` 一起提交成一個 commit（P2-4）。
2. 修 P2-1（貸款購車必填頭期款／利率／期數）與 P2-2（利率取整）。
3. 決定五年那條 Mock 規則的措辭（P2-3）。
4. 之後再進入下一階段，避免重演 P0 的 HEAD 相依問題。
