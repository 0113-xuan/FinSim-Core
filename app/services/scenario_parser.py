from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import ValidationError

from app.schemas import EventSource, ParsedScenario, ScenarioClarification, ScenarioContext, ScenarioParseRequest
from app.core.events import calculate_loan_payment
from app.services.ai_provider import (
    AIProviderError,
    UnsupportedAIProviderOperation,
    get_ai_provider,
)
from app.services.financial_answer_extraction import deterministic_financial_extraction
from app.services.scenario_bridge import build_housing_scenario_request, build_vehicle_scenario_request
from app.services.financial_amount import FINANCIAL_AMOUNT_PATTERN, parse_financial_amount
from app.services.calendar_period import (
    YearMonth,
    extract_date_text,
    normalize_date_text,
    period_for_simulation_month,
    resolve_reference_date,
    simulation_month_for_period,
)


logger = logging.getLogger(__name__)
LEGACY_VEHICLE_MAINTENANCE_MONTHLY = Decimal("1500")
LEGACY_VEHICLE_MAINTENANCE_ANNUAL = LEGACY_VEHICLE_MAINTENANCE_MONTHLY * Decimal(12)


@dataclass(frozen=True)
class InsuranceAffordabilityPolicy:
    candidate_cashflow_shares: tuple[Decimal, ...] = (
        Decimal("0.25"), Decimal("0.50"), Decimal("0.75")
    )
    minimum_candidate: Decimal = Decimal("500")
    comparison_months: int = 60


INSURANCE_AFFORDABILITY_POLICY = InsuranceAffordabilityPolicy()


def _scenario_display(
    *,
    events: List[Dict[str, Any]],
    adjustments: List[Dict[str, Any]],
    confidence: float,
    months: int,
    timing_source: str | None = None,
    extra_assumptions: List[Dict[str, Any]] | None = None,
    reference_date: date | None = None,
    original_target_date_text: str | None = None,
) -> ScenarioContext:
    reference_date = reference_date or date.today()
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
    start_period = period_for_simulation_month(start_month, reference_date)
    end_period = period_for_simulation_month(end_month, reference_date)
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
    event_sources = {
        getattr(item.get("source"), "value", item.get("source"))
        for item in [*events, *adjustments]
    }
    interpretation_source = (
        "系統模擬假設"
        if EventSource.system_assumption.value in event_sources
        else "AI 語意解析"
        if EventSource.ai.value in event_sources
        else "系統計算"
    )
    assumptions = [
        {
            "key": "timing",
            "label": "發生時間",
            "value": f"{start_period.replace('-', '年')}月開始",
            "suggested_value": f"{start_period.replace('-', '年')}月開始",
            "source": timing_source or interpretation_source,
            "editable": True,
        },
        {
            "key": "duration",
            "label": "持續期間",
            "value": f"{duration} 個月",
            "suggested_value": f"{duration} 個月",
            "source": interpretation_source,
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
                "source": "系統模擬假設",
                "editable": True,
            }
        )
    assumptions.extend(extra_assumptions or [])
    return ScenarioContext(
        id=f"scenario-{start_month}-{len(events)}-{len(adjustments)}",
        title="、".join(titles[:3]) or "AI 建立的財務情境",
        scenario_type="複合生活事件" if len(titles) > 1 else (titles[0] if titles else "生活事件"),
        start_month=start_month,
        start_period=start_period,
        end_period=end_period,
        original_target_date_text=original_target_date_text,
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
                "source": interpretation_source,
                "estimated": True,
            },
        ],
    )


def _clarification_result(
    *,
    intent: str,
    summary: str,
    known_values: List[Dict[str, str]],
    missing_fields: List[str],
    questions: List[str],
    fallback_reason: str,
    system_assumption_offer: str,
    candidates: List[Dict[str, Any]] | None = None,
) -> ParsedScenario:
    return ParsedScenario(
        summary=summary,
        expense_adjustments=[],
        events=[],
        confidence=0.95,
        warnings=[],
        display=None,
        provider_used=False,
        fallback_used=True,
        fallback_type="deterministic_clarification",
        fallback_reason=fallback_reason,
        clarification={
            "intent": intent,
            "summary": summary,
            "known_values": known_values,
            "candidates": candidates or [],
            "missing_fields": missing_fields,
            "questions": questions,
            "system_assumption_offer": system_assumption_offer,
        },
    )


def _request_reference_date(req: ScenarioParseRequest) -> date:
    return resolve_reference_date(req.reference_date, req.timezone)


def _vehicle_month_index(normalized_target_date: str, reference_date: date) -> int:
    return simulation_month_for_period(normalized_target_date, reference_date)


