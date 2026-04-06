import random
from typing import Dict, Any, List, Optional
from app.core.simulation import simulate_finance


def generate_random_shock_event(months: int) -> List[Dict[str, Any]]:
    """
    隨機產生一次性突發支出
    機率 10%，金額 5000 ~ 50000
    """
    events: List[Dict[str, Any]] = []

    if random.random() < 0.10:
        shock_month = random.randint(1, months)
        shock_amount = random.randint(5000, 50000)
        events.append({
            "type": "one_time",
            "month": shock_month,
            "amount": -shock_amount,
            "note": "random_shock"
        })

    return events


def run_monte_carlo(
    profile: Dict[str, Any],
    base_events: Optional[List[Dict[str, Any]]] = None,
    loans: Optional[List[Dict[str, Any]]] = None,
    months: int = 60,
    simulations: int = 1000
) -> Dict[str, Any]:
    """
    Monte Carlo 多情境模擬

    每次模擬會：
    - 隨機抽樣薪資成長率
    - 隨機抽樣通膨率
    - 可能加入一次突發支出
    """
    if months <= 0:
        raise ValueError("months must be > 0")

    if simulations <= 0:
        raise ValueError("simulations must be > 0")

    base_events = base_events or []
    loans = loans or []

    results = []

    for _ in range(simulations):
        sampled_raise_rate = random.uniform(0.02, 0.05)
        sampled_inflation_rate = random.uniform(0.01, 0.04)

        random_events = generate_random_shock_event(months)
        all_events = list(base_events) + random_events

        result = simulate_finance(
            profile=profile,
            months=months,
            events=all_events,
            loans=loans,
            override_raise_rate=sampled_raise_rate,
            override_inflation_rate=sampled_inflation_rate
        )

        summary = result["summary"]

        results.append({
            "final_balance": summary["final_balance"],
            "min_balance": summary["min_balance"],
            "max_fsi": summary["max_fsi"],
            "bankrupt": summary["min_balance"] < 0
        })

    avg_final_balance = sum(r["final_balance"] for r in results) / len(results)
    best_case_balance = max(r["final_balance"] for r in results)
    worst_case_balance = min(r["final_balance"] for r in results)
    bankrupt_probability = sum(1 for r in results if r["bankrupt"]) / len(results)
    avg_max_fsi = sum(r["max_fsi"] for r in results) / len(results)

    return {
        "simulations": simulations,
        "avg_final_balance": round(avg_final_balance, 2),
        "best_case_balance": round(best_case_balance, 2),
        "worst_case_balance": round(worst_case_balance, 2),
        "bankrupt_probability": round(bankrupt_probability, 4),
        "avg_max_fsi": round(avg_max_fsi, 4)
    }