from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# 1. 初始化 FastAPI
app = FastAPI(title="AI 財務模擬系統 API", version="1.0.0")

# 2. 定義資料模型 (Data Models) - 讓組員 A 知道要傳什麼 JSON 過來
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

# 3. API 路由實作 (API Routes)

@app.get("/")
def home():
    return {"message": "後端系統運作中", "docs": "/docs"}

# [POST] 建立使用者
@app.post("/user/create")
async def create_user(user: UserCreate):
    # TODO: 這裡之後要呼叫組員 D 的資料庫儲存功能
    return {"status": "success", "message": f"使用者 {user.username} 已建立"}

# [POST] 執行模擬 (核心功能)
@app.post("/simulate")
async def simulate(request: SimulationRequest):
    # TODO: 這裡要呼叫組員 C 的 simulate_future() 函數
    # 目前先回傳假資料 (Mock Data) 供前端測試
    mock_result = {
        "user_id": request.user_id,
        "future_savings": request.initial_savings + (request.monthly_income - request.monthly_expense) * 12 * request.years,
        "bankruptcy_probability": "5%",
        "fsi_index": 0.35
    }
    return mock_result

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

# 4. 啟動伺服器
if __name__ == "__main__":
    print("=== AI 財務模擬系統後端已啟動 ===")
    print("請開啟瀏覽器輸入 http://127.0.0.1:8000/docs 查看 API 文件")
    uvicorn.run(app, host="127.0.0.1", port=8000)
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 這行就是 VIP 名單！
    allow_credentials=True,
    allow_methods=["*"],   # 允許 GET, POST 等所有動作
    allow_headers=["*"],
)