def _vehicle_clarification_or_scenario(
    req: ScenarioParseRequest,
    *,
    fallback_reason: str,
) -> ParsedScenario | None:
    if re.search(
        r"(?:搬家|搬到|旅行|旅遊|健身|換工作|轉職|move|travel|gym|change job)",
        req.text,
        re.IGNORECASE,
    ):
        return None
    reference_date = _request_reference_date(req)
    extraction = deterministic_financial_extraction(req.text, current_date=reference_date)
    if extraction is None or not extraction.future_plans:
        return None
    plan = extraction.future_plans[0]
    if plan.plan_type.value != "vehicle_purchase":
        return None

    known_values: List[Dict[str, str]] = []
    if plan.estimated_cost is not None:
        known_values.append({
            "key": "purchase_price",
            "label": "購車價格",
            "value": f"NT${plan.estimated_cost:,.0f}",
            "source": "使用者提供",
        })
    if plan.original_target_date_text:
        known_values.append({
            "key": "timing",
            "label": "預計時間",
            "value": plan.original_target_date_text,
            "source": "使用者提供",
        })
        known_values.append({
            "key": "normalized_timing",
            "label": "實際年月",
            "value": f"{plan.normalized_target_date.replace('-', '年')}月",
            "source": "系統計算",
        })
    if "二手" in req.text:
        known_values.append({
            "key": "vehicle_condition", "label": "車況", "value": "二手車", "source": "使用者提供"
        })
    if plan.down_payment is not None:
        known_values.append({
            "key": "down_payment",
            "label": "頭期款",
            "value": f"NT${plan.down_payment:,.0f}",
            "source": "使用者提供",
        })
    financing = plan.financing
    if financing and financing.loan_amount is not None:
        known_values.append({
            "key": "loan_amount",
            "label": "貸款金額",
            "value": f"NT${financing.loan_amount:,.0f}",
            "source": "使用者提供",
        })
    if financing and financing.loan_term_months is not None:
        known_values.append({
            "key": "loan_term",
            "label": "貸款期數",
            "value": f"{financing.loan_term_months} 期",
            "source": "使用者提供",
        })
    if financing and financing.annual_interest_rate is not None:
        known_values.append({
            "key": "interest_rate",
            "label": "年利率",
            "value": f"{financing.annual_interest_rate:g}%",
            "source": "使用者提供",
        })

    missing: List[str] = []
    questions: List[str] = []
    direct_spend = re.search(
        rf"(?:拿|花|用)\s*{FINANCIAL_AMOUNT_PATTERN}(?:元|塊)?[^，。]{{0,8}}買",
        req.text,
    )
    cash_purchase = bool(
        re.search(r"(?:現金|一次付清|全額現金)", req.text)
        or (direct_spend and financing is None)
    )
    if cash_purchase:
        known_values.append({
            "key": "payment_method", "label": "付款方式", "value": "現金一次付清", "source": "使用者提供"
        })
    if plan.estimated_cost is None:
        missing.append("purchase_price")
    if plan.normalized_target_date is None:
        missing.append("timing")
    if plan.estimated_cost is None and plan.normalized_target_date is None:
        questions.append("預計什麼時候買車？")
    else:
        if plan.estimated_cost is None:
            questions.append("購車預算或預計車價是多少？")
        if plan.normalized_target_date is None:
            questions.append("預計什麼時候買車？")
        if financing is None and not cash_purchase:
            missing.extend(["payment_method", "down_payment", "loan_term", "interest_rate"])
            questions.extend([
                "會用現金一次付清，還是辦理貸款？",
                "若貸款，頭期款、貸款期數與年利率各是多少？",
            ])
        elif financing is not None:
            if plan.down_payment is None and financing.loan_amount is None:
                missing.append("down_payment")
                questions.append("頭期款預計多少？")
            if financing.loan_term_months is None:
                missing.append("loan_term")
                questions.append("預計貸款幾期？")
            if financing.annual_interest_rate is None:
                missing.append("interest_rate")
                questions.append("車貸年利率是多少？")
    missing = list(dict.fromkeys(missing))

    if missing:
        return _clarification_result(
            intent="vehicle_purchase",
            summary="已辨識為購車計畫，尚未建立或儲存模擬事件。",
            known_values=known_values,
            missing_fields=missing,
            questions=questions,
            fallback_reason=fallback_reason,
            system_assumption_offer=(
                "缺少的持有成本可選擇使用系統模擬假設；年度預算換算與其他假設不會寫入已確認的財務資料。"
            ),
        )

    start_month = min(_vehicle_month_index(plan.normalized_target_date, reference_date), req.months)
    start_period = plan.normalized_target_date
    events: List[Dict[str, Any]] = []
    extra_assumptions: List[Dict[str, Any]] = []
    if cash_purchase:
        events.append({
            "type": "life_event",
            "name": "購車款",
            "start_month": start_month,
            "start_period": start_period,
            "one_time_amount": -float(plan.estimated_cost),
            "target_expense_category": "transportation",
            "source": EventSource.manual.value,
            "display_source": "使用者提供",
            "reason": "使用者表示以現金一次付清",
        })
    else:
        if financing.loan_amount is None:
            principal = Decimal(str(plan.estimated_cost)) - Decimal(str(plan.down_payment or 0))
            principal_source = "系統計算"
        else:
            principal = Decimal(str(financing.loan_amount))
            principal_source = "使用者提供"
        if plan.down_payment:
            events.append({
                "type": "life_event",
                "name": "購車頭期款",
                "start_month": start_month,
                "start_period": start_period,
                "one_time_amount": -float(plan.down_payment),
                "target_expense_category": "transportation",
                "source": EventSource.manual.value,
                "display_source": "使用者提供",
                "reason": "使用者提供的購車頭期款",
            })
        monthly_payment = calculate_loan_payment(
            float(principal),
            float(Decimal(str(financing.annual_interest_rate)) / Decimal(100)),
            financing.loan_term_months,
        )
        events.append({
            "type": "life_event",
            "name": "車貸",
            "start_month": start_month,
            "start_period": start_period,
            "end_month": min(req.months, start_month + financing.loan_term_months - 1),
            "monthly_amount": -monthly_payment,
            "source": EventSource.system.value,
            "display_source": "系統計算",
            "reason": f"依本金、{financing.loan_term_months} 期與年利率計算",
        })
        extra_assumptions.append({
            "key": "vehicle_loan_principal",
            "label": "車貸本金",
            "value": f"NT${principal:,.0f}",
            "suggested_value": f"NT${principal:,.0f}",
            "source": principal_source,
            "editable": True,
        })

    maintenance_monthly = LEGACY_VEHICLE_MAINTENANCE_ANNUAL / Decimal(12)
    events.append({
        "type": "life_event",
        "name": "車輛維護規劃平均",
        "start_month": start_month,
        "start_period": start_period,
        "end_month": req.months,
        "category_monthly_adjustment": float(maintenance_monthly),
        "target_expense_category": "transportation",
        "source": EventSource.system_assumption.value,
        "display_source": "系統模擬假設",
        "assumption_key": "legacy_vehicle_maintenance_annual_budget",
        "reason": "舊版年度維護預算除以 12 的規劃平均，不代表每月實際保養",
    })
    extra_assumptions.extend([
        {
            "key": "vehicle_maintenance_annual_budget",
            "label": "車輛年度維護預算",
            "value": f"NT${LEGACY_VEHICLE_MAINTENANCE_ANNUAL:,.0f} / 年",
            "suggested_value": f"NT${LEGACY_VEHICLE_MAINTENANCE_ANNUAL:,.0f} / 年",
            "source": "系統模擬假設",
            "editable": True,
        },
        {
            "key": "vehicle_maintenance_monthly_average",
            "label": "維護費每月規劃平均",
            "value": f"NT${maintenance_monthly:,.0f} / 月（年度預算 ÷ 12）",
            "suggested_value": f"NT${maintenance_monthly:,.0f} / 月",
            "source": "系統計算",
            "editable": False,
        },
    ])
    display = _scenario_display(
        events=events,
        adjustments=[],
        confidence=0.95,
        months=req.months,
        timing_source="使用者提供",
        extra_assumptions=extra_assumptions,
        reference_date=reference_date,
        original_target_date_text=plan.original_target_date_text,
    )
    typed_request = build_vehicle_scenario_request(
        scenario_id="vehicle-purchase", target_period=start_period, horizon_months=req.months,
        original_text=req.text, purchase_price=Decimal(str(plan.estimated_cost)),
        payment_method="cash" if cash_purchase else "financed",
        down_payment=Decimal(str(plan.down_payment)) if plan.down_payment is not None else None,
        explicit_loan_amount=Decimal(str(financing.loan_amount)) if financing and financing.loan_amount is not None else None,
        loan_term_months=financing.loan_term_months if financing else None,
        annual_interest_rate_percent=Decimal(str(financing.annual_interest_rate)) if financing and financing.annual_interest_rate is not None else None,
        vehicle_condition="used" if "二手" in req.text else "unknown",
    )
    legacy_clarification = None
    if cash_purchase:
        legacy_clarification = ScenarioClarification(
            intent="vehicle_purchase",
            summary="已辨識為現金購車計畫；持有成本仍可稍後補充，不影響購車比較。",
            known_values=known_values,
            missing_fields=["insurance", "tax", "fuel_or_electricity", "parking", "annual_maintenance"],
            questions=["可稍後提供保險、稅費、油電、停車與年度維護預算。"],
            system_assumption_offer="未提供的持有成本不會自動加入比較。",
        )
    return ParsedScenario(
        summary="已依使用者提供的購車資料建立情境草稿。",
        events=events,
        expense_adjustments=[],
        confidence=0.95,
        warnings=["維護費是年度預算的每月規劃平均，不代表每月實際保養。"],
        display=display,
        provider_used=False,
        fallback_used=True,
        fallback_type="deterministic_vehicle_adapter",
        fallback_reason=fallback_reason,
        typed_scenario_request=typed_request.model_dump(mode="json"),
        clarification=legacy_clarification,
    )


