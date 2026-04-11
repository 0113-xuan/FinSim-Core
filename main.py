from fastapi import FastAPI, HTTPException
from typing import Optional
import uvicorn
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from supabase import create_client
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

from app.schemas import (
    SimulationRequest,
    MonteCarloRequest,
    CompareRequest,
    FinanceEvent,
)
from app.core.simulation import simulate_finance
from app.core.monte_carlo import run_monte_carlo
from app.core.advisor import compare_options, generate_advice


# =========================
# Supabase 連線
# =========================
SUPABASE_URL = "https://tpgtuairychavuzfgifc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwZ3R1YWlyeWNoYXZ1emZnaWZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0NjY2ODQsImV4cCI6MjA5MTA0MjY4NH0.W-BQ7HijWcGnqRlQQSRyaT4GDdLCKMaYYBtL7LFFz-I"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 密碼加密
# =========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =========================
# FastAPI 初始化
# =========================
app = FastAPI(title="AI 財務模擬系統 API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent


# =========================
# Pydantic Models
# =========================
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FinancialProfileCreate(BaseModel):
    user_id: str
    current_savings: int
    monthly_income: int
    has_loan: bool
    loan_amount: int = 0


# =========================
# 基本 API
# =========================
@app.get("/api/version")
def version():
    return {
        "app": "FinSim-Core",
        "version": "render-check-001"
    }
    
@app.get("/api")
def home():
    return {
        "message": "後端系統運作中",
        "docs": "/docs",
        "version": "3.0.0"
    }


# =========================
# 註冊 / 登入 API
# =========================
@app.post("/auth/register")
async def register_user(req: RegisterRequest):
    try:
        # 檢查 email 是否已存在
        existing = supabase.table("users").select("*").eq("email", req.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="此 Email 已被註冊")

        password_hash = pwd_context.hash(req.password)

        response = supabase.table("users").insert({
            "name": req.name,
            "email": req.email,
            "password_hash": password_hash
        }).execute()

        return {
            "status": "success",
            "message": "註冊成功",
            "data": response.data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"註冊失敗: {str(e)}")


@app.post("/auth/login")
async def login_user(req: LoginRequest):
    try:
        response = supabase.table("users").select("*").eq("email", req.email).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="查無此使用者")

        user = response.data[0]
        stored_hash = user.get("password_hash")

        if not stored_hash:
            raise HTTPException(status_code=500, detail="資料庫中沒有 password_hash 欄位或資料")

        if not pwd_context.verify(req.password, stored_hash):
            raise HTTPException(status_code=401, detail="密碼錯誤")

        return {
            "status": "success",
            "message": "登入成功",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登入失敗: {str(e)}")
        
@app.get("/api/version")
def version():
    return {
        "app": "FinSim-Core",
        "version": "render-check-001"
    }


# =========================
# 財務資料 API
# =========================
@app.post("/financial-profile/create")
async def create_financial_profile(profile: FinancialProfileCreate):
    try:
        response = supabase.table("financial_profiles").insert({
            "user_id": profile.user_id,
            "current_savings": profile.current_savings,
            "monthly_income": profile.monthly_income,
            "has_loan": profile.has_loan,
            "loan_amount": profile.loan_amount
        }).execute()

        return {
            "status": "success",
            "message": "財務資料已建立",
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"建立財務資料失敗: {str(e)}")


# =========================
# 事件 API
# =========================
@app.post("/event/add")
async def add_event(event: FinanceEvent):
    try:
        event_data = event.model_dump() if hasattr(event, "model_dump") else event.dict()

        response = supabase.table("life_events").insert({
            "user_id": event_data["user_id"],
            "event_type": event_data["event_type"],
            "decision": f"amount={event_data['amount']}"
        }).execute()

        return {
            "status": "event_added",
            "data": response.data,
            "impact": "negative" if event_data["amount"] < 0 else "positive"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增事件失敗: {str(e)}")


@app.get("/result/{user_id}")
async def get_result(user_id: str):
    try:
        sessions = supabase.table("simulation_sessions").select("*").eq("user_id", user_id).execute()

        if not sessions.data:
            return {
                "user_id": user_id,
                "summary": "尚無模擬資料",
                "charts_data": []
            }

        latest_session = sessions.data[-1]
        results = supabase.table("simulation_results").select("*").eq("session_id", latest_session["id"]).execute()

        if not results.data:
            return {
                "user_id": user_id,
                "summary": "尚無模擬結果",
                "charts_data": []
            }

        latest_result = results.data[-1]

        return {
            "user_id": user_id,
            "summary": "已成功取得最新模擬結果",
            "session": latest_session,
            "result": latest_result,
            "charts_data": [
                latest_result["projected_income"],
                latest_result["projected_expense"],
                latest_result["projected_savings"]
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查詢結果失敗: {str(e)}")


# =========================
# AI 模組 API
# =========================
@app.post("/simulate")
async def simulate_api(req: SimulationRequest):
    try:
        data = req.model_dump() if hasattr(req, "model_dump") else req.dict()

        result = simulate_finance(
            profile=data["profile"],
            months=data["months"],
            events=data.get("events", []),
            loans=data.get("loans", [])
        )

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
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")


# =========================
# 啟動
# =========================
if __name__ == "__main__":
    print("=== AI 財務模擬系統後端已啟動 ===")
    print("Swagger 文件：http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
