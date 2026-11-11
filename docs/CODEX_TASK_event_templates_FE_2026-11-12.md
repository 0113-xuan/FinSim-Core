# Codex 任務（前端）：新增事件範本「搬家」「醫療支出」「二手車」

日期：2026-11-12。分支 `feat/event-templates-fe`（從 `feat/event-templates` 的 HEAD 開出，與後端同一個 commit）。期限：11/13。

## 背景

計畫頁目前可選的事件只有購車、換工作、一次性收支、期間每月收支。要新增「搬家」「醫療支出」「二手車」三張卡片。不改資料表，也不改後端 API：搬家與醫療用既有的 `range` 事件同時存一次金額與每月金額，二手車重用購車流程。

## 契約

`docs/contracts/event_templates_moving_medical_usedcar_2026-11-12.md`（唯一依據，不要複製第二份）。重點是第 4 節第 6 點：`details.template` 絕不可送到任何後端 API。

## 你可以改的檔案

`static/event-templates.js`、`static/event-picker.js`、`static/plan.html`、`static/plan-page.js`、`static/planner-model.js`、`static/shell-model.js`、`static/shell.css`、`static/compare-model.js`（只在需要顯示範本名稱時）、`tests/*.js`、`tests/browser/**`。

不可以改：`app/**`、`main.py`、`data/**`、`tests/*.py`、`docs/**`、`static/index.html`、`static/vehicle.html`、`static/car-needs.html`。

## 要做的事

1. `event-templates.js`、`event-picker.js`：新增三張範本與 `preset` 欄位、`templateForEvent` 新規則、`moving` 改 `available`、兩個新圖示。完成的樣子：卡片順序為購車、換工作、搬家、醫療支出、二手車，「之後會加入」清單不再有搬家，既有事件的辨識結果不變。
2. `plan.html`、`plan-page.js`：搬家與醫療顯示一次金額加每月金額兩組欄位（各含收入／支出，預設支出）、結束月份選填；兩者都為 0 時顯示契約指定的錯誤；自訂「期間每月收支」不變。完成的樣子：契約第 4 節第 1、2、4 點。
3. 二手車：沿用購車三步驟，不顯示車款下拉，車價標籤為「二手車價格」，儲存時 `details.template = 'used_car'`。完成的樣子：契約第 4 節第 3 點。
4. `planner-model.js`：`range` 帶 `one_time_amount`；排除 `details.template`（兩處，見契約第 4 節第 5、6 點）。完成的樣子：契約測試 3、4 通過。
5. `shell-model.js`、`plan-page.js`、比較頁：摘要文字與範本名稱顯示（契約第 4 節第 7、8 點）。完成的樣子：事件列表寫「搬家｜2026-12｜一次 …，每月 …，至 …」。

## 必要的測試

契約第 6 節「前端」9 條。另：`tests/test_planner_ui.js` 若有寫死範本數量或「之後會加入」文字的斷言，跟著改，並在回報列出改了哪幾條；不可刪測試。

## 不在範圍

契約第 7 節全部。不預填任何金額、折舊率或保養費。

## 紅線

- 介面文字繁體中文、白話，不出現「Monte Carlo」；醫療只寫「醫療支出」「自付」「回診或藥費」，不出現診斷或疾病字眼（見 `PRODUCT.md`）。
- 不用 `innerHTML` 插入使用者文字；只用 anon key，不用 service_role。
- 不 push、不 `git add .`（只 add 自己改的檔案）、不讀或輸出 `.env`。
- commit 前 `python -m pytest -q` 與 `node --test tests/*.js` 全過。基準：pytest 980 passed、node 278 pass。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 契約沒寫的文案或規則不要自己選，寫進回報。

## 回報格式

commit hash；改了哪些檔案；兩套測試指令與通過數量；改過的既有測試清單；沒做的與原因；發現的矛盾；375px 檢查結果。
