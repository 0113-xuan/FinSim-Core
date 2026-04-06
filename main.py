from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from supabase import create_client

SUPABASE_URL = "https://tpgtuairychavuzfgifc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwZ3R1YWlyeWNoYXZ1emZnaWZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0NjY2ODQsImV4cCI6MjA5MTA0MjY4NH0.W-BQ7HijWcGnqRlQQSRyaT4GDdLCKMaYYBtL7LFFz-I"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. 初始化 FastAPI
app = FastAPI(title="AI 財務模擬系統 API", version="1.0.0")

# 2. ⚠️ 關鍵修正：CORS 必須放在這裡！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 允許所有網址連線
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 定義資料模型 (Data Models)
class UserCreate(BaseModel):
    username: str
    age: int
    initial_savings: float

class FinanceEvent(BaseModel):
    user_id: str
    event_type: str  # 例如: "買車", "中樂透", "失業"
    amount: float

class SimulationRequest(BaseModel):
    user_id: str
    years: int = 10
    monthly_income: float
    monthly_expense: float
    initial_savings: float  # ⚠️ 關鍵修正：這裡必須加上，否則下面計算會報錯！

# 4. API 路由實作 (API Routes)

# 把原本的 "/" 改成 "/api"，把根目錄留給前端網頁
@app.get("/api")
def home():
    return {"message": "後端系統運作中", "docs": "/docs"}

# 建立使用者
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

# [POST] 執行模擬 (核心功能)
@app.post("/simulate")
async def simulate(request: SimulationRequest):
    try:
        future_savings = request.initial_savings + \
            (request.monthly_income - request.monthly_expense) * 12 * request.years

        # 先建立 session
        session = supabase.table("simulation_sessions").insert({
            "user_id": request.user_id,
            "simulation_name": "預設模擬"
        }).execute()

        session_id = session.data[0]["id"]

        # 存結果
        result = supabase.table("simulation_results").insert({
            "session_id": session_id,
            "simulation_year": request.years,
            "projected_income": request.monthly_income,
            "projected_expense": request.monthly_expense,
            "projected_savings": future_savings,
            "financial_stress_score": 35.0
        }).execute()

        return {
            "future_savings": future_savings,
            "session_id": session_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# [POST] 新增財務事件
@app.post("/event/add")
async def add_event(event: FinanceEvent):
    # TODO: 這裡要記錄事件並影響後續模擬
    return {"status": "event_added", "impact": "negative" if event.amount < 0 else "positive"}

# [GET] 獲取模擬結果
@app.get("/result/{user_id}")
async def get_result(user_id: str):
    return {
        "user_id": user_id,
        "summary": "你的財務狀況穩定",
        "charts_data": [100, 120, 150, 180] # 供 Chart.js 使用
    }

# [POST] 獲取 AI 建議
@app.post("/ai/advice")
async def get_ai_advice(user_id: str):
    # TODO: 這裡要串接組員 C 的 generate_advice()
    return {
        "user_id": user_id,
        "ai_suggestion": "根據 FSI 指數，建議您增加緊急預備金，並減少非必要開支。"
    }

# 5. ⚠️ 關鍵修正：掛載前端靜態網頁 (必須寫在所有 API 的最下面！)
# 這樣伺服器就會去 static 資料夾找組員 A 寫的 index.html
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# 6. 啟動伺服器
if __name__ == "__main__":
    print("=== AI 財務模擬系統後端已啟動 ===")
    print("請開啟瀏覽器輸入 http://127.0.0.1:8000/docs 查看 API 文件")
    uvicorn.run(app, host="127.0.0.1", port=8000)
