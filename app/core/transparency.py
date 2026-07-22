from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


CATEGORY_LABELS = {
    "food": "餐飲",
    "transportation": "交通",
    "shopping": "購物",
    "entertainment": "娛樂",
    "medical": "醫療",
    "education": "教育",
    "travel": "旅遊",
    "other": "其他",
    "social": "其他",
    "family_support": "其他",
}

DISPLAY_CATEGORIES = (
    "food",
    "transportation",
    "shopping",
    "entertainment",
    "medical",
    "education",
    "travel",
    "other",
)

SOURCE_DISPLAY_LABELS = {
    "manual": "使用者提供",
    "user_provided": "使用者提供",
    "使用者輸入": "使用者提供",
    "使用者提供": "使用者提供",
    "使用者財務資料": "使用者提供",
    "ai": "AI 語意解析",
    "ai_interpretation": "AI 語意解析",
    "ai_extracted": "AI 語意解析",
    "ai_estimated": "AI 語意解析",
    "AI 推估": "AI 語意解析",
    "AI 語意判讀": "AI 語意解析",
    "system_assumption": "系統模擬假設",
    "system_default": "系統模擬假設",
    "系統預設": "系統模擬假設",
    "系統假設值": "系統模擬假設",
    "系統模擬假設": "系統模擬假設",
    "system": "系統計算",
    "derived": "系統計算",
    "backend_normalized": "系統計算",
    "系統計算": "系統計算",
    "財務引擎計算": "系統計算",
    "external_estimate": "外部資料估算",
    "external_research": "外部資料估算",
    "外部資料": "外部資料估算",
    "外部資料估算": "外部資料估算",
}


def display_source_label(source: Any) -> str:
    normalized = getattr(source, "value", source)
    if normalized is None:
        return "來源未標示"
    return SOURCE_DISPLAY_LABELS.get(str(normalized), "來源未標示")


def _active(event: Dict[str, Any], month: int) -> bool:
    start = event.get("start_month") or event.get("month")
    end = event.get("end_month") or start
    return bool(start and end and int(start) <= month <= int(end))


def _display_category(category: Optional[str]) -> str:
    if hasattr(category, "value"):
        category = category.value
    if category in ("social", "family_support", None):
        return "other"
    return str(category)


def _group_categories(row: Dict[str, Any]) -> Dict[str, float]:
    grouped = {category: 0.0 for category in DISPLAY_CATEGORIES}
    for item in row.get("expense_categories", []) or []:
        category = _display_category(item.get("category"))
        if category in grouped:
            grouped[category] += float(item.get("amount", 0) or 0)
    return {key: round(value, 2) for key, value in grouped.items()}


def _percentages(amounts: Dict[str, float]) -> Dict[str, float]:
    total = round(sum(amounts.values()), 2)
    if total <= 0:
        return {category: 0.0 for category in DISPLAY_CATEGORIES}
    result = {
        category: round(amounts.get(category, 0.0) / total * 100, 2)
        for category in DISPLAY_CATEGORIES
    }
    remainder = round(100.0 - sum(result.values()), 2)
    largest = max(DISPLAY_CATEGORIES, key=lambda category: amounts.get(category, 0.0))
    result[largest] = round(result[largest] + remainder, 2)
    return result


def _event_reasons(events: Iterable[Dict[str, Any]], category: str, month: int) -> List[str]:
    reasons = []
    for event in events:
        target = _display_category(event.get("target_expense_category"))
        changes_category = (
            float(event.get("category_monthly_adjustment", 0) or 0) != 0
            or float(event.get("variable_expense_multiplier", 1) or 1) != 1
        )
        if changes_category and _active(event, month) and target in (category, "other"):
            reason = event.get("reason") or event.get("description") or event.get("name")
            if reason:
                reasons.append(str(reason))
    return reasons


def _event_source(
    events: Iterable[Dict[str, Any]],
    category: str,
    month: int,
) -> Optional[str]:
    sources = []
    for event in events:
        target = _display_category(event.get("target_expense_category"))
        changes_category = (
            float(event.get("category_monthly_adjustment", 0) or 0) != 0
            or float(event.get("variable_expense_multiplier", 1) or 1) != 1
        )
        if changes_category and _active(event, month) and target in (category, "other"):
            label = display_source_label(event.get("source"))
            if label not in sources:
                sources.append(label)
    return "、".join(sources) if sources else None


def _expense_source(profile: Dict[str, Any]) -> str:
    model = profile.get("variable_expense_model") or {}
    if model.get("mode") == "advanced" and model.get("categories"):
        return "user_provided"
    return "system_assumption"


