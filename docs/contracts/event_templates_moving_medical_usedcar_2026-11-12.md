# 契約：新增事件範本「搬家」「醫療支出」「二手車」

日期：2026-11-12。分支 `feat/event-templates`（從 `main` `1a88076` 開出）。功能凍結 11/15。
本檔是前端與後端唯一的共同依據。

## 1. 決定（已定）

| 項目 | 決定 | 理由 |
| --- | --- | --- |
| 資料庫 | 不改。`plan_events.type` 仍只有 `one_time`、`range`、`salary_change`、`vehicle_purchase` | 改 type 要使用者執行 SQL，時間不夠 |
| 範本怎麼辨識 | 新範本存進既有的 `details` jsonb：`details.template` = `moving`、`medical`、`used_car` | `details` 欄位本來就是「事件完整參數」 |
| 搬家、醫療 | `type = 'range'`，同時使用既有欄位 `amount`（一次金額）與 `monthly_amount`（每月金額） | 一個計畫只放一個事件，一次費用與每月變化必須在同一個事件；兩個欄位資料表已有 |
| 二手車 | `type = 'vehicle_purchase'`，重用購車流程，不選車款、自己填車價 | 購車流程本來就支援自訂車款 |
| 預設數字 | 一個都不預填。所有金額由使用者填 | 專案原則：沒有出處的數字不放 |
| 買機車、買房 | 不做，維持「之後會加入」 | 沒有有出處的機車價格與稅費資料；本次範圍 |
| 換工作 | 已存在（`job_change`），不動 | — |

## 2. 範本清單（`static/event-templates.js`）

| id | 名稱 | 說明（畫面文字） | group | eventType | `details.template` |
| --- | --- | --- | --- | --- | --- |
| `moving` | 搬家 | 安排搬家一次費用，以及搬家後每月租金或通勤的變化。 | life | `range` | `moving` |
| `medical` | 醫療支出 | 安排一次醫療自付，以及之後一段期間每月的回診或藥費。 | life | `range` | `medical` |
| `used_car` | 二手車 | 自己填二手車價格與付款方式，系統幫你算車貸與持有成本。 | life | `vehicle_purchase` | `used_car` |

- `moving` 從「之後會加入」改為 `available`；`medical`、`used_car` 為新增，三張卡片排在 `job_change` 之後、`home` 之前。圖示：`moving` 沿用現有，`medical`、`used_car` 各補一個 `icon` 路徑（`event-picker.js`）。
- 範本新增布林欄位 `preset: true`（三張新卡片）；既有 `vehicle`、`range` 等沒有此欄位。
- `templateForEvent(event)`：先找 `id === event.details?.template` 且 `eventType === event.type` 的範本；找不到再找 `eventType === event.type` 且不是 `preset` 的範本。所以既有事件（沒有 `details.template`）行為不變。
- `asksForName`：沿用既有規則（`life` 群組的名稱預填範本名稱，可修改）。

## 3. 儲存格式

| 範本 | `type` | `amount` | `monthly_amount` | `end_period` | `details` |
| --- | --- | --- | --- | --- | --- |
| 搬家 | `range` | 一次費用，支出為負、收入為正（可為 0） | 每月租金或通勤變化，支出為負（可為 0） | 選填，空白 = 到模擬結束 | `{"template":"moving"}` |
| 醫療支出 | `range` | 一次自付，支出為負（可為 0） | 每月回診或藥費，支出為負（可為 0） | 選填，空白 = 到模擬結束 | `{"template":"medical"}` |
| 二手車 | `vehicle_purchase` | null | null | null | 現有購車 `details` 全部欄位，另加 `"template":"used_car"` |

既有的自訂 `range`（「期間每月收支」）仍存 `amount: null`、`details: {}`，行為完全不變。

## 4. 前端行為

