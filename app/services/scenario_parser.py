from __future__ import annotations

from typing import Any, Dict, List

from pydantic import ValidationError

from app.schemas import EventSource, ParsedScenario, ScenarioContext, ScenarioParseRequest
from app.services.ai_provider import get_ai_provider


def _scenario_display(
    *,
    events: List[Dict[str, Any]],
    adjustments: List[Dict[str, Any]],
    confidence: float,
    months: int,
) -> ScenarioContext:
    starts = [
        int(item.get("start_month") or item.get("month") or 1)
        for item in [*events, *adjustments]
    ]
    ends = [
        int(item.get("end_month") or item.get("start_month") or item.get("month") or 1)
        for item in [*events, *adjustments]
    ]
    start_month = min(starts) if starts else 1
    end_month = min(max(ends) if ends else start_month, months)
    duration = max(1, end_month - start_month + 1)
    one_time = sum(
        max(
            0.0,
            -float(
                item.get("amount")
                if item.get("type") == "one_time"
                else item.get("one_time_amount", 0)
                or 0
            ),
        )
        for item in events
    )
    recurring = sum(
        max(0.0, -float(item.get("monthly_amount", 0) or 0))
        + max(0.0, float(item.get("category_monthly_adjustment", 0) or 0))
        for item in events
    ) + sum(max(0.0, float(item.get("monthly_amount", 0) or 0)) for item in adjustments)
    titles = list(dict.fromkeys(item.get("name") for item in events if item.get("name")))
    expected = one_time + recurring * duration
    assumptions = [
        {
            "key": "timing",
            "label": "發生時間",
            "value": f"第 {start_month} 個月開始",
            "suggested_value": f"第 {start_month} 個月開始",
            "source": "AI 推估",
            "editable": True,
        },
        {
            "key": "duration",
            "label": "持續期間",
            "value": f"{duration} 個月",
            "suggested_value": f"{duration} 個月",
            "source": "AI 推估",
            "editable": True,
        },
    ]
    if any("旅行" in str(item.get("name", "")) for item in events):
        assumptions.append(
            {
                "key": "travel_style",
                "label": "旅遊方式",
                "value": "標準型",
                "suggested_value": "標準型",
                "source": "系統預設",
                "editable": True,
            }
        )
    if any("車貸" in str(item.get("name", "")) for item in events):
        assumptions.extend(
            [
                {
                    "key": "car_loan_term",
                    "label": "車貸期限",
                    "value": "60 個月",
                    "suggested_value": "60 個月",
                    "source": "系統預設",
                    "editable": True,
                },
                {
                    "key": "car_loan_rate",
                    "label": "車貸利率",
                    "value": "2.8%",
                    "suggested_value": "2.8%",
                    "source": "系統預設",
                    "editable": True,
                },
            ]
        )
    return ScenarioContext(
        id=f"scenario-{start_month}-{len(events)}-{len(adjustments)}",
        title="、".join(titles[:3]) or "AI 建立的財務情境",
        scenario_type="複合生活事件" if len(titles) > 1 else (titles[0] if titles else "生活事件"),
        start_month=start_month,
        duration_months=duration,
        one_time_cost=round(one_time, 2),
        recurring_monthly_cost=round(recurring, 2),
        low_estimate=round(expected * 0.85, 2),
        expected_estimate=round(expected, 2),
        high_estimate=round(expected * 1.2, 2),
        confidence=confidence,
        status="等待確認",
        assumptions=assumptions,
        sources=[
            {
                "label": "情境描述",
                "value": "由使用者自然語言整理",
                "source": "使用者輸入",
                "estimated": False,
            },
            {
                "label": "時間與金額",
                "value": "確認前皆為估算值",
                "source": "AI 推估",
                "estimated": True,
            },
        ],
    )


