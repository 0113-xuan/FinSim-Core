# Codex 任務（前端）：意外風險

日期：2026-11-10。分支 `feat/life-shocks-fe`（從 `feat/life-shocks` 的 HEAD 開出，與後端同一個 commit）。期限：11/12。

## 背景

計畫頁的模擬結果目前不會告訴使用者「遇到意外時撐不撐得住」。後端另一份任務提供 `POST /monte-carlo/life-shocks`，前端加一個開關與一張並排比較卡片。

## 契約

`docs/contracts/life_shocks_2026-11-10.md`（唯一依據）。後端未完成時，用契約第 4 節的範例 JSON 當 fixture 先做畫面與測試。

## 你可以改的檔案

`static/plan.html`、`static/plan-page.js`、`static/results-model.js`、`static/shell.css`，以及需要的新 `static/*.js`、`tests/*.js`、`tests/browser/**`。

不可以改：`app/**`、`main.py`、`data/**`、`tests/*.py`、`docs/**`、`static/index.html`、`static/vehicle.html`、`static/car-needs.html`。

## 要做的事

1. `plan.html` 模擬表單加「加入意外風險」開關，預設關，不存進計畫。完成的樣子：關閉時畫面與現在完全一樣，且不呼叫新端點。
2. 開關開啟時，照原流程算完後，用同一份請求（`seed: 42`、`simulations: 300`）呼叫 `POST /monte-carlo/life-shocks`（`plan-page.js` 約 357 行附近）。
3. 結果區加「意外風險」卡片：並排「沒有意外」「有意外」兩欄，各顯示現金不足機率、期末淨資產 p5 到 p95 與中位數；「沒有意外」用原本 `/monte-carlo` 的回應，「有意外」用新端點的回應。完成的樣子：兩欄一眼能比；兩欄數字都來自回應，前端沒有寫死機率或金額。
4. 卡片下方列出 `assumptions` 三筆（名稱、`chance_in_horizon`、金額範圍或收入中斷月數）與 `disclaimer`（原樣顯示，不改字）。
5. 降級：新端點失敗時原結果照常，卡片位置顯示錯誤與重試；修改表單任何欄位時卡片一併清掉（沿用 `invalidate`）。
6. 把顯示用的整理邏輯放進 `results-model.js`（純函式，可用 node 測），不要塞在 `plan-page.js`。

## 必要的測試

契約第 6 節「前端」6 條。node 測試涵蓋 1 到 5；第 6 條 375px 無水平捲動請在 `tests/browser/` 補，截圖由 Claude 驗收。

## 不在範圍

契約第 7 節全部。不做使用者自訂機率與金額。

## 紅線

- 介面文字繁體中文、白話：不出現「Monte Carlo」「亂數種子」「random_shocks」，不出現「癌症」等診斷字眼（見 `PRODUCT.md`）。
- 不用 `innerHTML` 插入回應文字；不使用 service_role key，只用 anon key。
- 不 push、不 `git add .`（只 add 自己改的檔案）、不讀或輸出 `.env`。
- commit 前 `python -m pytest -q` 與 `node --test tests/*.js` 全過。基準：pytest 974 passed、node 273 pass。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 契約沒寫的文案或規則不要自己選，寫進回報。

## 回報格式

commit hash；改了哪些檔案；兩套測試指令與通過數量；沒做的與原因；發現的矛盾；375px 檢查結果。
