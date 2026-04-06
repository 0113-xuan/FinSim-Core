from typing import Dict, Any, List
from app.core.simulation import simulate_finance
from app.core.monte_carlo import run_monte_carlo


def score_option(sim_summary: Dict[str, Any], mc_summary: Dict[str, Any]) -> float:
    """
    方案評分函式
    分數越低越好

    權重邏輯：
    - max_fsi 越高越差
    - min_balance 若為負，懲罰越重
    - bankrupt_probability 越高越差
    """
    score = 0.0

    score += sim_summary["max_fsi"] * 50
    score += max(0, -sim_summary["min_balance"]) * 0.001
    score += mc_summary["bankrupt_probability"] * 100

    return round(score, 4)


def compare_options(
    profile: Dict[str, Any],
    options: List[Dict[str, Any]],
    months: int = 60,
    mc_runs: int = 300
) -> Dict[str, Any]:
    """
    比較多個方案，回傳最佳方案與各方案結果

    options 格式：
    [
        {
            "name": "buy_now",
            "events": [...],
            "loans": [...]
        },
        ...
    ]
    """
    if not options:
        raise ValueError("options must not be empty")

    option_results = []

    for option in options:
        sim_result = simulate_finance(
            profile=profile,
            months=months,
            events=option.get("events", []),
            loans=option.get("loans", [])
        )

        mc_result = run_monte_carlo(
            profile=profile,
            base_events=option.get("events", []),
            loans=option.get("loans", []),
            months=months,
            simulations=mc_runs
        )

        score = score_option(sim_result["summary"], mc_result)

        option_results.append({
            "name": option["name"],
            "simulation_summary": sim_result["summary"],
            "monte_carlo_summary": mc_result,
            "score": score
        })

    option_results.sort(key=lambda x: x["score"])
    best = option_results[0]

    return {
        "best_option": best["name"],
        "options": option_results
    }


def generate_advice(compare_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    依最佳方案生成建議文字與風險摘要
    """
    best = compare_result["options"][0]
    sim = best["simulation_summary"]
    mc = best["monte_carlo_summary"]

    if mc["bankrupt_probability"] < 0.05 and sim["max_fsi"] < 0.75:
        risk_level = "low"
    elif mc["bankrupt_probability"] < 0.15 and sim["max_fsi"] < 0.90:
        risk_level = "medium"
    else:
        risk_level = "high"

    summary = (
        f"綜合現金流模擬、FSI 與 Monte Carlo 分析後，"
        f"目前最建議的方案為「{best['name']}」。"
    )

    reasons = [
        f"最高 FSI 為 {sim['max_fsi']}",
        f"最低資產餘額為 {sim['min_balance']}",
        f"Monte Carlo 破產機率為 {mc['bankrupt_probability'] * 100:.2f}%"
    ]

    suggestions = []

    if sim["min_balance"] < 0:
        suggestions.append("此方案曾出現資產轉負，建議降低支出或延後高額決策。")

    if sim["max_fsi"] >= 0.90:
        suggestions.append("財務壓力偏高，建議增加緊急預備金或降低貸款負擔。")

    if mc["bankrupt_probability"] >= 0.15:
        suggestions.append("情境風險偏高，建議保守規劃並預留更高安全邊際。")

    if not suggestions:
        suggestions.append("整體風險可控，可作為優先考慮方案。")

    return {
        "summary": summary,
        "risk_level": risk_level,
        "best_option": best["name"],
        "reason": reasons,
        "suggestions": suggestions
    }