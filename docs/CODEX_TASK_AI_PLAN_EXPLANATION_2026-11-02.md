# Codex 任務：計畫頁的 AI 白話解釋

日期：2026-11-02。完成後由 Claude 審查。

## 背景

- 教授的意見是「可信度不夠、不夠個人化、希望多一點 AI」。專題原則是 **Python 負責計算，LLM 只負責解釋**。
- 計畫頁跑完模擬後，畫面上有十幾個指標（最低現金、現金不足機率、p5／p50／p95……），一般使用者看不懂這些數字代表什麼、該注意什麼。
- 這次在計畫頁加一個「用白話解釋結果」按鈕，讓 AI 根據**後端算好的數字**寫一段說明。
- **最重要的規則：AI 寫的文字裡不能出現它自己寫的數字。**所有數字都由後端代入，這樣就不會出現 AI 算錯或捏造數字的情況。這也是口試時要展示的重點。

## 工作規則

- 從 `main` 建立新分支 `feat/ai-plan-explanation`。**不要 push**。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- **測試不可以呼叫真的 AI**，一律用 `app/services/mock_ai_provider.py` 的 `MockAIProvider`。
- 沿用既有的 `get_ai_provider()`、`generate_structured()`、`rate_limit_ai()`，不要另外寫一套呼叫 Gemini 的程式。
- `/simulate`、`/monte-carlo`、`/planner/vehicle-events` 與所有 `/decisions/vehicle*` 的計算結果不可以改變。

## 任務 A：後端整理「事實表」

新增 `app/services/plan_explanation.py`，裡面有一個純函式 `build_facts(...)`，把模擬結果整理成一份事實表。

**怎麼算**

- 後端自己重新計算，不接受前端傳來的結果數字。
- 用前端送來的模擬請求（和計畫頁送給 `/simulate` 的內容相同），呼叫和 `/simulate`、`/monte-carlo` 一樣的計算。Monte Carlo 用 `simulations=300`、`seed=42`，和計畫頁一致，這樣解釋裡的數字會和畫面上的指標完全相同。

**事實表的格式**

每一筆事實有：

- `id`：英文小寫加底線，例如 `minimum_cash`。
- `label`：中文名稱，例如「最低現金」。
- `value`：已經格式化好的文字。金額用 `NT$1,234,567`，不帶小數；月份用 `YYYY-MM`；機率用百分比；月數取到小數一位。
- `raw`：原始數值。

**至少要有這些事實**（沒有資料的就不放）

| id | 內容 |
| --- | --- |
| `monthly_income`、`monthly_expense`、`monthly_debt_payment`、`monthly_investment`、`monthly_surplus` | 目前每月收入、支出（固定＋變動）、既有貸款月付、每月投資，以及四者相減後的每月結餘 |
| `minimum_cash`、`minimum_cash_period` | 最低現金和發生月份 |
| `first_negative_period` | 第一次現金小於 0 的月份；沒有就不放，另外加一筆布林 `never_negative` |
| `minimum_emergency_months`、`emergency_target_months` | 最低緊急預備金月數，以及使用者設定的目標月數 |
| `ending_cash`、`ending_net_worth` | 確定性模擬的期末現金和期末淨資產 |
| `shortfall_probability` | Monte Carlo 的現金不足機率 |
| `net_worth_p5`、`net_worth_p50`、`net_worth_p95`、`real_net_worth_p50` | 期末淨資產百分位數，以及用今日購買力計算的 p50 |
| `months`、`start_period`、`end_period` | 模擬期間 |
| `event_<n>_name`、`event_<n>_period`、`event_<n>_summary` | 每個事件的名稱、月份和金額摘要；摘要文字由前端送來，和計畫頁時間軸相同 |
| `vehicle_<n>_monthly_payment`、`vehicle_<n>_one_time_cash`、`vehicle_<n>_total_interest` | 有購車事件時，從 `/planner/vehicle-events` 的換算結果取得 |
| `largest_drop_period`、`largest_drop_amount` | 現金單月下降最多的月份和金額。可以參考 `/simulate` 回傳的 `transparency`，看能不能指出是哪個事件造成的；指不出來就不放 |

## 任務 B：AI 只能用「代號」寫數字

