# 計畫頁「計算狀態與錯誤就地顯示」修改報告（2026-11-04）

來源：`docs/CLAUDE_CRITIQUE_PLAN_PAGE_2026-11-04.md` 的問題 2。分支 `feat/frontend-upgrade`，未 commit。

## 問題

按鈕在頁底，「正在計算…」與錯誤訊息卻在頁首；`ctx.perform` 把整頁 fieldset 與按鈕全部 disabled，焦點會掉到 body，螢幕閱讀器使用者尤其受影響；頁首狀態與多個 `aria-live` 同時更新。

## 改了什麼

1. `static/shell.js`
   - `showError(error, id='pageError')`：可指定顯示位置。
   - `ctx.perform(action, {scope, errorId})`：
     - `scope`：只鎖定指定區塊內的 fieldset 與按鈕（預設仍是整個 `#pageContent`，其他頁面行為不變），並在該區塊加 `aria-busy`。
     - `errorId`：失敗訊息顯示在指定元素，不再固定在頁首。
     - 結束後把焦點還給原本的元素；action 可回傳一個元素，焦點就移到那裡。
     - 操作進行中又點了別的操作時，不再完全沉默，會在頁首狀態說明「上一個操作還在進行，請稍候。」，結束後清掉。
2. `static/plan.html`：在「執行模擬」與「用白話解釋結果」按鈕旁各加 `role="status"` 的進度行與 `role="alert"` 的錯誤行；模擬區塊加 `id="simulationPanel"`。
3. `static/plan-page.js`
   - 模擬：按鈕旁顯示「正在計算，請稍候…」加 spinner；完成後顯示「模擬完成，結果在下方。」並把焦點移到結論標題；失敗時清掉進度行，錯誤顯示在按鈕下方。
   - AI 解釋：同樣的做法，鎖定範圍是解釋區塊本身。
   - 不再用頁首 `#pageStatus` 報這兩項狀態，避免重複朗讀。
4. `static/shell.css`：`.run-status`、spinner（尊重 `prefers-reduced-motion`，減少動態時只顯示靜態圓環）。
5. 測試：`tests/test_planner_ui.js` 新增一則，檢查上述結構。

## 刻意沒做

- 文案「後端預設」、「Monte Carlo」等：第 3 項。
- 事件新增／刪除等其他操作仍用整頁鎖定與頁首狀態（只多了焦點還原與忙碌提示）。
- 沒有改後端或資料庫。

## 驗證

- `node --test tests/*.js`：238 通過。`node --check` 通過。
- 視覺：計畫頁需要登入，無法直接開。把模擬區塊放進登入頁並套用狀態後檢查：按鈕、spinner 進度行、紅色錯誤框依序排在同一視線內。這不是真實流程的截圖。
- 沒有做：真實計算流程中焦點移動、螢幕閱讀器朗讀、逾時 30 秒的實際行為，都沒有在瀏覽器實測。

## 注意

- `static/plan-page.js` 在這次工作期間被另一方同時修改（出現了 `qa` 變數，疑似 AI 計畫問答任務）。我只改了上述片段，合併 commit 前請確認兩邊改動沒有互相覆蓋。
- 焦點移到的 `#conclusionHeading` 帶 `tabindex="-1"`，只能程式聚焦，不進入 Tab 順序。