def deterministic_parse_scenario(req: ScenarioParseRequest) -> ParsedScenario:
    text = req.text.lower()
    events = []
    adjustments = []
    warnings = ["目前使用本機關鍵字解析。"]

    if "taipei" in text or "台北" in text or "move" in text or "搬家" in text:
        adjustments.append(
            {
                "category": "transportation",
                "start_month": min(6, req.months),
                "multiplier": 1.2,
                "monthly_amount": 0,
                "reason": "搬遷可能提高交通成本",
                "end_month": req.months,
                "source": "AI 推估",
            }
        )
        events.append(
            {
                "type": "life_event",
                "name": "搬家",
                "description": "搬家的一次性安置費用",
                "start_month": min(6, req.months),
                "one_time_amount": -30000,
                "source": EventSource.ai.value,
                "display_source": "AI 推估",
                "reason": "搬家的一次性安置費用",
            }
        )
    if "gym" in text or "健身" in text:
        adjustments.append(
            {
                "category": "medical",
                "start_month": min(6, req.months),
                "multiplier": 1.0,
                "monthly_amount": 1500,
                "reason": "健身房月費",
                "end_month": req.months,
                "source": "AI 推估",
            }
        )
    if "japan" in text or "travel" in text or "日本" in text or "旅行" in text or "旅遊" in text:
        travel_month = min(12, req.months)
        events.extend(
            [
                {
                    "type": "life_event",
                    "name": "旅行機票與住宿",
                    "description": "預計的機票與住宿支出",
                    "start_month": travel_month,
                    "one_time_amount": -24000,
                    "target_expense_category": "travel",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "機票與住宿",
                },
                {
                    "type": "life_event",
                    "name": "旅遊期間餐飲",
                    "start_month": travel_month,
                    "category_monthly_adjustment": 6000,
                    "target_expense_category": "food",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "旅遊期間餐飲增加",
                },
                {
                    "type": "life_event",
                    "name": "原日常餐飲抵銷",
                    "start_month": travel_month,
                    "category_monthly_adjustment": -2000,
                    "target_expense_category": "food",
                    "expense_role": "offset",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "旅遊期間原本日常餐飲減少",
                },
                {
                    "type": "life_event",
                    "name": "旅遊交通",
                    "start_month": travel_month,
                    "category_monthly_adjustment": 1200,
                    "target_expense_category": "transportation",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "機場與當地交通，與日常通勤分開",
                },
            ]
        )
    if "buy a car" in text or "car loan" in text or "買車" in text or "車貸" in text:
        car_month = min(6, req.months)
        car_end = min(req.months, car_month + 59)
        events.extend(
            [
                {
                    "type": "life_event",
                    "name": "購車頭期款",
                    "start_month": car_month,
                    "one_time_amount": -200000,
                    "target_expense_category": "transportation",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "購車一次性頭期款",
                },
                {
                    "type": "life_event",
                    "name": "車貸",
                    "start_month": car_month,
                    "end_month": car_end,
                    "monthly_amount": -12000,
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "車貸本金與利息",
                },
                {
                    "type": "life_event",
                    "name": "燃油",
                    "start_month": car_month,
                    "end_month": req.months,
                    "category_monthly_adjustment": 3000,
                    "target_expense_category": "transportation",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "每月燃油費",
                },
                {
                    "type": "life_event",
                    "name": "停車",
                    "start_month": car_month,
                    "end_month": req.months,
                    "category_monthly_adjustment": 2000,
                    "target_expense_category": "transportation",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "每月停車費",
                },
                {
                    "type": "life_event",
                    "name": "保險與稅金",
                    "start_month": car_month,
                    "end_month": req.months,
                    "category_monthly_adjustment": 2500,
                    "target_expense_category": "other",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "車輛保險與稅金月平均",
                },
                {
                    "type": "life_event",
                    "name": "車輛維護",
                    "start_month": car_month,
                    "end_month": req.months,
                    "category_monthly_adjustment": 1500,
                    "target_expense_category": "transportation",
                    "source": EventSource.ai.value,
                    "display_source": "AI 推估",
                    "reason": "保養與維修月平均",
                },
            ]
        )
    if "change job" in text or "new job" in text or "換工作" in text or "轉職" in text:
        events.append(
            {
                "type": "salary_change",
                "name": "換工作",
                "description": "工作變動帶來的收入調整",
                "start_month": min(6, req.months),
                "income_multiplier": 1.1,
                "source": EventSource.ai.value,
                "display_source": "AI 推估",
                "reason": "換工作後收入調整",
            }
        )
    if not events and not adjustments:
        warnings.append("找不到明確的財務情境，請補充時間與金額。")

    confidence = 0.55 if events or adjustments else 0.25
    return ParsedScenario(
        summary="已整理出一份情境草稿。",
        expense_adjustments=adjustments,
        events=events,
        confidence=confidence,
        warnings=warnings,
        display=_scenario_display(
            events=events,
            adjustments=adjustments,
            confidence=confidence,
            months=req.months,
        )
        if events or adjustments
        else None,
    )


def parse_scenario(req: ScenarioParseRequest) -> ParsedScenario:
    provider = get_ai_provider()
    if provider is None:
        return deterministic_parse_scenario(req)
    system = (
        "Return strict JSON for a personal finance scenario parser. "
        "Do not calculate financial results. Output only structured parameters for review. "
        "If the input is off-topic, nonsensical, or has no financial scenario, return empty "
        "events and expense_adjustments, low confidence, and a concise warning in Traditional Chinese."
    )
    try:
        raw: Dict[str, Any] = provider.complete_json(system=system, user=req.text)
        parsed = ParsedScenario.model_validate(raw)
        if parsed.display is None and (parsed.events or parsed.expense_adjustments):
            parsed.display = _scenario_display(
                events=[item.model_dump() for item in parsed.events],
                adjustments=[item.model_dump() for item in parsed.expense_adjustments],
                confidence=parsed.confidence,
                months=req.months,
            )
        return parsed
    except (RuntimeError, ValidationError, KeyError, ValueError):
        return deterministic_parse_scenario(req)
