# FinSim-Core

FinSim-Core is an **AI-assisted personal life-decision simulation and financial-risk analysis platform** for a graduation project.

The product is not a generic financial chatbot. The deterministic backend engine is always responsible for cash-flow, loan, cash shortfall, Monte Carlo, comparison, and optimization calculations. AI is used only to help users parse natural-language scenarios, categorize expenses, and explain backend-generated results.

## FinSim 2.0 Vehicle Decision

The current decision workspace is `/vehicle.html`. It compares 60 months of
cash flow using the deterministic engine, without AI or legacy risk scoring.

- One-at-a-time sensitivity: income +/-10%, fuel/parking/insurance +/-20%,
  maintenance +/-30%, inflation +/-1 percentage point, vehicle price +/-10%.
- Save an evaluated option A, edit purchase conditions, evaluate option B,
  then compare on identical financial inputs, constraints, and observation dates.
- Existing debt details replace the aggregate payment and stop after the last
  remaining installment (counted from simulation month 1).
- Assumption records include effective/default values, units, provenance,
  source dates, and override status. Defaults are uncalibrated planning budgets,
  not market quotes. Missing external source dates remain null.

APIs: `POST /decisions/vehicle`, `POST /decisions/vehicle/sensitivity`,
`POST /decisions/vehicle/compare`, `POST /decisions/vehicle/what-if`,
`GET /decisions/vehicle/assumptions`.
Sensitivity starts with concrete input changes, before/after cash, and threshold
checks. Charts stay collapsed. Custom income, parking, and price changes use the
same engine; invalid adjusted amounts or financing terms have no result.
See [Sprint 2 definitions](docs/SPRINT2_IMPLEMENTATION.md).

## Existing Platform Features

- FastAPI backend with OpenAPI docs at `/docs`
- Backend-only deterministic financial simulation
- Quick variable-expense mode with automatic category splitting
- Advanced category expense model with:
  - baseline amount
  - monthly volatility
  - category inflation
  - income elasticity
  - 12 seasonal factors
  - optional min/max bounds
- Life-event effects for income, fixed expenses, variable categories, one-time amounts, and recurring amounts
- Loan amortization
- Configurable random financial shocks
- Monte Carlo simulation with:
  - average, median, min, max final balance
  - p5/p25/p50/p75/p95 percentiles
  - cash shortfall probability (any month-end cash below zero)
  - emergency-fund shortfall
  - sample paths
  - deterministic seed support
- Scenario comparison and bounded optimization
- Backend-only AI provider abstraction with deterministic fallback
- AI endpoints:
  - `POST /ai/parse-scenario`
  - `POST /ai/categorize-expenses`
  - `POST /ai/generate-report`
- Frontend demo mode without login
- Polished responsive dashboard frontend in `static/`
- Tests that do not require real AI keys

## Local Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Open:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

## Environment Variables

See `.env.example`.

Important variables:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `CORS_ORIGINS`
- `AI_PROVIDER`
- `AI_ENABLED`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_TIMEOUT_SECONDS`
- `AI_MAX_RETRIES`

使用 Gemini 結構化擷取時：

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=your-secret
GEMINI_MODEL=gemini-3.5-flash-lite
```

AI provider 的金鑰僅能放在後端環境變數或未追蹤的 `.env`，不可寫入
`.env.example`、前端程式或日誌。
`AI_ENABLED` 為可選的停用開關；未設定時會依選定 provider 的 key
自動啟用，明確設為 `false` 時停用。

測試分支的舊 `gemini-flash-lite-latest` 設定會相容解析為固定的
`gemini-3.5-flash-lite`，避免模型版本漂移；不改寫你的 `.env`。
組員啟動與桌面驗收請參閱 [P4 測試版說明](docs/P4_TEAM_TEST_GUIDE.md)。

Do not commit `.env` or real secrets.

## Supabase Planner

