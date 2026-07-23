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
    FinancialOnboardingMessageRequest,
    FinancialOnboardingMessageResponse,
    FinancialProfileDraftConfirm,
    FinancialProfileDraftUpdate,
)
from app.security.auth import create_access_token, current_user, hash_password, public_user, verify_password
from app.services.expense_categorizer import categorize_expenses
from app.services.ai_provider import AIProvider, AIProviderError, get_ai_provider
from app.services.financial_answer_extraction import (
    ExtractionNormalizationError,
    deterministic_financial_extraction,
    extract_financial_answer,
)
from app.services.optimizer import optimize
from app.services.rate_limit import rate_limit_ai
from app.services.report_generator import generate_report
from app.services.scenario_parser import parse_scenario
from app.services.profile_onboarding import (
    assistant_reply,
    confirm_draft,
    create_draft,
    extract_message,
    is_standalone_amount_answer,
    merge_extraction_candidates,
    next_questions,
    interview_progress,
    update_draft,
)
from app.scenario_schemas import ScenarioComparisonRequest, ScenarioComparisonResponse
from app.services.scenario_engine import compare_scenarios


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
PROFILE_DRAFTS: Dict[str, Any] = {}
CONFIRMED_DEMO_PROFILES: Dict[str, Dict[str, Any]] = {}


def get_onboarding_ai_provider() -> AIProvider | None:
    return get_ai_provider()


@app.get("/api")
def home() -> Dict[str, Any]:
    return {
        "message": "FinSim-Core API is running",
        "product": "AI-assisted personal life-decision simulation and financial-risk analysis platform",
        "docs": "/docs",
        "version": settings.app_version,
        "ai_enabled": settings.ai_provider_ready(),
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


@app.post("/ai/financial-onboarding/message", response_model=FinancialOnboardingMessageResponse)
async def financial_onboarding_message(
    req: FinancialOnboardingMessageRequest,
    request: Request,
    provider: Any = Depends(get_onboarding_ai_provider),
) -> Dict[str, Any]:
    rate_limit_ai(request)
    draft = PROFILE_DRAFTS.get(req.draft_id) if req.draft_id else None
    if draft is None:
        draft = create_draft()
    updated = None
    provider_succeeded = False
    deterministic_extraction = deterministic_financial_extraction(req.text)
    if deterministic_extraction is not None:
        updated = merge_extraction_candidates(draft, deterministic_extraction, req.text)
        provider_succeeded = provider is not None
    elif is_standalone_amount_answer(req.text):
        # The active interview question deterministically defines a bare
        # amount's field. Avoid asking the model to infer it again.
        updated = extract_message(draft, req.text)
        provider_succeeded = provider is not None
    elif provider is not None:
        current_values = {
            field_name: {
                "value": getattr(draft, field_name).value,
                "source": getattr(draft, field_name).source.value,
            }
            for field_name in (
                "cash_and_deposits",
                "investments",
                "other_assets",
                "monthly_salary",
                "other_recurring_income",
                "fixed_expenses",
                "total_variable_expenses",
                "monthly_debt_payments",
                "emergency_fund",
                "simulation_months",
                "risk_preference",
            )
            if getattr(draft, field_name).source.value != "system_default"
        }
        try:
            extraction = await extract_financial_answer(
                provider=provider,
                answer=req.text,
                current_values=current_values,
                current_question=(next_questions(draft) or [None])[0],
                existing_future_plans=[
                    {
                        "index": index,
                        "value": item.value,
                        "source": item.source.value,
                    }
                    for index, item in enumerate(draft.future_plans)
                ],
            )
            updated = merge_extraction_candidates(draft, extraction, req.text)
            provider_succeeded = True
        except (AIProviderError, ExtractionNormalizationError, LookupError, ValueError):
            updated = None
    if updated is None:
        updated = extract_message(draft, req.text)
    PROFILE_DRAFTS[updated.id] = updated
    questions = next_questions(updated)
    progress = interview_progress(updated)
    return {
        "draft": updated,
        "assistant_message": assistant_reply(updated),
        "follow_up_questions": questions,
        "ready_for_review": not questions,
        "provider_available": provider_succeeded,
        **progress,
    }


@app.get("/financial-profile-drafts/{draft_id}")
def get_financial_profile_draft(draft_id: str) -> Dict[str, Any]:
    draft = PROFILE_DRAFTS.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="找不到財務資料草稿。")
    return {"draft": draft}


@app.put("/financial-profile-drafts/{draft_id}")
def update_financial_profile_draft(draft_id: str, req: FinancialProfileDraftUpdate) -> Dict[str, Any]:
    previous = PROFILE_DRAFTS.get(draft_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="找不到財務資料草稿。")
    updated = update_draft(req.draft, previous)
    PROFILE_DRAFTS[draft_id] = updated
    return {"draft": updated}


@app.post("/financial-profile-drafts/{draft_id}/confirm")
def confirm_financial_profile_draft(draft_id: str, req: FinancialProfileDraftConfirm) -> Dict[str, Any]:
    previous = PROFILE_DRAFTS.get(draft_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="找不到財務資料草稿。")
    if not req.explicit_confirmation:
        raise HTTPException(status_code=400, detail="必須明確確認後才能套用財務資料。")
    candidate = update_draft(req.draft, previous)
    try:
        confirmed, profile = confirm_draft(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    PROFILE_DRAFTS[draft_id] = confirmed
    CONFIRMED_DEMO_PROFILES[draft_id] = profile
    return {"status": "success", "draft": confirmed, "profile": profile}


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


@app.post("/scenarios/compare", response_model=ScenarioComparisonResponse)
def scenario_compare_api(req: ScenarioComparisonRequest) -> ScenarioComparisonResponse:
    """Typed, deterministic baseline/scenario comparison without persistence or providers."""
    try:
        return compare_scenarios(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/optimize")
def optimize_api(req: OptimizeRequest) -> Dict[str, Any]:
    return optimize(req.model_dump())


@app.post(
    "/ai/parse-scenario",
    deprecated=True,
    summary="Legacy scenario parser",
    description=(
        "Backward-compatible deterministic/AI parser. This legacy endpoint will "
        "later be replaced by the Generic Scenario Engine."
    ),
)
def parse_scenario_api(req: ScenarioParseRequest, request: Request) -> Dict[str, Any]:
    rate_limit_ai(request)
    confirmed_profile = (
        CONFIRMED_DEMO_PROFILES.get(req.profile_draft_id)
        if req.profile_draft_id
        else None
    )
    return parse_scenario(req, confirmed_profile=confirmed_profile).model_dump()


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
