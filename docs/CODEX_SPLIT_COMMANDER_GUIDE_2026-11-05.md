# 指揮官手冊：Claude 指揮、Codex 分前端／後端寫程式

日期：2026-11-05。功能凍結 11/15，口試 11/19。

## 1. 角色

| 角色 | 做什麼 | 不做什麼 |
| --- | --- | --- |
| **Claude（指揮官）** | 決定做什麼、拆任務、寫 API 契約、寫兩份任務說明、審查 diff、跑測試與截圖驗收、整合兩個分支、寫審查報告 | 不替 Codex 寫大段實作（小修正除外） |
| **Codex 後端** | 只改後端檔案，照契約實作並寫 Python 測試 | 不碰 `static/`、不改契約、不做產品決策 |
| **Codex 前端** | 只改前端檔案，照契約實作並寫 node／瀏覽器測試 | 不碰 `app/`、`main.py`、`data/`、不改契約、不做產品決策 |

Codex 遇到任何「契約沒寫」「文案沒寫」「規則互相矛盾」的地方：**不要自己選，寫進回報**，由 Claude 決定。

## 2. 檔案擁有權（兩邊不能碰同一個檔案，合併才不會衝突）

| 區域 | 擁有者 |
| --- | --- |
| `app/**`、`main.py`、`data/**`、`scripts/**`、`requirements.txt` | 後端 |
| `tests/*.py`、`tests/conftest.py`、`tests/fixtures/**` | 後端 |
| `docs/supabase/*.sql`（只寫成檔案，由使用者執行） | 後端 |
| `static/**`（除下列舊頁面） | 前端 |
| `tests/*.js`、`tests/browser/**` | 前端 |
| `static/index.html`、`static/vehicle.html`、`static/car-needs.html` | **誰都不改** |
| `docs/**`（任務說明、契約、報告）、`PRODUCT.md`、`README.md`、`.env*` | 只有 Claude |

唯一的交會處：`main.py` 用 `StaticFiles` 提供 `static/`；`tests/test_knowledge_base.py` 等少數 Python 測試會讀 `static/`。所以**兩邊每次 commit 前都要跑完整的兩套測試**。

## 3. 工作流程（每個功能都照這個走）

1. **Claude 寫契約**：`docs/contracts/<功能>_<日期>.md`，包含端點、請求／回應 JSON、錯誤碼、降級狀態、範例 fixture。這是兩邊唯一的共同依據。
2. **Claude 寫兩份任務**：`docs/CODEX_TASK_<功能>_BE_<日期>.md`、`..._FE_<日期>.md`，格式見第 6 節。
3. **兩邊並行**：
   - 後端分支 `feat/<功能>-be`、前端分支 `feat/<功能>-fe`，**從同一個 commit 開出去**。
   - 後端用 pytest 對著契約驗證；前端用契約裡的 fixture JSON 先做出畫面，不必等後端。
4. **Claude 分別審查**（`git diff`、兩套測試、截圖），各自寫審查報告到 `docs/`。
5. **整合**：先合後端、再合前端到整合分支，跑兩套測試加 Playwright 全流程，再跑真的 Gemini 一次。
6. **契約有誤**：不改程式去遷就，回到 Claude 修契約，兩邊同步更新。

## 4. 現在要先處理的事（開新分支前）

目前在 `feat/ai-plan-qa`，**工作區有 11 個前端檔案尚未 commit**（`static/event-picker.js`、`explanation-model.js`、`plan-page.js`、`plan.html`、`results-model.js`、`shell.css`、`shell.js`，以及 4 個 `tests/*.js`），另有 `PRODUCT.md`、`.impeccable/` 未追蹤。

從有未提交修改的狀態開新分支，修改會被帶走。所以先：

1. 審查這 11 個檔案，通過就 commit（只 `git add` 這些檔案）。
2. 再從乾淨的 HEAD 開 `-be`／`-fe` 兩個分支。

這個分支已堆在 main 之上 18 個 commit，合併風險已經偏高；11/15 前建議審查通過一個就合併一個。

## 5. 共同的紅線（兩份任務說明都要抄進去）

- 專案原則：**Python 負責計算，AI 只負責解釋**；AI 不產生任何數字。
- 不 push、不 `git add .`、不讀或輸出 `.env` 與任何 key；前端只能用 Supabase **anon key**，絕不使用 service_role。
- 不動資料庫：需要改表就寫 SQL 檔，由使用者執行。資料表只有 v2 四張：`profiles`、`debts`、`plans`、`plan_events`；不提舊表（users、life_events、simulation_sessions）。
- commit 前：`python -m pytest -q` 與 `node --test tests/*.js` 全過。目前基準：pytest 672 以上、node 192 以上（以最近一次 Claude 審查為準）。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 測試不可呼叫真的 AI，一律用 `MockAIProvider`。
- 介面文字：繁體中文、白話、不用「Monte Carlo」「亂數種子」「後端預設」這類工程詞（見 `PRODUCT.md`）。
- 不 commit `futurewallet-flow.html` 與 `docs/` 底下未追蹤的報告。

## 6. 任務說明模板（Claude 每次照這個寫）

```
# Codex 任務（後端／前端）：<功能>
日期、分支名稱、完成期限
## 背景（2～4 句：為什麼做）
## 契約（連到 docs/contracts/…，不要複製貼上第二份）
## 你可以改的檔案／不可以改的檔案
## 要做的事（編號，每項寫清楚「完成的樣子」）
## 必要的測試（逐條列出）
## 不在範圍（明確寫）
## 回報格式（commit hash、改了哪些檔案、測試指令與數量、沒做的與原因、發現的矛盾）
```

## 7. 審查清單（Claude 用）

- `git diff --stat`：有沒有改到不屬於這一邊的檔案？有就退回。
- 兩套測試數量沒有減少（不得刪測試來讓它通過）。
- 回應欄位名稱、型別、列舉值與契約**逐項對照**。
- 後端：既有端點行為沒變；log 沒有問題內容、事實內容、key；錯誤訊息是繁中。
- 前端：沒有 `innerHTML` 插入 AI 或使用者文字；375px 無水平捲動；錯誤與狀態在使用者看得到的位置。
- 審查完寫報告到 `docs/<主題>_REVIEW_<日期>.md`（繁中、自成一份、可直接貼給 ChatGPT）。

## 8. 目前專案的兩邊現況（供指揮參考）

**後端端點（已存在，行為不可改）**：`/simulate`、`/monte-carlo`、`/compare`、`/planner/vehicle-events`、`/planner/parking`、`/planner/vehicle-fees`、`/regions`、`/occupations`、`/salary-reference`、`/decisions/vehicle*`、`/ai/plan-explanation`、`/ai/plan-qa`、`/config/public`。

**前端頁面**：`login`、`onboarding`、`dashboard`、`plan`、`profile`（新流程）；`index`、`vehicle`、`car-needs`（舊，不改）。前端直接用 anon key 讀寫 Supabase 四張表（見 `static/shell.js`），計算與 AI 才打後端。

**還在分支上、未合併 main**：`feat/ai-plan-explanation`、`event-template-picker`、`vehicle-insurance-tax`、`location-parking-occupation`、`frontend-upgrade`、`ai-plan-qa`（堆疊）。

**使用者待辦（不是 Codex 的事）**：Render 環境變數、Supabase Site URL、執行 `docs/supabase/04_profiles_location_occupation.sql`、真的 Gemini 測試、TDX 帳號。
