from fastapi import FastAPI, HTTPException
from typing import Dict, Any
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from supabase import create_client

from app.schemas import (
    SimulationRequest,
    MonteCarloRequest,
    CompareRequest,
    UserCreate,
    FinanceEvent,
)
from app.core.simulation import simulate_finance
from app.core.monte_carlo import run_monte_carlo
from app.core.advisor import compare_options, generate_advice


SUPABASE_URL = "https://tpgtuairychavuzfgifc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwZ3R1YWlyeWNoYXZ1emZnaWZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0NjY2ODQsImV4cCI6MjA5MTA0MjY4NH0.W-BQ7HijWcGnqRlQQSRyaT4GDdLCKMaYYBtL7LFFz-I"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. 初始化 FastAPI
app = FastAPI(title="AI 財務模擬系統 API", version="2.0.0")

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# 基本 API
# =========================

@app.get("/api")
def home():
    return {
        "message": "後端系統運作中",
        "docs": "/docs",
        "version": "2.0.0"
    }


# =========================
# 使用者 / 基本資料 API
# =========================

@app.post("/user/create")
async def create_user(user: UserCreate):
    try:
        data = {
            "name": user.username,
            "email": f"{user.username}@test.com"
        }

        response = supabase.table("users").insert(data).execute()

        return {
            "status": "success",
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/event/add")
async def add_event(event: FinanceEvent):
    try:
        # 先保留簡單版本，之後可改成真的寫進 Supabase
        return {
            "status": "event_added",
            "event": event.model_dump() if hasattr(event, "model_dump") else event.dict(),
            "impact": "negative" if event.amount < 0 else "positive"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/result/{user_id}")
async def get_result(user_id: str):
    try:
        # 先保留假資料版本，之後再改成真的查 Supabase
        return {
            "user_id": user_id,
            "summary": "你的財務狀況穩定",
            "charts_data": [100, 120, 150, 180]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# AI 模組 API
# =========================

@app.post("/simulate")
async def simulate_api(req: SimulationRequest):
    """
    使用你真正的財務模擬引擎
    """
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()

        result = simulate_finance(
            profile=data["profile"],
            months=data["months"],
            events=data.get("events", []),
            loans=data.get("loans", [])
        )

        # 若前端有傳 user_id，可再考慮存資料
        user_id = data.get("user_id")
        session_id = None

        if user_id:
            try:
                session = supabase.table("simulation_sessions").insert({
                    "user_id": user_id,
                    "simulation_name": "AI財務模擬"
                }).execute()

                if session.data:
                    session_id = session.data[0]["id"]

                    summary = result["summary"]
                    supabase.table("simulation_results").insert({
                        "session_id": session_id,
                        "simulation_year": int(data["months"] / 12),
                        "projected_income": data["profile"]["salary"],
                        "projected_expense": (
                            data["profile"]["fixed_expense"]
                            + data["profile"]["variable_expense"]
                        ),
                        "projected_savings": summary["final_balance"],
                        "financial_stress_score": summary["max_fsi"]
                    }).execute()
            except Exception as db_error:
                # DB 存失敗不影響核心模擬
                return {
                    "result": result,
                    "warning": f"模擬成功，但資料庫儲存失敗: {str(db_error)}"
                }

        return {
            "result": result,
            "session_id": session_id
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/monte-carlo")
async def monte_carlo_api(req: MonteCarloRequest):
    """
    使用你真正的 Monte Carlo 模組
    """
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()

        result = run_monte_carlo(
            profile=data["profile"],
            base_events=data.get("events", []),
            loans=data.get("loans", []),
            months=data["months"],
            simulations=data["simulations"]
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/compare")
async def compare_api(req: CompareRequest):
    """
    比較多個方案，並回傳 AI 建議
    """
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()

        compare_result = compare_options(
            profile=data["profile"],
            options=data["options"],
            months=data["months"],
            mc_runs=data["mc_runs"]
        )

        advice = generate_advice(compare_result)

        return {
            "compare_result": compare_result,
            "advice": advice
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ai/advice")
async def get_ai_advice(req: CompareRequest):
    """
    直接輸入 compare 所需資料，輸出建議
    """
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()

        compare_result = compare_options(
            profile=data["profile"],
            options=data["options"],
            months=data["months"],
            mc_runs=data["mc_runs"]
        )

        advice = generate_advice(compare_result)

        return advice

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# 靜態前端
# =========================

app.mount("/", StaticFiles(directory="static", html=True), name="static")


# =========================
# 啟動
# =========================

if __name__ == "__main__":
    print("=== AI 財務模擬系統後端已啟動 ===")
    print("Swagger 文件：http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