**AI 回傳的格式**（用 `generate_structured` 的 Pydantic schema）

```json
{
  "headline": "一句話總結",
  "paragraphs": ["2 到 4 段說明"],
  "watch_points": ["0 到 3 個要注意的地方"],
  "suggestions": ["0 到 3 個可以考慮的調整"]
}
```

**寫數字的規則**

- 文字中要提到數字時，一律寫成 `{fact_id}`，例如「最低現金會在 {minimum_cash_period} 降到 {minimum_cash}」。
- 後端收到後要做以下驗證：
  1. 文字中不可以出現任何阿拉伯數字（半形 `0-9` 和全形 `０-９`）。
  2. 每個 `{...}` 都必須是事實表裡存在的 id。
  3. 每段字數有上限：`headline` 60 字，其他每段 200 字。
- 驗證不通過時重試一次。再失敗就改用任務 C 的範本說明，**不可以把驗證不通過的文字顯示給使用者**。
- 驗證通過後，把每段文字拆成片段陣列回傳給前端，例如 `[{"text": "最低現金會在 "}, {"fact": "minimum_cash_period", "value": "2028-06", "label": "最低現金發生月份"}, ...]`。前端用這個陣列把數字加粗，並把 label 放進 `title`。

**提示詞**放在 `app/prompts/plan_explanation.md`，用既有的 `prompt_loader` 讀取。內容要包含：

- **讀者**：剛出社會的年輕人，沒有財金背景。用台灣常用的繁體中文，語氣平實，不要說教。
- **只能使用事實表裡的事實**，不可以自己計算、推估或加總任何數字；需要比較時用文字描述，例如「低於你設定的目標」。
- **事件**：提到計畫中的事件時，要說明它對現金的影響。
- **現金不足機率**：現金不足機率大於 0 時，一定要提到不確定性，並說明這是用台灣過去的通膨與股市資料抽樣得到的結果，不是預測。
- **建議**：只能是調整計畫的方向，例如延後某個事件、降低某類支出、提高預備金。**不可以推薦任何特定的投資商品、股票、基金或保險**，也不可以說「保證」「一定」。
- **最後一句**固定提醒：這是模擬結果，不是財務建議。

## 任務 C：沒有 AI 時的範本說明

- 寫一個純函式，只用事實表產生 headline、paragraphs、watch_points，用規則判斷，不用 AI。例如：
  - 最低緊急預備金月數低於目標時，寫「預備金在 {minimum_cash_period} 前後會低於你設定的目標」。
  - 現金不足機率大於 0 時，寫一句不確定性提醒。
  - 有購車事件時，寫購車當月的一次支出和每月車貸。
- 範本的輸出格式和 AI 相同，也走同一套片段拆分。
- **以下情況都使用範本**：
  - `AI_ENABLED` 沒開。
  - 沒有設定 key。
  - provider 錯誤或逾時。
  - 驗證連續兩次不通過。
- 回應中用 `source: "ai"` 或 `source: "template"` 標示說明的來源。`source` 是 `template` 時，另外帶 `fallback_reason`（`disabled`、`provider_error`、`invalid_output`）。

## 任務 D：API

新增 `POST /ai/plan-explanation`。

**請求**

```json
{
  "simulation": { "...": "和計畫頁送給 /simulate 的內容相同（含 assets、loans、events）" },
  "start_period": "2026-11",
  "events": [{"name": "買車", "type": "vehicle_purchase", "start_period": "2027-03", "summary": "車價 NT$849,000，貸款 60 期"}],
  "vehicles": [ "可省略；計畫頁已經呼叫過 /planner/vehicle-events 時，直接送它回傳的 vehicles" ],
  "emergency_target_months": 6
}
```

**回應**

```json
{
  "source": "ai",
  "fallback_reason": null,
  "model": "gemini-3.5-flash-lite",
  "headline": [ "片段陣列" ],
  "paragraphs": [[ "片段陣列" ]],
  "watch_points": [[ "片段陣列" ]],
  "suggestions": [[ "片段陣列" ]],
  "facts": [{"id": "minimum_cash", "label": "最低現金", "value": "NT$751,822"}],
  "disclaimer": "這段說明由 AI 根據上方的模擬數字撰寫，數字都來自模擬計算，不是 AI 自己算的。這是模擬結果，不是財務建議。"
}
```