def _metric(before: Optional[float], after: Optional[float]) -> Dict[str, Optional[float]]:
    if before is None or after is None:
        return {"before": before, "after": after, "difference": None}
    return {
        "before": round(float(before), 4),
        "after": round(float(after), 4),
        "difference": round(float(after) - float(before), 4),
    }


def _event_costs(event: Dict[str, Any]) -> Dict[str, float]:
    one_time = event.get("amount") if event.get("type") == "one_time" else event.get("one_time_amount")
    one_time_cost = max(0.0, -float(one_time or 0))
    direct_monthly = float(event.get("monthly_amount", 0) or 0)
    category_monthly = float(event.get("category_monthly_adjustment", 0) or 0)
    recurring_cost = max(0.0, -direct_monthly) + max(0.0, category_monthly)
    offset = max(0.0, direct_monthly) + max(0.0, -category_monthly)
    return {
        "one_time_cost": round(one_time_cost, 2),
        "recurring_cost": round(recurring_cost, 2),
        "offset": round(offset, 2),
    }


def build_simulation_transparency(
    *,
    profile: Dict[str, Any],
    events: List[Dict[str, Any]],
    loans: List[Dict[str, Any]],
    random_shocks: List[Dict[str, Any]],
    baseline_result: Dict[str, Any],
    scenario_result: Dict[str, Any],
    scenario_context: Optional[List[Dict[str, Any]]] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    baseline_curve = baseline_result.get("simulation_curve") or []
    scenario_curve = scenario_result.get("simulation_curve") or []
    candidate_months = [
        int(event.get("start_month") or event.get("month"))
        for event in events
        if event.get("start_month") or event.get("month")
    ]
    comparison_month = min(candidate_months) if candidate_months else 1
    max_month = min(len(baseline_curve), len(scenario_curve))
    if max_month:
        comparison_month = min(max(comparison_month, 1), max_month)

    baseline_row = baseline_curve[comparison_month - 1] if max_month else {}
    scenario_row = scenario_curve[comparison_month - 1] if max_month else {}
    original = _group_categories(baseline_row)
    adjusted = _group_categories(scenario_row)
    original_percentages = _percentages(original)
    adjusted_percentages = _percentages(adjusted)
    allocation_source = _expense_source(profile)
    allocation_source_label = display_source_label(allocation_source)

    allocation = []
    comparison = []
    for category in DISPLAY_CATEGORIES:
        before = original.get(category, 0.0)
        after = adjusted.get(category, 0.0)
        difference = round(after - before, 2)
        reasons = _event_reasons(events, category, comparison_month)
        source = _event_source(events, category, comparison_month) or allocation_source_label
        allocation.append(
            {
                "category": category,
                "label": CATEGORY_LABELS[category],
                "monthly_amount": round(after, 2),
                "percentage": adjusted_percentages[category],
                "original_percentage": original_percentages[category],
                "source": source,
                "scenario_changed": abs(difference) >= 0.01,
            }
        )
        comparison.append(
            {
                "category": category,
                "label": CATEGORY_LABELS[category],
                "original_amount": round(before, 2),
                "adjusted_amount": round(after, 2),
                "difference": difference,
                "reason": "；".join(reasons) if reasons else "無情境調整",
                "source": source,
            }
        )

    event_ledger = []
    for event in events:
        costs = _event_costs(event)
        month = int(event.get("start_month") or event.get("month") or 1)
        event_ledger.append(
            {
                "name": event.get("name") or "財務事件",
                "type": event.get("type") or "life_event",
                "month": month,
                "end_month": event.get("end_month"),
                "category": _display_category(event.get("target_expense_category")),
                "category_label": CATEGORY_LABELS.get(
                    _display_category(event.get("target_expense_category")), "其他"
                ),
                "source": display_source_label(event.get("source")),
                "reason": event.get("reason") or event.get("description") or "",
                "effect_on_assets": round(
                    -costs["one_time_cost"] - costs["recurring_cost"] + costs["offset"], 2
                ),
                **costs,
            }
        )

    one_time_cost = round(sum(item["one_time_cost"] for item in event_ledger), 2)
    recurring_cost = round(sum(item["recurring_cost"] for item in event_ledger), 2)
    offsets = round(sum(item["offset"] for item in event_ledger), 2)
    replaced = round(
        sum(
            item["recurring_cost"]
            for item, event in zip(event_ledger, events)
            if event.get("expense_role") == "replacement"
        ),
        2,
    )

    baseline_summary = baseline_result.get("summary") or {}
    scenario_summary = scenario_result.get("summary") or {}
    baseline_last = baseline_curve[-1] if baseline_curve else {}
    scenario_last = scenario_curve[-1] if scenario_curve else {}
    impact = {
        "final_assets": _metric(
            baseline_summary.get("final_balance"), scenario_summary.get("final_balance")
        ),
        "lowest_asset_balance": _metric(
            baseline_summary.get("min_balance"), scenario_summary.get("min_balance")
        ),
        "monthly_cash_flow": _metric(
            baseline_last.get("net_cashflow"), scenario_last.get("net_cashflow")
        ),
        "emergency_fund_coverage": _metric(
            baseline_summary.get("emergency_fund_coverage"),
            scenario_summary.get("emergency_fund_coverage"),
        ),
        "debt_to_income_ratio": _metric(
            baseline_summary.get("debt_to_income"), scenario_summary.get("debt_to_income")
        ),
        "fsi": _metric(baseline_summary.get("max_fsi"), scenario_summary.get("max_fsi")),
        "negative_balance_probability": _metric(None, None),
        "monte_carlo_risk_probability": _metric(None, None),
        "first_high_risk_month": {
            "before": baseline_summary.get("first_risk_month"),
            "after": scenario_summary.get("first_risk_month"),
            "difference": None,
        },
    }

    markers = [
        {
            "name": item["name"],
            "month": item["month"],
            "cost": round(item["one_time_cost"] + item["recurring_cost"], 2),
            "category": item["category_label"],
            "source": item["source"],
            "effect_on_assets": item["effect_on_assets"],
        }
        for item in event_ledger
    ]
    first_risk_month = scenario_summary.get("first_risk_month")
    if first_risk_month:
        markers.append(
            {
                "name": "首次高風險月份",
                "month": first_risk_month,
                "cost": 0,
                "category": "風險",
                "source": "財務引擎計算",
                "effect_on_assets": 0,
            }
        )

    return {
        "version": 1,
        "scenarios": scenario_context or [],
        "comparison_month": comparison_month,
        "actions": [
            "理解使用者的未來計畫",
            f"建立 {len(events)} 個財務事件",
            "調整相關支出分類",
            "分開計算一次性、週期性支出與抵銷",
            "執行基準與情境財務模擬",
            "分析資產、現金流與風險變化",
        ],
        "assumptions": [
            {
                "label": "年調薪率",
                "value": profile.get("raise_rate", 0.03),
                "source": "使用者輸入",
                "editable": True,
            },
            {
                "label": "年通膨率",
                "value": profile.get("inflation_rate", 0.02),
                "source": "使用者輸入",
                "editable": True,
            },
            {
                "label": "緊急備用金目標",
                "value": profile.get("target_emergency_months", 3),
                "source": "使用者輸入",
                "editable": True,
            },
            {
                "label": "變動支出分配",
                "value": allocation_source_label,
                "source": allocation_source_label,
                "editable": True,
            },
            {
                "label": "隨機財務衝擊",
                "value": "已啟用" if random_shocks else "未啟用",
                "source": "使用者輸入",
                "editable": True,
            },
            {
                "label": "Random seed",
                "value": seed,
                "source": display_source_label(
                    "system_assumption" if seed is None else "user_provided"
                ),
                "editable": True,
            },
        ],
        "sources": [
            {
                "label": "目前資產與每月收支",
                "source": display_source_label("user_provided"),
                "estimated": False,
            },
            {
                "label": "變動支出分類比例",
                "source": allocation_source_label,
                "estimated": allocation_source == "system_assumption",
            },
            {
                "label": "情境事件與金額",
                "source": (
                    display_source_label(events[0].get("source"))
                    if events
                    else "來源未標示"
                ),
                "estimated": any(
                    getattr(event.get("source"), "value", event.get("source"))
                    == "system_assumption"
                    for event in events
                ),
            },
            {
                "label": "資產、現金流與 FSI",
                "source": display_source_label("derived"),
                "estimated": False,
            },
        ],
        "events": event_ledger,
        "expense_allocation": allocation,
        "expense_comparison": comparison,
        "cost_breakdown": {
            "normal_monthly_expenses": round(
                float(baseline_row.get("expense", 0) or 0)
                + float(baseline_row.get("debt_payment", 0) or 0),
                2,
            ),
            "one_time_scenario_expenses": one_time_cost,
            "recurring_scenario_expenses": recurring_cost,
            "replaced_expenses": replaced,
            "offsets": offsets,
            "net_monthly_change": round(recurring_cost - offsets, 2),
        },
        "financial_impact": impact,
        "event_markers": markers,
    }
