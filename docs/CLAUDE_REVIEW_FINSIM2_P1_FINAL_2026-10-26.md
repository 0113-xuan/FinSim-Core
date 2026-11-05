# FinSim 2.0 P1 最終驗收 — Claude 獨立覆審報告

審查日期：2026-10-26（Asia/Taipei）
審查對象：「FinSim P1 最終驗收（2026-10-26）」，commit `30fa3c96194cc2f5cc1bc77f325e3dc6d056f841`
前次審查：`docs/CLAUDE_REVIEW_FINSIM2_P1_2026-10-26.md`（P2-1 ～ P2-4）
審查方式：唯讀。未修改、未提交、未 reset／checkout；HEAD 以 `git archive` 匯出到 repo 外暫存區測試（匯出內無 `.env`，無未追蹤文件）；`AI_ENABLED=false`，AI／Gemini／Supabase 變數皆清空；未啟動伺服器、未呼叫任何外部服務。

## 1. 結論

**前次 4 項 P2 全數修正屬實，無 P0／P1，可進入 P2 規格／車款推薦開發。** 另有 2 項新的低風險 P2（Mock 字面規則的邊界案例），不阻擋。

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD | `30fa3c96194cc2f5cc1bc77f325e3dc6d056f841`，父 commit `a9eb20f`，與報告一致 |
| 提交範圍 | 9 檔、+777／−1：`docs/P1_QUESTIONNAIRE.md`、`static/car-needs{,-state}.js`、`static/car-needs.{css,html}`、`static/vehicle.html`、`tests/browser/car_needs.pw.js`、`tests/test_car_needs.js`、`tests/test_car_needs_integration.py` |
| 財務引擎／API／依賴未改 | `git diff a9eb20f HEAD -- app main.py requirements.txt` 無輸出 |
| 未夾帶其他文件 | 工作區仍有 8 份未追蹤 `docs/*.md`（含 4 份 Claude 審查報告），未被加入提交 |
| 乾淨 HEAD 匯出：Python | `python -m pytest -q -p no:cacheprovider`：**339 passed**（無警告） |
| 乾淨 HEAD 匯出：Node | `node --test tests/*.js`：**110 passed**，0 failed，0 skipped（原 78 ＋ 問卷 32） |
| 無外部請求／危險 API | 問卷程式碼唯一 `fetch` 為 `GET /decisions/vehicle/catalog`；無 `/ai/`、`innerHTML`、`localStorage`／`sessionStorage`、`eval` |
| 入口與相依檔案同一提交 | 前次 P2-4 的「入口連結指向尚未提交頁面」已解除 |

## 3. 前次發現的修正，逐項實測

以 Node 直接呼叫 `static/car-needs-state.js`：

| 前次項目 | 實測 | 結果 |
|---|---|---|
| P2-1 貸款購車缺欄位仍通過 | `financed` 只填年利率 → 錯誤：`down_payment`、`loan_term_months` 皆「請填寫這個欄位。」 | 已修正 |
| P2-1 驗證細節 | 頭期款＝車價預算 → 「頭期款須小於購車預算」；利率 3.123 → 「最多兩位小數」；期數 60.5 → 「請輸入整數」 | 已修正 |
| P2-1 非貸款不留舊值 | 先填貸款三欄再改 `cash` → `down_payment`、`annual_interest_rate`、`loan_term_months` 皆輸出 null | 已修正 |
| 偽造確認 | 貸款不完整時直接設 `state.confirmed=true` → `serialize` 輸出 `status=draft`、`handoff=awaiting_confirmation`；另新增 `confirm()` 會重跑三步驗證 | 已修正 |
| P2-2 利率浮點雜訊 | 1.1→0.011、0.7→0.007、2.5→0.025、0→0、0.01→0.0001、97.99→0.9799、98→0.98（前次為 0.011000000000000001） | 已修正 |
| P2-3 Mock 誤判 | 「我不是很在意保養費低」→ 無候選；「五年後我要出國」→ 無候選；「五年後可能換車」→ 無候選；「我打算持有五年」→ 僅 `five-years`；「我不會持有五年」「不打算持有五年」→ 無候選 | 已修正 |
| P2-3 正向案例 | 「不喜歡休旅車，常載長輩，後座舒服，保養費不要太高」→ 4 項候選齊全 | 維持 |

## 4. 發現（皆非阻擋）

### P2-A — 同一子句內「但是」連接時，正向需求會被前面的否定吃掉（漏判）

實測：「不喜歡休旅車但是常載長輩」→ 只產生 `avoid-suv`，**沒有**「接送長輩」。原因：子句只以標點切分；長輩接送的否定正規式 `(?:不|沒|無需|不用)[^，。]*載長輩` 會跨過「但是」，把「不喜歡休旅車」的「不」當成對「載長輩」的否定。這是漏判而非誤判，使用者仍可在第二步手動勾選，影響有限。

### P2-B — 「不重要」未被視為否定（誤判）

實測：「後座舒服不重要」→ 產生 `comfort`（乘坐舒適）候選。否定清單沒有「不重要」。需使用者逐項確認才會套用，影響有限。

建議：兩項都屬於「有限字面樣本」範圍；P3 換成真實 LLM 前不必深修，但請不要把現有正規式當成通用語意解析，並在 P2 的測試規格中保留這兩個案例作為已知限制。

### 附註（非缺陷）

- `/favicon.ico` 404 為既有問題，報告已揭露。
- `docs/P1_QUESTIONNAIRE.md` 的測試指令列出的是特定 Node 測試檔，而非 `tests/*.js`；我採用 `tests/*.js` 全跑，結果 110 passed。

## 5. 未驗證項目

- **Playwright 桌面（1440×1000）／手機（390×844）流程、截圖、`errors=[]`／`aiRequests=[]`、單車與雙車成本 API 的 200 回應**：未重跑。該流程需要 `npx --yes` 下載外部套件並啟動伺服器，不在本次唯讀審查範圍；僅確認 `tests/browser/car_needs.pw.js` 已隨 commit 提交。
- **實際渲染外觀與 `aria-invalid`／`aria-describedby` 行為**：只檢視狀態模組與測試，未渲染頁面。
- **「不重建全新 OS／依賴環境」**：報告已自述使用本機已安裝依賴；我同樣使用本機 Python／Node，結論不涵蓋乾淨依賴安裝。
- 真實 LLM、推薦演算法：報告明確未實作，不適用。

## 6. 建議下一步

1. 可進入 P2 規格／車款推薦開發。
2. P2 階段維持「後端重新驗證需求，前端 `confirmed` 不是授權」的原則（報告已自述）。
3. 將 P2-A、P2-B 兩個字面案例記入 P2／P3 的已知限制，替換成真實 LLM 時一併納入回歸。
4. 本輪新增的 4 份 Claude 審查報告與其他未追蹤文件，請自行決定哪些要提交。
