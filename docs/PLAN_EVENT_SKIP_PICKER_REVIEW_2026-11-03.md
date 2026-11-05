# 計畫頁：從對話框選過事件後不再重複選擇與命名 — 檢查報告（2026-11-03）

## 結論

已完成，尚未 commit。

**問題**：使用者在「建立計畫」對話框選了事件（例如購車），進到計畫頁後，畫面還是：
- 再列一次全部事件卡片；
- 要求填「事件名稱」。

**修改後的行為**：
- **從對話框進來**：只顯示該事件的表單。
  - 標題寫「新增事件：購車」。
  - 名稱自動填「購車」，名稱欄位隱藏。
  - 焦點放在第一個可填的欄位（開始月份）。
  - 提供「改選其他事件」按鈕，可以回到事件卡片。
- **在計畫頁直接點卡片**：行為相同，選完就收起卡片。
- **一次性收支、期間每月收支**：仍然顯示名稱欄位，而且必填。這兩種是自訂收支，同一個計畫可能有很多筆（獎金、家電、旅遊），沒有名稱就無法區分。
- **修改事件**：
  - 標題寫「修改事件：購車」，不顯示卡片。
  - 人生事件不顯示名稱欄位，保留原本存的名稱。
- **儲存或取消後**：回到事件卡片，讓使用者選下一筆。

## 改動檔案

| 檔案 | 內容 |
| --- | --- |
| `static/event-templates.js` | 新增 `asksForName(template)`，只有 `group==='custom'` 回傳 true |
| `static/plan.html` | 新增 `#changeTemplate` 按鈕；事件名稱 label 加 `data-event-name hidden` |
| `static/plan-page.js` | 新增 `showTemplate()`，負責收起卡片、設定標題和名稱；新增 `focusFirstField()`。`selectTemplate`、`editEvent`、`resetEditor` 和 `?add=` 進場流程都改成走這兩個函式 |
| `tests/test_event_templates.js` | +1 個測試：只有自訂收支會要求名稱 |
| `tests/test_planner_ui.js` | 斷言 `#changeTemplate`、`data-event-name hidden` 存在 |

資料庫的 `name` 欄位不變。人生事件直接存範本名稱（「購車」、「換工作」），後端和 Supabase 都不需要改。

## 驗證

| 項目 | 結果 |
| --- | --- |
| `node --test tests/*.js` | 220 passed |
| `python -m pytest -q` | 802 passed（含 Codex 進行中的停車場測試） |
| Playwright `modal-skip.e2e.js`（真後端 + fake Supabase，Edge） | 13/13 |
| Playwright `upgrade.e2e.js`（已更新為新行為） | 29/29 |

`modal-skip.e2e.js` 涵蓋的情境：
- 從對話框選購車後，卡片隱藏、標題正確、名稱自動帶入、焦點在開始月份。
- 不填名稱也能儲存，時間軸顯示「購車」。
- 儲存後卡片重新出現。
- 一次性收支會顯示空白的名稱欄位。
- 「改選其他事件」可以回到卡片。
- 從計畫頁點換工作，名稱自動帶入。
- 修改購車時不顯示卡片和名稱。
- 375px 寬度下用 `?add=job_change` 會直接進入換工作表單。
- 沒有 console 錯誤。

截圖：`%TEMP%\fw-pw\modal-skip-desktop.png`、`%TEMP%\fw-pw\modal-skip-mobile.png`。

## 發現

- **P0**：無。
- **P1**：無。
- **P2**：「改選其他事件」目前用預設按鈕樣式，位置在標題下方。如果想做成文字連結樣式需要改 `shell.css`，但 Codex 的停車場任務正在改這個檔案，所以這次沒動。
- **P2**：同一個計畫如果有兩筆購車，時間軸會出現兩個「購車」，只能靠月份和車價區分。目前一個計畫通常只有一台車，先不處理。

## 沒有驗證的部分

- 沒有用真的 Supabase 測試，用的是 fake Supabase。不過名稱欄位沒有改，風險低。
- 工作目錄同時有 Codex 尚未 commit 的停車場改動。這次修改沒有碰那些檔案，commit 時只會加上面列出的 5 個檔案。

## 下一步

- 確認後 commit 上面 5 個檔案，只 add 指定檔案。
- Codex 停車場任務完成後照原計畫檢查。