開啟 `http://localhost:8000/planner.html`，使用 Supabase 的電子郵件與密碼註冊、登入，
並儲存自己的財務資料、現有貸款、計畫與事件。此頁由前端的固定版本 supabase-js
直接操作 Supabase Auth 與四張 v2 表；後端只提供公開設定及財務計算，不連線 Supabase。
原有 `index.html`、`vehicle.html`、`car-needs.html` 的示範流程維持獨立。

啟動前，請自行在未追蹤的 `.env` 設定 `SUPABASE_URL` 與 `SUPABASE_ANON_KEY`。
只能使用專案的公開 anon key，不可填入 service-role 或 secret key。
`GET /config/public` 只回傳這兩項公開設定與 `configured`；任一項缺漏時，
兩個值都回傳空字串，planner 顯示「尚未設定 Supabase」並停用登入。
修改設定後須重新啟動後端，勿把實際值寫入程式碼、報告或日誌。

Supabase 後台需啟用 Email 登入／註冊。若啟用確認信，註冊後先到信箱確認，
再回此頁登入。在 Auth 的 URL Configuration 中將 Site URL 設為實際使用的
planner 網址，例如 `http://localhost:8000/planner.html`；Redirect URLs 也應包含
實際使用的位址（使用 `127.0.0.1`、其他連接埠或部署網址時需分別設定）。

此頁需要已存在的 `profiles`、`debts`、`plans`、`plan_events`，以及允許登入者
存取自己資料的 RLS policy 與表權限。結構參考：

```text
docs/supabase_schema_v2.sql
```

應用程式不會自動執行此 SQL 或更動資料庫。既有專案已建立 v2 表時，不要重複執行。
每月投資金額目前只視為現金支出，投資市值不納入模擬；購車事件暫不提供新增。
模擬只送出所選計畫與已儲存的資料，調薪率留空時跟隨有效通膨率。

## Core API Examples

### Run Simulation

```http
POST /simulate
Content-Type: application/json
```

```json
{
  "profile": {
    "salary": 60000,
    "fixed_expense": 20000,
    "variable_expense": 15000,
    "balance": 1000000,
    "target_emergency_months": 6
  },
  "months": 60,
  "seed": 42
}
```

### Monte Carlo

```json
{
  "profile": {
    "salary": 60000,
    "fixed_expense": 20000,
    "variable_expense": 15000,
    "balance": 1000000
  },
  "months": 60,
  "simulations": 300,
  "sample_paths": 8,
  "seed": 42
}
```

### Parse Scenario

```json
{
  "text": "I plan to move to Taipei in six months, join a gym, and travel to Japan at the end of the year.",
  "months": 60
}
```

## Testing

```powershell
pytest
```

Tests cover:

- Cash metrics and cash shortfall probability
- Loan calculation
- Basic simulation
- Categorized expenses
- Seasonal/inflation behavior
- Random shocks and seed reproducibility
- Monte Carlo percentiles
- AI fallback validation
- Optimization
- Important API endpoints
- Public configuration boundaries and planner ownership filters

## Security Notes

- Planner sign-in and session handling use Supabase Auth in the browser.
- Planner reads and writes are scoped to the signed-in user and protected by database RLS.
- AI keys are read only by the backend.
- CORS origins are configured by environment variable.
- Supabase service-role keys must never be exposed to frontend code.
- The legacy demo pages and their AI drafts remain separate from planner persistence.

## Known Limitations

- Supabase Email settings, confirmation redirects, table permissions and RLS must be configured separately; the app does not apply migrations automatically.
- The AI provider layer supports OpenAI-style chat completions first; when unavailable, deterministic fallback is used.
- The frontend intentionally keeps parameter editing compact rather than implementing every possible CRUD screen.

## Troubleshooting

- If AI endpoints return fallback warnings, check `AI_ENABLED=true` and `AI_API_KEY`.
- If planner shows that Supabase is unconfigured, set both public configuration variables and restart the backend.
- If registration requires confirmation, follow the email link and verify the configured Site URL before signing in.
- If Supabase REST access fails in production, verify table grants, RLS policies, and Data API exposure settings.
