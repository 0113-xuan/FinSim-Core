# FinSim-Core

FinSim-Core is an **AI-assisted personal life-decision simulation and financial-risk analysis platform** for a graduation project.

The product is not a generic financial chatbot. The deterministic backend engine is always responsible for cash-flow, loan, FSI, Monte Carlo, comparison, and optimization calculations. AI is used only to help users parse natural-language scenarios, categorize expenses, and explain backend-generated results.

## Features

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
  - negative-balance and bankruptcy probabilities
  - high-risk month distribution
  - emergency-fund shortfall
  - sample paths
  - deterministic seed support
- Scenario comparison and bounded optimization
- Backend-only AI provider abstraction with deterministic fallback
- AI endpoints:
  - `POST /ai/parse-scenario`
  - `POST /ai/categorize-expenses`
  - `POST /ai/generate-report`
- Frontend demo mode without login; optional JWT-protected profile endpoints remain available for future auth work
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
- `JWT_SECRET`
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
GEMINI_MODEL=gemini-flash-lite-latest
```

API key 僅能放在後端環境變數或未追蹤的 `.env`，不可寫入
`.env.example`、前端程式或日誌。
`AI_ENABLED` 為可選的停用開關；未設定時會依選定 provider 的 key
自動啟用，明確設為 `false` 時停用。

Do not commit `.env` or real secrets.

## Supabase Schema

The local app can run without Supabase. Required production table definitions and RLS guidance are documented in:

```text
docs/supabase_schema.sql
```

For production, create the tables in Supabase and enable ownership-based RLS policies for every user-owned table.

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

- FSI calculations
- Loan calculation
- Basic simulation
- Categorized expenses
- Seasonal/inflation behavior
- Random shocks and seed reproducibility
- Monte Carlo percentiles
- AI fallback validation
- Optimization
- Important API endpoints
- Authentication protection

## Security Notes

- Passwords are hashed with bcrypt.
- The current frontend intentionally skips login for graduation-project demo flow.
- JWT tokens remain available for optional protected profile endpoints.
- AI keys are read only by the backend.
- CORS origins are configured by environment variable.
- Supabase service-role keys must never be exposed to frontend code.
- Production Supabase deployments should use Auth + ownership-based RLS.

## Known Limitations

- Local authentication uses an in-memory store for graduation-demo convenience. Restarting the server clears local users.
- Supabase persistence schema is documented, but the local app does not apply migrations automatically.
- The AI provider layer supports OpenAI-style chat completions first; when unavailable, deterministic fallback is used.
- The frontend intentionally keeps parameter editing compact rather than implementing every possible CRUD screen.

## Troubleshooting

- If `email-validator` is missing, run `pip install -r requirements.txt`.
- If AI endpoints return fallback warnings, check `AI_ENABLED=true` and `AI_API_KEY`.
- If protected profile endpoints return `401`, login or register first and pass the returned bearer token.
- If Supabase REST access fails in production, verify table grants, RLS policies, and Data API exposure settings.