def _relocation_clarification(
    req: ScenarioParseRequest,
    *,
    fallback_reason: str,
) -> ParsedScenario | None:
    if not re.search(r"(?:搬家|搬到|搬去|換住處|換房)", req.text):
        return None
    reference_date = _request_reference_date(req)
    target_text = extract_date_text(req.text)
    target_period = normalize_date_text(target_text, reference_date) if target_text else None

    def amount(pattern: str) -> Decimal | None:
        match = re.search(
            pattern + rf"[^零一二兩三四五六七八九十百千萬\d]{{0,8}}(?P<amount>{FINANCIAL_AMOUNT_PATTERN})(?:元|塊)?",
            req.text,
        )
        if not match:
            return None
        try:
            return parse_financial_amount(match.group("amount")).value
        except ValueError:
            return None

    rent_terms = r"(?:房租|租金|租屋費|每月租金)"
    commute_terms = r"(?:交通費|通勤費?|通勤成本|車資)"
    increase_terms = r"(?:增加|多花|多|上升|變貴|提高)"
    decrease_terms = r"(?:減少|少|省|降低|變便宜)"
    current_rent = amount(r"(?:目前|現在|原本)\s*(?:房租|租金|租屋費)")
    new_rent = amount(r"(?:新房租|新租金|新租屋費)")
    rent_increase = amount(rent_terms + r"[^，。]{0,12}" + increase_terms)
    rent_decrease = amount(rent_terms + r"[^，。]{0,12}" + decrease_terms)
    if re.search(r"(?:新房租|新租金|新租屋費)[^，。]{0,12}" + increase_terms, req.text):
        new_rent = None
    deposit = amount(r"押金")
    moving_cost = amount(r"搬家費")
    commute_saving = amount(commute_terms + r"[^，。]{0,12}" + decrease_terms)
    commute_increase = amount(commute_terms + r"[^，。]{0,12}" + increase_terms)
    if rent_increase is None and current_rent is not None and new_rent is not None:
        rent_increase = new_rent - current_rent
    if rent_decrease is not None:
        rent_increase = -rent_decrease
    commute_change = -commute_saving if commute_saving is not None else commute_increase

    known: List[Dict[str, str]] = []
    if target_period:
        known.append({"key": "timing", "label": "搬家時間", "value": f"{target_period.replace('-', '年')}月（原文：{target_text}）", "source": "系統計算"})
    if current_rent is not None:
        known.append({"key": "current_rent", "label": "目前房租", "value": f"NT${current_rent:,.0f}", "source": "使用者提供"})
    if new_rent is not None:
        known.append({"key": "new_rent", "label": "新房租", "value": f"NT${new_rent:,.0f}", "source": "使用者提供"})
    if rent_increase is not None:
        sign = "+" if rent_increase >= 0 else "-"
        known.append({"key": "rent_change", "label": "每月房租變化", "value": f"{sign}NT${abs(rent_increase):,.0f}", "source": "使用者提供"})
    if commute_change is not None:
        sign = "+" if commute_change > 0 else "-"
        known.append({"key": "commute_change", "label": "每月交通費變化", "value": f"{sign}NT${abs(commute_change):,.0f}", "source": "使用者提供"})
    if rent_increase is not None and commute_change is not None:
        net_expense = rent_increase + commute_change
        cashflow = -net_expense
        sign = "+" if cashflow > 0 else "-"
        known.append({"key": "net_cash_flow", "label": "每月淨現金流影響", "value": f"{sign}NT${abs(cashflow):,.0f}", "source": "系統計算"})
    if deposit is not None:
        known.append({"key": "deposit", "label": "押金", "value": f"NT${deposit:,.0f}", "source": "使用者提供"})
    if moving_cost is not None:
        known.append({"key": "moving_cost", "label": "搬家費", "value": f"NT${moving_cost:,.0f}", "source": "使用者提供"})

    missing: List[str] = []
    questions: List[str] = []
    if target_period is None:
        missing.append("timing")
        questions.append("預計什麼時候搬家？")
    if rent_increase is None:
        missing.extend(["current_rent", "new_rent"])
        questions.extend(["目前房租是多少？", "新房租大約多少？"])
    if deposit is None and moving_cost is None:
        missing.append("one_time_costs")
        questions.append("是否有押金、仲介費或搬家費？若未知可先保留未知。")
    if commute_change is None:
        missing.append("commuting_cost_change")
        questions.append("搬家後每月通勤費預計增加或減少多少？")

    if missing:
        return _clarification_result(
            intent="relocation",
            summary="已辨識為搬家計畫；已知的房租與交通變化會分開保留。",
            known_values=known,
            missing_fields=list(dict.fromkeys(missing)),
            questions=questions,
            fallback_reason=fallback_reason,
            system_assumption_offer="一次性費用可保留未知、輸入實際金額，或另行選擇清楚標示的系統模擬假設。",
        )

    start_month = min(simulation_month_for_period(target_period, reference_date), req.months)
    end_period = period_for_simulation_month(req.months, reference_date)
    events: List[Dict[str, Any]] = []
    if deposit is not None:
        events.append({
            "type": "life_event", "name": "租屋押金", "start_month": start_month,
            "start_period": target_period, "one_time_amount": -float(deposit),
            "source": EventSource.manual.value, "display_source": "使用者提供",
            "reason": "使用者提供的押金",
        })
    if moving_cost is not None:
        events.append({
            "type": "life_event", "name": "搬家費", "start_month": start_month,
            "start_period": target_period, "one_time_amount": -float(moving_cost),
            "source": EventSource.manual.value, "display_source": "使用者提供",
            "reason": "使用者提供的搬家費",
        })
    adjustments = [
        {"category": "other", "start_month": start_month, "end_month": req.months,
         "start_period": target_period, "end_period": end_period, "monthly_amount": float(rent_increase),
         "reason": "每月房租增加", "source": "user_provided"},
        {"category": "transportation", "start_month": start_month, "end_month": req.months,
         "start_period": target_period, "end_period": end_period, "monthly_amount": float(commute_change),
         "expense_role": "offset" if commute_change < 0 else "additional",
         "reason": "每月通勤費變化", "source": "user_provided"},
    ]
    typed_request = build_housing_scenario_request(
        scenario_id="housing-change", target_period=target_period, horizon_months=req.months,
        original_text=req.text, current_rent=current_rent, new_rent=new_rent,
        monthly_rent_change=None if current_rent is not None and new_rent is not None else rent_increase,
        monthly_commute_change=commute_change, deposit=deposit, moving_cost=moving_cost,
    )
    return ParsedScenario(
        summary="已依使用者提供的搬家日期、房租、交通與一次性費用建立情境草稿。",
        events=events, expense_adjustments=adjustments, confidence=0.98, warnings=[],
        display=_scenario_display(events=events, adjustments=adjustments, confidence=0.98,
                                  months=req.months, reference_date=reference_date,
                                  original_target_date_text=target_text,
                                  timing_source="系統計算"),
        provider_used=False, fallback_used=True, fallback_type="deterministic_relocation_adapter",
        fallback_reason=fallback_reason,
        typed_scenario_request=typed_request.model_dump(mode="json"),
    )