**表單（`plan.html`、`plan-page.js`）**
1. 搬家與醫療選了之後顯示：事件名稱（預填「搬家」「醫療支出」，可改）、開始月份、「一次性金額」（含收入／支出選項，預設支出）、「每月金額」（含收入／支出選項，預設支出）、結束月份（選填）。兩個金額欄位都必填，可填 0；兩者都是 0 時顯示錯誤：`一次費用與每月金額不能都是 0`。
2. 自訂「期間每月收支」不顯示「一次性金額」，行為不變。
3. 二手車：沿用購車三步驟；不顯示「車款」下拉（`vehicle_catalog_id` 一律為空）；車價欄位標籤改為「二手車價格」；不預填任何折舊率或保養費。
4. 修改已存的事件時，依 `details.template` 還原正確的範本與欄位；修改時不可變更範本。

**請求（`planner-model.js`）**
5. `range` 事件有一次金額時，送 `one_time_amount`：`{type:'range', name, start_month, end_month, monthly_amount, one_time_amount}`。`amount` 為 null 或 0 時不送 `one_time_amount`（與現在一致）。
6. **`details.template` 不可送到任何後端 API**。後端 `PlannerVehicleDetails` 與決策 payload 都是 `extra=forbid`，多一個欄位會 422。必須在這兩處排除：`buildSimulationRequest` 把購車事件 push 進 `vehicles` 時（`structuredClone(event.details)` 之後刪掉 `template`），以及 `buildVehicleDecisionRequest` 迭代 `details` 時略過 `template`。
7. `shell-model.js` 的 `eventSummary`：`range` 且 `amount` 非 0 時顯示 `一次 ${money(amount)}，每月 ${money(monthly_amount)}，至 ${end_period||'模擬結束'}`；其餘維持原文字。`vehicle_purchase` 摘要不變。
8. 事件列表與比較頁顯示範本名稱（`搬家`、`醫療支出`、`二手車`），不是通用的「期間每月收支」「購車」。`shell.eventNames` 只依 `type`，所以名稱改由 `templateForEvent` 取得。

**不變的**
- 引擎已支援（`get_one_time_asset_impact` 對 `range` 在起始月加上 `one_time_amount`），後端不用改引擎。
- AI 說明、比較頁、模擬請求都用 `eventSummary` 與 `request.events`，不另外改。
- 畫面用語：不出現診斷或疾病字眼，醫療只寫「醫療支出」「自付」「回診或藥費」。

## 5. 後端（只有知識庫）

在 `data/knowledge/` 補三段說明，並在 `tests/test_plan_qa.py` 補黃金測試：
- `moving`：搬家事件怎麼算（起始月一次費用，加上之後每月租金或通勤變化，到結束月份或模擬結束）。
- `medical`：醫療支出事件怎麼算（只算金錢，一次自付加每月回診或藥費；金額由使用者填，不是預測）。要寫明它與計畫頁「加入意外風險」是兩件事：前者是你自己設定的已知支出，後者是隨機抽的假設，兩個都開會重複計入。
- `used_car`：二手車事件怎麼算（與購車相同的車貸與持有成本計算，車價與保養費由使用者填，沒有預設值）。

不得出現診斷、存活字眼，不得寫任何價格、機率或統計數字。

## 6. 測試

**前端（node）**
1. `templateForEvent`：有 `details.template` 時回對應範本；沒有時回通用範本（既有行為不變）。
2. 三個範本都 `available`，`moving` 不再在「之後會加入」清單。
3. `buildSimulationRequest`：搬家事件產生的 `range` 帶 `one_time_amount`；自訂 `range` 不帶；二手車送出的 `vehicles[].details` 不含 `template`。
4. `buildVehicleDecisionRequest`：`payload` 不含 `template`。
5. `eventSummary`：搬家、醫療的一次加每月文字；自訂 `range` 文字不變。
6. 一次與每月都是 0 時報錯，訊息與契約相同。
7. 二手車不顯示車款下拉，`vehicle_catalog_id` 為空。
8. 不使用 `innerHTML` 插入使用者文字。
9. 375px 無水平捲動（Playwright 截圖由 Claude 驗收）。

**後端（pytest）**
10. 契約第 5 節三段說明的黃金測試；`tests/test_knowledge_base.py` 仍通過。
11. 既有測試全過（數量不得減少）。

## 7. 不在範圍

買機車、買房、修改資料表、預設金額或折舊率、二手車的專屬資料庫、醫療診斷、變更 `/simulate` 或任何 API 的欄位。
