from fastapi import APIRouter, HTTPException

from app.schemas import (
    SimulationRequest,
    MonteCarloRequest,
    CompareRequest,
)
from app.core.simulation import simulate_finance
from app.core.monte_carlo import run_monte_carlo
from app.core.advisor import compare_options, generate_advice


router = APIRouter(tags=["FutureWallet"])


@router.get("/")
def root():
    return {
        "message": "FutureWallet API is running"
    }


@router.post("/simulate")
def simulate_api(req: SimulationRequest):
    try:
        data = req.model_dump()

        result = simulate_finance(
            profile=data["profile"],
            months=data["months"],
            events=data.get("events", []),
            loans=data.get("loans", [])
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/monte-carlo")
def monte_carlo_api(req: MonteCarloRequest):
    try:
        data = req.model_dump()

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


@router.post("/compare")
def compare_api(req: CompareRequest):
    try:
        data = req.model_dump()

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