`source` 是 `template` 時，`model` 為 `null`，`disclaimer` 的第一句改成「這段說明由系統依規則產生」。

**其他要求**

- 呼叫 `rate_limit_ai(request)`。
- **快取**：用 `simulation`、`events`、`vehicles`、`emergency_target_months` 排序後的 JSON 做 sha256，在記憶體快取最近 200 筆結果，同樣的請求不要重複呼叫 AI。範本結果不需要快取。
- **log**：可以記錄 provider 名稱、耗時、`source`、`fallback_reason`。不可以記錄提示詞內容、事實內容、事件名稱或任何 key。
- **送給 AI 的內容**：只有事實表的 `id`、`label`、`value`，加上事件名稱與摘要。不送 email、`user_id` 或任何帳號資料。

## 任務 E：計畫頁

- 「模擬結果」區塊最下方新增一個「AI 白話解釋」小節：
  - 一個「用白話解釋結果」按鈕。按鈕只有在模擬完成後才能按；結果被 `invalidate()` 清掉時，解釋也一起清掉。
  - 請求的 `simulation`、`vehicles` 直接沿用這次模擬時用的內容（`prepareSimulation` 的結果），`events` 的 `summary` 用 `ShellModel.eventSummary`。
  - 顯示順序：headline（粗體）→ paragraphs → 「要注意」清單 → 「可以考慮」清單 → disclaimer。
  - 數字片段用 `<strong title="label">value</strong>`。
  - `source` 是 `template` 時，在小節標題旁顯示「（系統範本）」，並依 `fallback_reason` 用一句話說明原因，例如「目前未啟用 AI，以下是系統依規則產生的說明」。
  - 按鈕下方用小字寫：「按下後，會把這次模擬的數字和事件名稱傳給 Google Gemini 產生說明。」
- 錯誤沿用 `ctx.perform` 顯示在畫面上。
- 把片段轉 DOM 的部分寫成純函式，放在 `shell-model.js` 或新的 `explanation-model.js`，給 node 測試用。
- **不可以用 `innerHTML` 插入 AI 文字**，一律用 `textContent`／`createElement`。

## 必要的測試

**Python**

- `build_facts`：
  - 用固定的輸入，確認 `minimum_cash`、`shortfall_probability`、`net_worth_p50` 的 `raw` 和直接呼叫 `/simulate`、`/monte-carlo`（`seed=42`、`simulations=300`）的結果完全相同。
  - 有購車事件和沒有購車事件時，事實表的內容都正確。
- 驗證規則：
  - 含半形數字、含全形數字、含不存在的 `{id}`、超過字數，這四種都會被拒絕。
  - 合法的輸入會正確拆成片段。
- 降級（fallback）：
  - provider 是 `None` 時回傳 `fallback_reason=disabled`。
  - provider 丟出 `AIProviderError` 時回傳 `provider_error`。
  - mock 連續兩次回傳含數字的文字時回傳 `invalid_output`，而且只呼叫了兩次。
- 快取：同一個請求呼叫兩次，mock provider 只被呼叫一次。
- 端點：用 `MockAIProvider` 跑一次，回應中所有 `value` 都能在 `facts` 裡找到。
- 現有測試不修改，全部通過。

**Node**

- 片段轉文字的函式：數字片段會變成 strong，`title` 是 label；文字片段如果含有 `<script>`，只會被當成純文字顯示。

**瀏覽器**

- 用 Playwright 或手動操作：計畫頁執行模擬 → 按「用白話解釋結果」。
- 本機沒有 AI key 時，應該顯示範本說明和「（系統範本）」。

## 不在本任務範圍

- RAG 和引用來源。
- 對話式問答。
- 儀表板上的解釋。
- 其他人生事件範本。
- 修改 `index.html`、`vehicle.html`、`car-needs.html`。
- 修改既有 `/ai/*` 端點。

發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. 新增、修改的 API 與檔案。
3. 一份範例：輸入的事實表，以及 mock 和範本兩種模式的輸出。
4. 測試指令與結果（通過數量、失敗數量）。
5. 估計一次真實 Gemini 呼叫的輸入與輸出 token 數。
6. 沒有完成或刻意保留的部分，以及原因。