def _insurance_result(
    req: ScenarioParseRequest,
    *,
    confirmed_profile: Dict[str, Any] | None,
    fallback_reason: str,
) -> ParsedScenario | None:
    if not re.search(r"(?:保險|保費)", req.text):
        return None
    reference_date = _request_reference_date(req)
    target_text = extract_date_text(req.text)
    target_period = normalize_date_text(target_text, reference_date) if target_text else None
    insurance_type_match = re.search(r"(醫療保險|醫療險|壽險|意外險|失能險|重大傷病險|車險|旅平險)", req.text)
    insurance_type = insurance_type_match.group(1) if insurance_type_match else None
    monthly_match = re.search(r"每月(?:保費)?(?:繳|付)?\s*([\d,]+)", req.text)
    annual_match = re.search(r"(?:一年|每年|年繳|年保費)[^\d]{0,8}([\d,]+)", req.text)
    candidate_segment = re.search(r"每月保費([^，。？?]+)", req.text)
    listed = [
        Decimal(item.replace(",", ""))
        for item in re.findall(r"\d[\d,]*", candidate_segment.group(1) if candidate_segment else "")
    ]
    monthly_premium = Decimal(monthly_match.group(1).replace(",", "")) if monthly_match else None
    annual_premium = Decimal(annual_match.group(1).replace(",", "")) if annual_match else None
    if annual_premium is not None:
        monthly_premium = (annual_premium / Decimal(12)).quantize(Decimal("0.01"))

    known: List[Dict[str, str]] = []
    if insurance_type:
        known.append({"key": "insurance_type", "label": "保險類型", "value": insurance_type, "source": "使用者提供"})
    if annual_premium is not None:
        known.extend([
            {"key": "annual_premium", "label": "原始年繳保費", "value": f"NT${annual_premium:,.0f}", "source": "使用者提供"},
            {"key": "monthly_average", "label": "每月規劃平均", "value": f"NT${monthly_premium:,.0f}", "source": "系統計算"},
        ])
    elif monthly_premium is not None:
        known.append({"key": "monthly_premium", "label": "每月保費", "value": f"NT${monthly_premium:,.0f}", "source": "使用者提供"})
    if target_period:
        known.append({"key": "timing", "label": "開始時間", "value": f"{target_period.replace('-', '年')}月（原文：{target_text}）", "source": "系統計算"})

    affordability_intent = bool(re.search(r"(?:負擔得起|能負擔|合理範圍|不知道.*多少|比較)", req.text))
    if affordability_intent:
        candidate_specs: List[tuple[Decimal, str]] = []
        if len(listed) >= 2:
            candidate_specs = [(value, "user_provided") for value in list(dict.fromkeys(listed))[:6]]
        elif confirmed_profile:
            disposable = Decimal(str(confirmed_profile.get("salary", 0))) - Decimal(str(confirmed_profile.get("fixed_expense", 0))) - Decimal(str(confirmed_profile.get("variable_expense", 0)))
            known.append({"key": "disposable_cash_flow", "label": "目前每月可支配現金流", "value": f"NT${disposable:,.0f}", "source": "系統計算"})
            if disposable > 0:
                candidate_specs = [
                    (max(INSURANCE_AFFORDABILITY_POLICY.minimum_candidate, (disposable * share).quantize(Decimal("1"))), "system_assumption")
                    for share in INSURANCE_AFFORDABILITY_POLICY.candidate_cashflow_shares
                ]
        requests_system_option = bool(re.search(r"系統[^，。]{0,12}(?:加|提供|產生|其他方案)", req.text))
        if requests_system_option and listed:
            unique = list(dict.fromkeys(listed))
            generated = (min(unique) + max(unique)) / Decimal(2)
            if generated in unique:
                generated = max(unique) + INSURANCE_AFFORDABILITY_POLICY.minimum_candidate
            candidate_specs.append((generated.quantize(Decimal("1")), "system_assumption"))

        structured_candidates: List[Dict[str, Any]] = []
        if candidate_specs:
            known.append({"key": "baseline", "label": "基準情境", "value": "不新增保費（NT$0）", "source": "系統計算"})
            for index, (candidate, source) in enumerate(candidate_specs, start=1):
                display_source = "使用者提供" if source == "user_provided" else "系統模擬假設"
                known.append({"key": f"premium_candidate_{index}", "label": f"保費候選 {index}", "value": f"每月 NT${candidate:,.0f}", "source": display_source})
                structured_candidates.append({
                    "id": f"insurance-option-{index}",
                    "label": f"保費方案 {index}",
                    "monthly_amount": float(candidate),
                    "source": source,
                    "display_source": display_source,
                    "comparison_months": INSURANCE_AFFORDABILITY_POLICY.comparison_months,
                    "derived_total": float(candidate * INSURANCE_AFFORDABILITY_POLICY.comparison_months),
                    "derived_source": "derived",
                    "derived_display_source": "系統計算",
                })
        questions = []
        missing = []
        if not insurance_type:
            questions.append("想評估哪一類保險？")
            missing.append("insurance_type")
        if not confirmed_profile:
            questions.append("請先補充每月收入、必要支出、債務付款與可動用存款，才能比較可負擔範圍。")
            missing.extend(["monthly_income", "necessary_expenses", "debt_payments", "liquid_savings"])
        if target_period is None:
            questions.append("預計從什麼時候開始投保？")
            missing.append("timing")
        if not questions:
            questions.append("請確認要比較哪些候選保費。")
        return _clarification_result(
            intent="insurance_purchase",
            summary="已辨識為保險保費負擔能力評估；候選金額只用來比較現金流，不代表投保建議。",
            known_values=known,
            missing_fields=list(dict.fromkeys(missing)),
            questions=questions,
            fallback_reason=fallback_reason,
            system_assumption_offer="使用者輸入的候選值維持「使用者提供」；只有系統另產生的方案標示為「系統模擬假設」。此階段不評估保障內容或理賠價值。",
            candidates=structured_candidates,
        )

    if monthly_premium is None or target_period is None:
        missing = []
        questions = []
        if monthly_premium is None:
            missing.append("premium_amount")
            questions.append("保費金額是多少？也可以改為評估可負擔範圍。")
        if target_period is None:
            missing.append("timing")
            questions.append("預計從什麼時候開始投保？")
        if not insurance_type:
            missing.append("insurance_type")
            questions.append("想評估哪一類保險？")
        return _clarification_result(
            intent="insurance_purchase", summary="已辨識為保險支出計畫。", known_values=known,
            missing_fields=missing, questions=questions, fallback_reason=fallback_reason,
            system_assumption_offer="年繳轉每月平均由後端計算，不會改寫原始年繳金額。",
        )

    start_month = min(simulation_month_for_period(target_period, reference_date), req.months)
    events = [{
        "type": "life_event", "name": insurance_type or "保險保費", "start_month": start_month,
        "start_period": target_period, "end_month": req.months,
        "end_period": period_for_simulation_month(req.months, reference_date),
        "monthly_amount": -float(monthly_premium), "source": EventSource.manual.value,
        "display_source": "使用者提供" if annual_premium is None else "系統計算",
        "reason": "保費對每月現金流的影響",
    }]
    return ParsedScenario(
        summary="已建立保費現金流情境；不包含保障內容或理賠價值判斷。", events=events,
        expense_adjustments=[], confidence=0.98, warnings=["此情境只比較保費現金流，不代表保險一定值得購買。"],
        display=_scenario_display(events=events, adjustments=[], confidence=0.98, months=req.months,
                                  reference_date=reference_date, original_target_date_text=target_text,
                                  timing_source="系統計算"),
        provider_used=False, fallback_used=True, fallback_type="deterministic_insurance_adapter",
        fallback_reason=fallback_reason,
    )


