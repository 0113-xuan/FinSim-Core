# 計畫頁「結論卡」修改報告（2026-11-04）

來源：`docs/CLAUDE_CRITIQUE_PLAN_PAGE_2026-11-04.md` 的問題 1（答案優先）。分支 `feat/frontend-upgrade`，未 commit。

## 改了什麼

結果區最上方新增一張白話結論卡，其餘數字退到後面。

1. `static/results-model.js`：新增純函式 `conclusion({summary, mc, startPeriod, months, simulations})`，回傳 `tone`、`headline`、三項事實、一句限制說明。沒有新增任何計算，數字全部取自既有的 `/simulate` 與 `/monte-carlo` 回應。
2. `static/plan.html`：`#simulationResults` 的順序改為：結論卡 → AI 白話解釋 → 淨資產範圍圖 → 現金投資淨資產圖 → 「看全部數字」（`<details>`，預設收合，內含原本的 16 張數字卡）→ 假設 → 購車。
3. `static/plan-page.js`：新增 `renderConclusion`，`renderResults` 多收一個 `months` 參數。
4. `static/shell.css`：結論卡與「看全部數字」樣式，手機單欄。
5. 測試：`tests/test_results_model.js`、`tests/test_planner_ui.js` 各加一則。

## 結論卡內容

標題句只講一件事，三種情況：

| 情況 | 句子 |
|---|---|
| 平均情況下現金會低於 0 | 照平均情況推算，現金會在 YYYY-MM 第一次低於 0。 |
| 平均情況不會，但隨機模擬有機率 | 照平均情況推算，現金不會低於 0，但在較差的情況下可能會。 |
| 都沒有 | 300 次隨機模擬中，現金都沒有低於 0。 |

三項事實：現金最低會到多少（含月份）、現金不足機率、期末淨資產一般情況（含 9 成範圍）。最後一行：「這是依台灣歷史資料做的模擬，不是預測，也不保證未來會發生。」第一種情況標題用 `--danger` 色，但語意由文字承擔，不靠顏色。

## 刻意沒做（留給後續項目）

- 計算狀態、按鈕旁回饋、完成後移動焦點：第 2 項（harden）。
- 「後端預設」、「Monte Carlo」、「亂數種子」等用語：第 3 項（clarify 文案）。仍留在「看全部數字」與假設區。
- 沒有改任何後端、資料庫或 Supabase 設定。

## 驗證

- `node --test tests/*.js`：231 通過。
- `python -m pytest -q`：850 通過。
- 偵測器：`plan.html` 只剩先前判定為誤報的 `em-dash-overuse`。
- 視覺：計畫頁需要登入，無法直接開。我在 localhost 的登入頁注入結果區 markup 與假資料做版面檢查：桌面三欄並排、手機（375px）單欄、無水平捲動、「看全部數字」摘要高 44px。這不是真實頁面的截圖，請登入後目視確認。

## 需要你確認

1. 標題句用語是否合適；「照平均情況推算」指的是確定性模擬（固定平均通膨與報酬）。
2. AI 解釋區塊被我移到圖表之前。它的資料外傳告知文字一起移動、內容沒改。如果你希望它仍在最底部，可以還原這一項。
3. `shell.css` 沒有版本參數，瀏覽器可能快取舊檔；開發時若樣式沒更新請強制重新整理。
