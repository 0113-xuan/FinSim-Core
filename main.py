from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.advisor import compare_options, generate_advice
from app.core.monte_carlo import run_monte_carlo
from app.core.simulation import simulate_finance
from app.core.transparency import build_simulation_transparency
from app.schemas import (
    CategorizeExpensesRequest,
    CompareRequest,
    GenerateReportRequest,
    LoginRequest,
    MonteCarloRequest,
    OptimizeRequest,
    RegisterRequest,
    ScenarioParseRequest,
    SimulationRequest,
)
from app.security.auth import create_access_token, current_user, hash_password, public_user, verify_password
from app.services.expense_categorizer import categorize_expenses
from app.services.optimizer import optimize
from app.services.rate_limit import rate_limit_ai
from app.services.report_generator import generate_report
from app.services.scenario_parser import parse_scenario


@asynccontextmanager
async def lifespan(_: FastAPI):
    for warning in settings.startup_warnings():
        print(f"CONFIG WARNING: {warning}")
    yield


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="FinSim-Core API",
    version=settings.app_version,
    description="AI-assisted personal life-decision simulation and financial-risk analysis platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Graduation-project friendly fallback store. Production deployments should use Supabase Auth/RLS.
USERS: Dict[str, Dict[str, Any]] = {}
PROFILES: Dict[str, Dict[str, Any]] = {}


@app.get("/api")
def home() -> Dict[str, Any]:
    return {
        "message": "FinSim-Core API is running",
        "product": "AI-assisted personal life-decision simulation and financial-risk analysis platform",
        "docs": "/docs",
        "version": settings.app_version,
        "ai_enabled": settings.ai_enabled and bool(settings.ai_api_key),
    }


@app.get("/api/version")
def version() -> Dict[str, str]:
    return {"app": settings.app_name, "version": settings.app_version}


@app.post("/auth/register")
def register_user(req: RegisterRequest) -> Dict[str, Any]:
    if req.username in USERS:
        raise HTTPException(status_code=400, detail="Username already exists")
    if any(user["email"] == req.email for user in USERS.values()):
        raise HTTPException(status_code=400, detail="Email already exists")
    user = public_user(req.username, str(req.email))
    USERS[req.username] = {**user, "password_hash": hash_password(req.password)}
    token = create_access_token(user)
    return {"status": "success", "user": user, "access_token": token, "token_type": "bearer"}


@app.post("/auth/login")
def login_user(req: LoginRequest) -> Dict[str, Any]:
    stored = USERS.get(req.username)
    if not stored or stored["email"] != str(req.email) or not verify_password(req.password, stored["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username, email, or password")
    user = {key: stored[key] for key in ("id", "username", "email")}
    return {"status": "success", "user": user, "access_token": create_access_token(user), "token_type": "bearer"}


@app.post("/financial-profile")
def save_financial_profile(profile: Dict[str, Any], user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    PROFILES[user["sub"]] = profile
    return {"status": "success", "profile": profile}


@app.get("/financial-profile")
def get_financial_profile(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"profile": PROFILES.get(user["sub"])}


@app.post("/simulate")
def simulate_api(req: SimulationRequest) -> Dict[str, Any]:
    data = req.model_dump()
    baseline = simulate_finance(
        profile=data["profile"],
        months=data["months"],
        events=[],
        loans=data.get("loans", []),
        random_shocks=data.get("random_shocks", []),
        seed=data.get("seed"),
        include_details=True,
    )
    result = simulate_finance(
        profile=data["profile"],
        months=data["months"],
        events=data.get("events", []),
        loans=data.get("loans", []),
        random_shocks=data.get("random_shocks", []),
        seed=data.get("seed"),
        include_details=True,
    )
    result["transparency"] = build_simulation_transparency(
        profile=data["profile"],
        events=data.get("events", []),
        loans=data.get("loans", []),
        random_shocks=data.get("random_shocks", []),
        baseline_result=baseline,
        scenario_result=result,
        scenario_context=data.get("scenario_context", []),
        seed=data.get("seed"),
    )
    if not data.get("include_details", False):
        for row in result["simulation_curve"]:
            row.pop("expense_categories", None)
        result.pop("shock_details", None)
    return {"result": result}


@app.post("/monte-carlo")
def monte_carlo_api(req: MonteCarloRequest) -> Dict[str, Any]:
    data = req.model_dump()
    return run_monte_carlo(
        profile=data["profile"],
        base_events=data.get("events", []),
        loans=data.get("loans", []),
        random_shocks=data.get("random_shocks", []),
        months=data["months"],
        simulations=data["simulations"],
        seed=data.get("seed"),
        sample_paths=data.get("sample_paths", 8),
        include_details=data.get("include_details", False),
    )


@app.post("/compare")
def compare_api(req: CompareRequest) -> Dict[str, Any]:
    data = req.model_dump()
    compare_result = compare_options(
        profile=data["profile"],
        options=data["options"],
        months=data["months"],
        mc_runs=data["mc_runs"],
        seed=data.get("seed"),
    )
    return {"compare_result": compare_result, "advice": generate_advice(compare_result)}


@app.post("/optimize")
def optimize_api(req: OptimizeRequest) -> Dict[str, Any]:
    return optimize(req.model_dump())


@app.post("/ai/parse-scenario")
def parse_scenario_api(req: ScenarioParseRequest, request: Request) -> Dict[str, Any]:
    rate_limit_ai(request)
    return parse_scenario(req).model_dump()


@app.post("/ai/categorize-expenses")
def categorize_expenses_api(req: CategorizeExpensesRequest, request: Request) -> Dict[str, Any]:
    rate_limit_ai(request)
    return categorize_expenses(req).model_dump()


@app.post("/ai/generate-report")
def generate_report_api(req: GenerateReportRequest, request: Request) -> Dict[str, Any]:
    rate_limit_ai(request)
    return generate_report(req.model_dump())


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