def _calendar_planning_clarification(
    req: ScenarioParseRequest,
    *,
    fallback_reason: str,
) -> ParsedScenario | None:
    reference_date = _request_reference_date(req)
    target_text = extract_date_text(req.text)
    target_period = normalize_date_text(target_text, reference_date) if target_text else None

    if re.search(r"(?:多存|增加儲蓄|提高儲蓄)", req.text):
        amount_match = re.search(r"(?:多存|增加儲蓄|提高儲蓄)[^\d]{0,8}([\d,]+)", req.text)
        known = []
        if target_period:
            known.append({"key": "timing", "label": "開始時間", "value": f"{target_period.replace('-', '年')}月", "source": "系統計算"})
        if amount_match:
            known.append({"key": "monthly_savings", "label": "每月增加儲蓄", "value": f"NT${Decimal(amount_match.group(1).replace(',', '')):,.0f}", "source": "使用者提供"})
        return _clarification_result(
            intent="savings_change", summary="已辨識為每月儲蓄調整；儲蓄是資產移轉，不會直接當成消費。",
            known_values=known, missing_fields=["funding_source"],
            questions=["這筆增加儲蓄來自收入增加，還是其他支出減少？"], fallback_reason=fallback_reason,
            system_assumption_offer="開始年月由後端依使用者原文換算，不使用第幾個月的預設。",
        )

    if re.search(r"(?:停工|暫停工作|工作空窗)", req.text):
        chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                   "七": 7, "八": 8, "九": 9, "十": 10}
        duration_match = re.search(r"(?:停工|暫停工作|工作空窗)[^，。]{0,8}?([一二三四五六七八九十]|\d+)個?月", req.text)
        duration = None
        if duration_match:
            raw = duration_match.group(1)
            duration = int(raw) if raw.isdigit() else chinese.get(raw)
        known = []
        if target_period:
            known.append({"key": "start_period", "label": "停工開始", "value": f"{target_period.replace('-', '年')}月", "source": "系統計算"})
        if target_period and duration:
            start = YearMonth.parse(target_period)
            end = start.add_months(duration - 1)
            known.extend([
                {"key": "duration", "label": "停工期間", "value": f"{duration} 個月", "source": "使用者提供"},
                {"key": "end_period", "label": "停工結束", "value": f"{end.year}年{end.month}月（含）", "source": "系統計算"},
            ])
        missing = []
        questions = []
        if not target_period:
            missing.append("timing")
            questions.append("預計從什麼時候開始停工？")
        if not duration:
            missing.append("duration")
            questions.append("預計停工幾個月？")
        missing.append("income_during_break")
        questions.append("停工期間每月預計還有多少收入？")
        return _clarification_result(
            intent="work_break", summary="已辨識為停工或工作空窗計畫。", known_values=known,
            missing_fields=missing, questions=questions, fallback_reason=fallback_reason,
            system_assumption_offer="結束年月採含首尾月份計算，未知收入不會自動設為零。",
        )

    if re.search(r"(?:換工作|轉職)", req.text):
        known = []
        missing = []
        questions = []
        if target_period:
            known.append({"key": "timing", "label": "預計時間", "value": f"{target_period.replace('-', '年')}月", "source": "系統計算"})
        else:
            missing.append("timing")
            questions.append("預計什麼時候換工作？")
        missing.append("income_change")
        questions.append("換工作後每月收入預計增加或減少多少？")
        return _clarification_result(
            intent="job_change", summary="已辨識為換工作計畫；時間不明時不會自動套用月份。",
            known_values=known, missing_fields=missing, questions=questions, fallback_reason=fallback_reason,
            system_assumption_offer="若要使用暫定日期，會清楚標示為系統模擬假設。",
        )
    return None


