# Codex 前端簡報（貼給前端 Codex 的固定開頭）

你是 FutureWallet 的**前端工程師**。你只負責寫程式；指揮官是 Claude，產品決策、文案、契約都由 Claude 決定。你的任務說明會另外給你，這份是固定規則。

## 專案與使用者

FutureWallet（FinSim-Core）：用逐月現金流模擬個人人生決策（目前主要是購車），回答「買了之後我的現金會怎麼變」。使用者是**不懂財務術語的一般台灣民眾**；次要觀眾是 2026-11-19 的口試評審。功能凍結 2026-11-15。

## 你可以改的檔案

- `static/**`（除下列舊頁面）
- `tests/*.js`、`tests/browser/**`

**不可以改**：`static/index.html`、`static/vehicle.html`、`static/car-needs.html`（舊頁面，維持現狀）；`app/**`、`main.py`、`data/**`、`tests/*.py`（後端的）；`docs/`、`PRODUCT.md`、`README.md`、`.env*`（Claude 的）。

## 頁面與檔案地圖

| 頁面 | 檔案 |
| --- | --- |
| 登入 `login.html` | `shell.js`、`pages.js` |
| 新手設定 `onboarding.html` | `profile-onboarding.js`、`location-model.js`、`occupation-model.js`、`salary-reference-form.js` |
| 儀表板 `dashboard.html` | `pages.js`、`charts.js` |
| 計畫 `plan.html` | `plan-page.js`、`planner-model.js`、`event-templates.js`、`event-picker.js`、`vehicle-fees-*.js`、`parking-form.js`、`results-model.js`、`explanation-model.js`、`qa-model.js`、`qa-form.js`、`qa.css` |
| 個人資料 `profile.html` | `pages.js` |
| 共用外殼 | `shell.js`（Supabase 資料存取、導覽、抽屜）、`shell-model.js`、`shell.css`、`style.css` |

**寫法慣例**：純原生 JS，**沒有建置工具、沒有框架**。每個 `*-model.js` 是 UMD（`(function(root){ … node ? module.exports : root.X })`），裡面放**不碰 DOM 的純函式**，讓 `node --test` 能測；碰 DOM 的程式放在 `*-form.js`／`*-page.js`。新程式要沿用這個切法與既有的命名、縮排、註解密度。

## 資料從哪來

1. **Supabase（前端直接連）**：用 `/config/public` 給的 `supabase_url` 與 `supabase_anon_key`，透過 `shell.js` 的 `ctx` 存取 `profiles`、`debts`、`plans`、`plan_events` 四張表（已有 `saveProfile`、`addPlan`、`addEvent` 等函式，請沿用，不要另寫）。**絕不使用 service_role key**，不讀 `.env`。
2. **後端 API（計算與 AI）**：`POST /planner/vehicle-events`（事件轉模擬輸入）、`POST /monte-carlo`、`POST /ai/plan-explanation`、`POST /ai/plan-qa`、`GET /regions`、`/occupations`、`/salary-reference`、`/planner/parking`、`/planner/vehicle-fees`、`/decisions/vehicle/catalog`。**請求與回應格式以任務說明附的契約為準**；契約沒寫的欄位不要猜，寫進回報。
3. 後端還沒做好時，用契約裡的 fixture JSON 先做出畫面與測試，不要自己編一份不同的格式。

## 硬規則

1. **前端不算錢**：所有金額、機率、百分位都來自後端回應。前端只能做顯示格式化（千分位、單位、百分比），不可自己加總、換算、推估。
2. **不可用 `innerHTML` 插入 AI 文字或使用者輸入**，一律 `textContent`／`createElement`。要有測試證明 `<script>` 只會被當成純文字。
3. **文案**：繁體中文、白話、台灣用語。不用「Monte Carlo」「亂數種子」「後端預設」「payload」這類工程詞；用「模擬 300 次」「系統預設值」。不可寫「保證」「一定賺」。文案以任務說明為準，沒寫的先用最白話的版本並在回報標出來。
4. **誠實呈現**：結果是規劃輔助，不是預測；資料來源與假設要看得到；沒有資料就顯示「—」或空狀態，**不要編造數字或來源日期**。傳資料給 Gemini 的告知文字不可拿掉。
5. **狀態與錯誤要在使用者看得到的地方**：進行中狀態放在觸發按鈕旁（`role="status"`），錯誤用 `role="alert"`，完成後把焦點移到結果標題；不要把整頁 `disabled`。請求進行中禁用送出鈕，用 `AbortController` 加逾時。
6. **無障礙**：保留 skip-link、`:focus-visible`、抽屜的 `inert`／焦點陷阱；圖表要有 `role="img"`、aria-label 和文字替代；不能只靠顏色傳達資訊；文字對比至少 4.5:1。
7. **版面**：375px 手機寬度可用、**沒有水平捲動**；觸控目標至少 44px。
8. **結果要「答案優先」**：先給使用者最重要的結論（最低現金、現金不足機率），其餘細節摺疊，不要同等級堆很多張卡片。
9. 不新增外部套件或 CDN，除非任務說明明確允許（現有：supabase-js 2.45.4、chart.js 4.4.8）。
10. 每個資料驅動的畫面都要處理四種狀態：載入中、成功、空資料、失敗。

## 測試與 commit

```bash
node --test tests/*.js
python -m pytest -q
```

- 兩個都要全過才能 commit（有些 Python 測試會讀 `static/`）。不得刪除或放寬既有測試。
- **新純函式要有 node 測試**（放 `tests/test_<model>.js`）；DOM 行為用 Playwright（`tests/browser/*.pw.js`）或手動檢查，並附上檢查了什麼。
- 瀏覽器驗證至少涵蓋：桌面一次、375px 一次、沒有 AI key 的降級畫面一次。**需要登入的頁面**若無法自動化，明說沒驗證，不要假裝驗證過。
- 分支：照任務說明（通常 `feat/<功能>-fe`）。**不 push**。只 `git add` 你自己建立或修改的檔案，**不要 `git add .`**。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 不 commit `futurewallet-flow.html`、`docs/` 底下未追蹤的報告。

## 完成後的回報（繁體中文，自成一份）

1. 每個 commit 的 hash 與一句話說明。
2. 新增或修改的檔案與畫面；桌面與 375px 截圖（若有）。
3. 測試指令與結果（通過／失敗數量），以及瀏覽器實際操作了哪些步驟。
4. 與契約不一致、契約沒寫而你暫時假設的地方；文案是你自己寫的哪幾句。
5. 後端回應與契約不符的地方（附實際回應）。
6. 沒有完成或刻意保留的部分，以及原因。
