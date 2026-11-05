# Codex 任務：建立計畫的對話框與事件選擇

日期：2026-11-02。完成後由 Claude 審查。

## 背景

- 專題主軸是**多種人生事件**。目前建立計畫只是在儀表板的卡片裡輸入名稱；新增事件時，要先在下拉選單選「一次性收支／期間每月收支／換工作／購車」，看不出這個系統能處理哪些人生事件。
- 新的流程：
  1. 按「新增計畫」會跳出對話框，第一步輸入計畫名稱。
  2. 按「下一步」後，畫面列出各種人生事件讓使用者直接選擇。
  3. 選好後建立計畫，進入計畫頁，並直接打開該事件的表單。
- 目前能計算的人生事件只有**購車**（沿用原本的購車決策：車款清單、車貸、持有成本、購車分析）和**換工作**。其他之後才會實作的事件（買房、結婚、生小孩、搬家、旅遊等）先放上去，標示「即將推出」，**不能選**。
- 版面可參考常見理財工具的「建立計畫」對話框，但**只參考結構，不要模仿任何現有產品的名稱、商標、配色或文字**。顏色沿用 `static/style.css` 的變數。
- 這次**不改後端，也不改資料庫結構**。對話框不放「筆記」欄位，因為 `plans` 表沒有這個欄位。

## 工作規則

- 從 `feat/ai-plan-explanation` 建立新分支 `feat/event-template-picker`。這個分支還沒合併到 main，但它修改過 `plan.html` 和 `plan-page.js`，從它建立分支可以避免衝突。**不要 push**。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- `index.html`、`vehicle.html`、`car-needs.html` 以及它們的 JS、CSS 不要修改。所有後端 API 不要修改。
- 全部介面用繁體中文。

## 任務 A：事件範本清單 `static/event-templates.js`

做成純資料加純函式的模組，前端頁面和 node 測試共用。

**每個範本的欄位**

| 欄位 | 說明 |
| --- | --- |
| `id` | 英文代號 |
| `name` | 中文名稱 |
| `description` | 一句白話說明，例如「選車款、付款方式，系統幫你算車貸、持有成本，並做購車分析」 |
| `icon` | 圖示代號 |
| `group` | `life`（人生事件）或 `custom`（自訂收支） |
| `status` | `available` 或 `coming_soon` |
| `eventType` | 對應 `plan_events.type`；只有 `available` 的範本才有 |

**清單內容**（順序照下表）

| id | 名稱 | group | status | eventType |
| --- | --- | --- | --- | --- |
| `vehicle` | 購車 | life | available | `vehicle_purchase` |
| `job_change` | 換工作 | life | available | `salary_change` |
| `home` | 買房 | life | coming_soon | — |
| `moving` | 搬家 | life | coming_soon | — |
| `marriage` | 結婚 | life | coming_soon | — |
| `child` | 生小孩 | life | coming_soon | — |
| `travel` | 旅遊 | life | coming_soon | — |
| `study` | 進修 | life | coming_soon | — |
| `one_time` | 一次性收支 | custom | available | `one_time` |
| `range` | 期間每月收支 | custom | available | `range` |

**純函式**

- `availableTemplates()`：回傳所有可以選的範本。
- `templateById(id)`：依代號找範本。
- `templateForEvent(event)`：依事件的 `type` 找回對應的範本，給時間軸顯示圖示和名稱用。

## 任務 B：建立計畫的對話框

**用原生 `<dialog>` 加 `showModal()`。**對話框放在共用外框（`shell.js`）裡，每一頁都能打開。

**觸發方式**

- 側欄的「新增計畫」改成按鈕，按了在目前頁面打開對話框，不要再導到 `/dashboard.html#new-plan`。
- 儀表板最後一張「新增計畫」卡片，改成一個打開對話框的按鈕，不再直接放表單。

**第一步：命名**

- 標題「建立計畫」。
- 欄位只有「計畫名稱」（必填，最多 80 字）。
- 按鈕「取消」「下一步」。名稱空白時不能按下一步，並在欄位旁顯示原因。

**第二步：選擇第一個事件**

- 標題「想先加入什麼事件？」，下方一句說明：「之後在計畫頁還可以加入更多事件。」
- 分成兩組：
  - 「人生事件」：`group = life` 的範本。
  - 「自訂收支」：`group = custom` 的範本。