def deterministic_parse_scenario(
    req: ScenarioParseRequest,
    *,
    fallback_reason: str = "provider_unavailable",
    confirmed_profile: Dict[str, Any] | None = None,
) -> ParsedScenario:
    text = req.text.lower()
    events = []
    adjustments = []
    warnings = ["目前使用本機關鍵字解析。"]

    vehicle_result = _vehicle_clarification_or_scenario(
        req,
        fallback_reason=fallback_reason,
    )
    if vehicle_result is not None:
        return vehicle_result
    insurance_result = _insurance_result(
        req, confirmed_profile=confirmed_profile, fallback_reason=fallback_reason
    )
    if insurance_result is not None:
        return insurance_result
    calendar_result = _calendar_planning_clarification(req, fallback_reason=fallback_reason)
    if calendar_result is not None:
        return calendar_result
    relocation_result = _relocation_clarification(
        req,
        fallback_reason=fallback_reason,
    )
    if relocation_result is not None:
        return relocation_result

    if "taipei" in text or "台北" in text or "move" in text or "搬家" in text:
        adjustments.append(
            {
                "category": "transportation",
                "start_month": min(6, req.months),
                "multiplier": 1.2,
                "monthly_amount": 0,
                "reason": "搬遷可能提高交通成本",
                "end_month": req.months,
                "source": EventSource.system_assumption.value,
                "assumption_key": "legacy_move_transportation_multiplier",
            }
        )
        events.append(
            {
                "type": "life_event",
                "name": "搬家",
                "description": "搬家的一次性安置費用",
                "start_month": min(6, req.months),
                "one_time_amount": -30000,
                "source": EventSource.system_assumption.value,
                "display_source": "系統模擬假設",
                "assumption_key": "legacy_move_one_time_cost",
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
                "source": EventSource.system_assumption.value,
                "assumption_key": "legacy_gym_monthly_cost",
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
                    "source": EventSource.system_assumption.value,
                    "display_source": "系統模擬假設",
                    "assumption_key": "legacy_travel_one_time_cost",
                    "reason": "機票與住宿",
                },
                {
                    "type": "life_event",
                    "name": "旅遊期間餐飲",
                    "start_month": travel_month,
                    "category_monthly_adjustment": 6000,
                    "target_expense_category": "food",
                    "source": EventSource.system_assumption.value,
                    "display_source": "系統模擬假設",
                    "assumption_key": "legacy_travel_food_cost",
                    "reason": "旅遊期間餐飲增加",
                },
                {
                    "type": "life_event",
                    "name": "原日常餐飲抵銷",
                    "start_month": travel_month,
                    "category_monthly_adjustment": -2000,
                    "target_expense_category": "food",
                    "expense_role": "offset",
                    "source": EventSource.system_assumption.value,
                    "display_source": "系統模擬假設",
                    "assumption_key": "legacy_travel_food_offset",
                    "reason": "旅遊期間原本日常餐飲減少",
                },
                {
                    "type": "life_event",
                    "name": "旅遊交通",
                    "start_month": travel_month,
                    "category_monthly_adjustment": 1200,
                    "target_expense_category": "transportation",
                    "source": EventSource.system_assumption.value,
                    "display_source": "系統模擬假設",
                    "assumption_key": "legacy_travel_transportation_cost",
                    "reason": "機場與當地交通，與日常通勤分開",
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
                "source": EventSource.system_assumption.value,
                "display_source": "系統模擬假設",
                "assumption_key": "legacy_job_change_income_multiplier",
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
        provider_used=False,
        fallback_used=True,
        fallback_type="deterministic_system_assumptions",
        fallback_reason=fallback_reason,
    )


def parse_scenario(
    req: ScenarioParseRequest,
    *,
    confirmed_profile: Dict[str, Any] | None = None,
) -> ParsedScenario:
    deterministic = deterministic_parse_scenario(
        req,
        fallback_reason="deterministic_supported_intent",
        confirmed_profile=confirmed_profile,
    )
    if re.search(r"[\u4e00-\u9fff]", req.text) and (
        deterministic.clarification is not None or deterministic.fallback_type in {
        "deterministic_vehicle_adapter",
        "deterministic_relocation_adapter",
        "deterministic_insurance_adapter",
        }
    ):
        return deterministic
    provider = get_ai_provider()
    if provider is None:
        logger.info(
            "scenario parser provider=none operation=parse_scenario "
            "provider_used=false fallback_used=true error_type=provider_unavailable"
        )
        return deterministic_parse_scenario(
            req, fallback_reason="provider_unavailable", confirmed_profile=confirmed_profile
        )
    provider_name = type(provider).__name__.removesuffix("Provider").lower()
    system = (
        "Return strict JSON for a personal finance scenario parser. "
        "Do not calculate financial results. Output only structured parameters for review. "
        "If the input is off-topic, nonsensical, or has no financial scenario, return empty "
        "events and expense_adjustments, low confidence, and a concise warning in Traditional Chinese."
    )
    try:
        raw: Dict[str, Any] = provider.complete_json(system=system, user=req.text)
        parsed = ParsedScenario.model_validate(raw)
        parsed.provider_used = True
        parsed.fallback_used = False
        parsed.fallback_type = None
        parsed.fallback_reason = None
        if parsed.display is None and (parsed.events or parsed.expense_adjustments):
            parsed.display = _scenario_display(
                events=[item.model_dump() for item in parsed.events],
                adjustments=[item.model_dump() for item in parsed.expense_adjustments],
                confidence=parsed.confidence,
                months=req.months,
            )
        logger.info(
            "scenario parser provider=%s operation=parse_scenario "
            "provider_used=true fallback_used=false",
            provider_name,
        )
        return parsed
    except UnsupportedAIProviderOperation:
        error_type = "unsupported_operation"
    except AIProviderError:
        error_type = "provider_error"
    except (ValidationError, KeyError, ValueError, TypeError):
        error_type = "invalid_structured_output"
    except RuntimeError:
        error_type = "provider_error"
    logger.warning(
        "scenario parser provider=%s operation=parse_scenario "
        "provider_used=false fallback_used=true error_type=%s",
        provider_name,
        error_type,
    )
    return deterministic_parse_scenario(
        req, fallback_reason=error_type, confirmed_profile=confirmed_profile
    )
