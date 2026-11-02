from __future__ import annotations
from app.core.financial_rules import emergency_shortfall

import math
import random
import statistics
from typing import Any, Dict, List, Optional

from app.core.expenses import get_expense_categories
from app.core.market_data import BLOCK_MONTHS, MarketHistory, block_bootstrap_indices, load_market_history
from app.core.simulation import simulate_finance


PAST_PERFORMANCE_WARNING = '歷史期間台股表現特別好，過去報酬不代表未來。'


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _percentiles(values: List[float], points=(5, 25, 50, 75, 95)) -> Dict[str, float]:
    return {f'p{point}': round(percentile(values, point / 100), 2) for point in points}


def _band(columns: List[List[float]], points) -> Dict[str, List[float]]:
    return {f'p{point}': [round(percentile(column, point / 100), 2) for column in columns] for point in points}


def _has_investment(profile: Dict[str, Any]) -> bool:
    return float(profile.get('investment_value') or 0) > 0 or float(profile.get('monthly_investment') or 0) > 0


def _sampling_metadata(profile: Dict[str, Any], random_shocks: List[Dict[str, Any]],
                       history: MarketHistory, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    sampled_parameters = []
    fixed_parameters = []
    span = f'{history.start_period} 至 {history.end_period} 共 {len(history.periods)} 個月'
    if profile.get('inflation_rate') is None:
        sampled_parameters.append('inflation_rate')
        notes = [f'通膨率與台股報酬取自 {span}的台灣歷史月資料，每次試驗以連續 {BLOCK_MONTHS} 個月為一個區塊抽樣，'
                 '同一個月的通膨與報酬成對抽取。']
    else:
        fixed_parameters.append('inflation_rate')
        notes = [f"通膨率固定使用使用者提供的 {float(profile['inflation_rate']) * 100:g}%，未抽樣；"
                 f'台股報酬取自 {span}的歷史月資料，以連續 {BLOCK_MONTHS} 個月為一個區塊抽樣。'
                 '歷史通膨與報酬按同一個月份成對選取，但通膨以使用者的固定值取代。']
    if profile.get('raise_rate') is None:
        if 'inflation_rate' in sampled_parameters:
            sampled_parameters.append('raise_rate')
            notes.append('調薪率跟隨該次試驗的實際通膨，每年調整一次。')
        else:
            notes.append('調薪率等於固定通膨率。')
    else:
        fixed_parameters.append('raise_rate')
        notes.append(f"調薪率固定使用使用者提供的 {float(profile['raise_rate']) * 100:g}%。")
    # Return paths are drawn in every trial, even when the investment account is zero.
    sampled_parameters.append('investment_return')
    if _has_investment(profile):
        notes.append('投資市值依抽樣的台股報酬指數（含股利再投入）變動，現金不足時也不會自動賣出。')
    else:
        notes.append('未設定投資市值或每月投入，抽樣報酬不影響帳戶金額。')
    notes.append('預期年報酬率（expected_annual_return）只用於確定性模擬，不影響 Monte Carlo。')

    expense_model = profile.get('variable_expense_model') or {}
    if expense_model.get('mode') == 'advanced' and any(
            category.get('enabled', True) for category in (expense_model.get('categories') or [])):
        notes.append('進階模式的支出分類使用各自設定的通膨率，不跟隨抽樣通膨。')

    # Advanced expense volatility remains a random source even with fixed rates.
    if any(float(category.get('monthly_volatility', 0) or 0) > 0
           for category in get_expense_categories(profile)):
        sampled_parameters.append('variable_expense')
        notes.append('變動支出依已啟用分類的月波動率抽樣。')
    if assets:
        notes.append('車輛估值依固定折舊率計算，不抽樣。')
    notes.append(PAST_PERFORMANCE_WARNING)
    if (profile.get('inflation_rate') is not None and not _has_investment(profile)
            and 'variable_expense' not in sampled_parameters
            and not any(shock.get('enabled', True) for shock in random_shocks)):
        notes.append('本次結果沒有隨機變動，分位數會相同。')
    return {
        'sampled_parameters': sampled_parameters,
        'fixed_parameters': fixed_parameters,
        'sampling_note': ''.join(notes),
        'sampling_method': {
            'method': 'block_bootstrap',
            'block_months': BLOCK_MONTHS,
            'paired_inflation_and_return': 'inflation_rate' in sampled_parameters,
            'history_start': history.start_period,
            'history_end': history.end_period,
            'history_months': len(history.periods),
        },
    }


def run_monte_carlo(
    profile: Dict[str, Any],
    base_events: Optional[List[Dict[str, Any]]] = None,
    loans: Optional[List[Dict[str, Any]]] = None,
    random_shocks: Optional[List[Dict[str, Any]]] = None,
    months: int = 60,
    simulations: int = 500,
    seed: Optional[int] = None,
    sample_paths: int = 8,
    include_details: bool = False,
    assets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if months <= 0:
        raise ValueError("months must be > 0")
    if simulations <= 0 or simulations > 5000:
        raise ValueError("simulations must be between 1 and 5000")

    base_events = base_events or []
    loans = loans or []
    random_shocks = random_shocks or []
    master_rng = random.Random(seed)
    history = load_market_history()
    fixed_inflation = profile.get("inflation_rate")

    final_balances: List[float] = []
    final_net_worths: List[float] = []
    real_net_worths: List[float] = []
    cash_shortfall_count = 0
    emergency_shortfalls: List[float] = []
    # One list per month across trials, for the monthly percentile bands.
    monthly_cash: List[List[float]] = [[] for _ in range(months)]
    monthly_investment: List[List[float]] = [[] for _ in range(months)]
    monthly_net_worth: List[List[float]] = [[] for _ in range(months)]
    paths = []
    debug_paths = []

    for index in range(simulations):
        path_seed = master_rng.randint(0, 2_147_483_647)
        # Inflation and return always come from the same historical month.
        months_drawn = block_bootstrap_indices(master_rng, months, len(history.periods))
        return_path = [history.returns[i] for i in months_drawn]
        inflation_path = None if fixed_inflation is not None else [history.inflation[i] for i in months_drawn]
        result = simulate_finance(
            profile=profile,
            months=months,
            events=base_events,
            loans=loans,
            random_shocks=random_shocks,
            seed=path_seed,
            include_details=include_details,
            inflation_path=inflation_path,
            return_path=return_path,
            assets=assets,
        )
        summary = result["summary"]
        curve = result["simulation_curve"]
        price_multiplier = (math.prod(1 + rate for rate in inflation_path) if inflation_path is not None
                            else (1 + float(fixed_inflation)) ** (months / 12))
        final_balances.append(summary["final_balance"])
        final_net_worths.append(summary["final_net_worth"])
        real_net_worths.append(summary["final_net_worth"] / price_multiplier)
        cash_shortfall_count += summary["first_negative_cash_month"] is not None
        for month_index, row in enumerate(curve):
            monthly_cash[month_index].append(row["balance"])
            monthly_investment[month_index].append(row["investment_value"])
            monthly_net_worth[month_index].append(row["net_worth"])
        target_months = float(profile.get("target_emergency_months", 3))
        emergency_shortfalls.append(emergency_shortfall(summary["final_balance"], curve[-1]["living_expense"], curve[-1]["debt_payment"], target_months))
        if index < sample_paths:
            paths.append(
                {
                    "seed": path_seed,
                    "history_periods": [history.periods[i] for i in months_drawn[::BLOCK_MONTHS]],
                    "points": [{"month": row["month"], "balance": row["balance"], "net_worth": row["net_worth"]}
                               for row in curve],
                }
            )
        if include_details and index < min(3, sample_paths):
            debug_paths.append({**result, "inflation_path": inflation_path, "return_path": return_path,
                                "price_multiplier": price_multiplier})

    shortfall_probability = cash_shortfall_count / simulations

    response = {
        "iterations": simulations,
        "seed": seed,
        "avg_final_balance": round(statistics.fmean(final_balances), 2),
        "median_final_balance": round(statistics.median(final_balances), 2),
        "min_final_balance": round(min(final_balances), 2),
        "max_final_balance": round(max(final_balances), 2),
        "percentiles": _percentiles(final_balances),
        "net_worth_percentiles": _percentiles(final_net_worths),
        "real_net_worth_percentiles": _percentiles(real_net_worths, (5, 50, 95)),
        "real_net_worth_definition": "期末淨資產（現金加投資）除以該次試驗的累積物價倍數，以今日購買力表示",
        "probability_cash_shortfall": round(shortfall_probability, 4),
        "cash_shortfall_definition": "模擬期間任一月底現金小於 0 的試驗比例",
        **_sampling_metadata(profile, random_shocks, history, assets or []),
        "data_sources": [dict(source) for source in history.data_sources],
        "expected_emergency_fund_shortfall": round(statistics.fmean(emergency_shortfalls), 2),
        "sample_paths": paths,
        "monthly_bands": {
            "definition": "每個月底在所有試驗中的分位數；各分位數線不是某一次試驗的路徑",
            "months": list(range(1, months + 1)),
            "net_worth": _band(monthly_net_worth, (5, 25, 50, 75, 95)),
            "cash": _band(monthly_cash, (5, 50, 95)),
            "investment": _band(monthly_investment, (5, 50, 95)),
        },
        "historical_averages": {
            "annual_inflation_rate": round(history.annual_inflation_rate, 6),
            "annual_return_rate": round(history.annual_return_rate, 6),
        },
    }
    if include_details:
        response["debug_paths"] = debug_paths
    return response