- 每個範本是一張卡片，有圖示、名稱和說明，點了就選取，選取時要有明顯的選取狀態。
- `coming_soon` 的卡片：
  - 顯示「即將推出」標籤。
  - 不能選，用 `aria-disabled="true"`，滑鼠游標不能是手指。
  - 鍵盤 Tab 可以停在上面，但按 Enter 或空白鍵不會選取。
- 按鈕「上一步」「先不加事件，直接建立」「建立計畫」。沒有選事件時，「建立計畫」不能按。

**建立之後**

- 用 `store.addPlan({name, kind: 'general'})` 建立計畫，然後導到 `/plan.html?id=<id>&add=<template id>`。選「先不加事件」時不帶 `add`。
- 建立失敗時，錯誤顯示在對話框裡，對話框不要關閉，已輸入的名稱和已選的範本都要保留。

**操作與手機版**

- Esc 和「取消」都能關閉對話框，關閉後焦點回到原本按的按鈕。
- 正在建立時，所有按鈕停用，避免重複建立。
- 寬度 760px 以下時，對話框佔滿寬度，卡片改成一欄，不可以出現橫向捲動。

## 任務 C：計畫頁改用同一套事件選擇

- **新增事件**：把「新增事件」表單裡的「事件類型」下拉選單，換成和對話框第二步同一套卡片，只是改成內嵌在頁面裡，不是對話框。
  - 「即將推出」的卡片一樣顯示，但不能選。
  - 選了可用的範本後，下方顯示該事件的表單。現有欄位和驗證都沿用，不要重寫。
  - 選購車時，表單和「購車分析」照現在的做法：車款清單、自動帶入車價、付款方式、持有成本預設值 placeholder。
- **網址帶 `add`**：網址有 `add=<template id>` 而且是可用的範本時，頁面載入後直接選取該範本，捲動到表單，焦點放在「事件名稱」。
  - 處理完後用 `history.replaceState` 把 `add` 從網址移除，避免重新整理時又選一次。
  - `add` 不存在或是「即將推出」的範本時，忽略它，不顯示錯誤。
- **修改事件**：修改既有事件時，範本固定為該事件的類型，卡片區顯示目前的範本但不能切換。
- **時間軸**：每筆事件的圖示和類型名稱改用 `templateForEvent` 取得，和卡片一致。

## 必要的測試

**Node**

- `event-templates.js`：
  - 範本清單的順序與內容符合任務 A 的表格。
  - `availableTemplates` 只回傳 `available` 的範本。
  - 每個可用範本的 `eventType` 都是 `plan_events.type` 允許的四種之一（`one_time`、`range`、`salary_change`、`vehicle_purchase`）。
  - `templateForEvent` 對四種事件類型都能找回正確的範本。
- 網址參數處理寫成純函式並測試：
  - 可用的範本代號會被選取。
  - 「即將推出」的代號、不存在的代號、沒有 `add` 參數，三種都忽略。
- `tests/test_planner_model.js`、`tests/test_shell_model.js` 等既有測試全部通過。

**瀏覽器**

- 用 Playwright 實際走一次：
  1. 儀表板按「新增計畫」，輸入名稱，按下一步。
  2. 確認「買房」不能選，選「購車」，按建立計畫。
  3. 到計畫頁後，購車表單已打開、焦點在事件名稱。填完儲存，按「購車分析」成功。
  4. 從側欄「新增計畫」打開對話框，按 Esc 關閉，確認焦點回到側欄按鈕。
  5. 選「先不加事件」建立計畫，確認計畫頁沒有預選範本。
  6. 寬度 375 時打開對話框，確認沒有橫向捲動。
- Supabase 可以用模擬資料，計算 API 要打真的後端。可以參考 Claude 的 `%TEMP%\fw-pw\pages.e2e.js`，它用 localStorage 模擬 Supabase，資料能跨頁保留。
- 桌面（1280）和手機（375）寬度各截圖一次對話框的第二步，確認瀏覽器 console 沒有錯誤。

## 不在本任務範圍

- 實作「即將推出」事件的計算。
- 筆記欄位。
- 修改資料庫結構或後端。
- 把 `vehicle.html` 的 A/B 比較、敏感度分析搬進計畫頁。
- 修改 `index.html`、`vehicle.html`、`car-needs.html`。

發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. 新增、修改的檔案。
3. 測試指令與結果（通過數量、失敗數量）。
4. 截圖檔案位置（桌面與手機）。
5. 沒有完成或刻意保留的部分，以及原因。
