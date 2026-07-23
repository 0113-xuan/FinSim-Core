from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.core.events import calculate_loan_payment
from app.core.simulation import simulate_finance
from app.core.transparency import display_source_label
from app.scenario_schemas import (
    HousingChangeScenarioInput,
    ScenarioBuildResult,
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
    ScenarioDelta,
    ScenarioFact,
    ScenarioOption,
    ScenarioOptionResult,
    ScenarioRequest,
    ValueSource,
    VehiclePurchaseScenarioInput,
)
from app.schemas import EventInput, EventSource, LoanInput
from app.services.calendar_period import YearMonth


MONEY = Decimal("0.01")
def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _fact(field: str, value: Decimal | None, source: ValueSource, reason: str) -> ScenarioFact:
    return ScenarioFact(
        field=field,
        value=_money(value) if value is not None else None,
        source=source,
        display_source=display_source_label(source),
        reason=reason,
    )


def find_baseline_option(options: list[ScenarioOption]) -> ScenarioOption:
    matches = [option for option in options if option.is_baseline]
    if not matches:
        raise ValueError("Scenario comparison is missing an explicit baseline")
    if len(matches) > 1:
        raise ValueError("Scenario comparison contains multiple baselines")
    return matches[0]


def _start_month(request: ScenarioRequest, start_period: YearMonth) -> int:
    difference = start_period.months_until(request.target_period)
    if difference <= 0:
        raise ValueError("target_period cannot be earlier than start_period")
    month = difference
    if month > request.horizon_months:
        raise ValueError("target_period falls outside the simulation horizon")
    return month


def _vehicle(request: ScenarioRequest, start_period: YearMonth) -> ScenarioBuildResult:
    payload = request.payload
    assert isinstance(payload, VehiclePurchaseScenarioInput)
    missing = list(request.missing_fields)
    warnings: list[str] = []
    derived: list[ScenarioFact] = []
    events: list[EventInput] = []
    loans: list[LoanInput] = []
    price = payload.purchase_price.value if payload.purchase_price else None
    if price is None:
        missing.append("purchase_price")
    elif price <= 0:
        raise ValueError("purchase_price must be greater than zero")
    start_month = _start_month(request, start_period)

    if payload.payment_method == "cash":
        if any((payload.down_payment, payload.explicit_loan_amount, payload.loan_term_months, payload.annual_interest_rate)):
            raise ValueError("cash purchase cannot include financing terms")
        if price is not None:
            events.append(EventInput(
                type="one_time", name="車輛現金購買", month=start_month,
                start_period=str(request.target_period), amount=-float(price),
                source=EventSource.manual, display_source=display_source_label(ValueSource.user_provided),
                reason="使用者提供的車輛購買價格",
            ))
    else:
        down = payload.down_payment.value if payload.down_payment else Decimal("0")
        if down < 0:
            raise ValueError("down_payment cannot be negative")
        if price is not None and down > price:
            raise ValueError("down_payment cannot exceed purchase_price")
        explicit = payload.explicit_loan_amount.value if payload.explicit_loan_amount else None
        principal = explicit
        if principal is None and price is not None:
            principal = price - down
            derived.append(_fact("loan_principal", principal, ValueSource.derived, "購買價格減去頭期款"))
        elif explicit is not None and price is not None and explicit != price - down:
            raise ValueError("explicit loan amount conflicts with purchase_price minus down_payment")
        if principal is None:
            missing.append("loan_amount")
        elif principal <= 0:
            raise ValueError("financed purchase requires a positive loan amount")
        if payload.loan_term_months is None:
            missing.append("loan_term_months")
        rate = payload.annual_interest_rate.value if payload.annual_interest_rate else None
        if rate is None:
            missing.append("annual_interest_rate")
        elif rate < 0 or rate > 1:
            raise ValueError("annual_interest_rate must be between 0 and 1")
        if down > 0:
            events.append(EventInput(
                type="one_time", name="車輛頭期款", month=start_month,
                start_period=str(request.target_period), amount=-float(down),
                source=EventSource.manual, display_source=display_source_label(ValueSource.user_provided),
                reason="使用者提供的頭期款",
            ))
        if principal is not None and payload.loan_term_months and rate is not None:
            loan = LoanInput(principal=float(principal), apr=float(rate), months=payload.loan_term_months,
                             start_month=start_month, note="車輛貸款")
            loans.append(loan)
            payment = _money(calculate_loan_payment(loan.principal, loan.apr, loan.months))
            interest = _money(payment * loan.months - principal)
            derived.extend([
                _fact("monthly_loan_payment", payment, ValueSource.derived, "既有貸款攤還公式"),
                _fact("total_interest", interest, ValueSource.derived, "月付款乘期數減本金"),
            ])

    recurring = [
        ("annual_insurance", payload.annual_insurance, True, "車輛保險年度金額的月平均"),
        ("annual_tax", payload.annual_tax, True, "車輛稅費年度金額的月平均"),
        ("annual_maintenance_budget", payload.annual_maintenance_budget, True, "年度維護預算的規劃月平均，非宣稱每月發生"),
        ("monthly_fuel_or_energy", payload.monthly_fuel_or_energy, False, "每月燃料或能源支出"),
        ("monthly_parking", payload.monthly_parking, False, "每月停車支出"),
    ]
    for field, sourced, annual, reason in recurring:
        if sourced is None:
            continue
        if sourced.value < 0:
            raise ValueError(f"{field} cannot be negative")
        amount = sourced.value / Decimal(12) if annual else sourced.value
        source = ValueSource.backend_normalized if annual else sourced.source
        derived.append(_fact(field + ("_monthly_average" if annual else ""), amount, source, reason))
        events.append(EventInput(
            type="range", name=field, start_month=start_month, end_month=request.horizon_months,
            start_period=str(request.target_period), amount=-float(amount), source=EventSource.manual,
            display_source=display_source_label(source), reason=reason,
        ))
    return ScenarioBuildResult(scenario_request=request, events=events, loans=loans,
                               assumptions=request.assumptions, missing_fields=list(dict.fromkeys(missing)),
                               warnings=warnings, derived_values=derived)


def _housing(request: ScenarioRequest, start_period: YearMonth) -> ScenarioBuildResult:
    payload = request.payload
    assert isinstance(payload, HousingChangeScenarioInput)
    start_month = _start_month(request, start_period)
    missing = list(request.missing_fields)
    warnings: list[str] = []
    derived: list[ScenarioFact] = []
    events: list[EventInput] = []
    rent_change = payload.monthly_rent_change.value if payload.monthly_rent_change else None
    if payload.current_rent and payload.new_rent:
        calculated = payload.new_rent.value - payload.current_rent.value
        if rent_change is not None and rent_change != calculated:
            raise ValueError("monthly_rent_change conflicts with current_rent and new_rent")
        rent_change = calculated
        derived.append(_fact("monthly_rent_change", rent_change, ValueSource.derived, "新租金減目前租金"))
    if rent_change is None:
        missing.append("monthly_rent_change")
    else:
        events.append(EventInput(type="range", name="租金變動", start_month=start_month,
                                 end_month=request.horizon_months, start_period=str(request.target_period),
                                 amount=-float(rent_change), source=EventSource.manual,
                                 display_source=display_source_label(ValueSource.derived if payload.current_rent and payload.new_rent else payload.monthly_rent_change.source),
                                 reason="租金差額，正值代表費用增加"))
    commute = payload.monthly_commute_change.value if payload.monthly_commute_change else None
    if commute is not None:
        events.append(EventInput(type="range", name="通勤費變動", start_month=start_month,
                                 end_month=request.horizon_months, start_period=str(request.target_period),
                                 amount=-float(commute), source=EventSource.manual,
                                 display_source=display_source_label(payload.monthly_commute_change.source),
                                 reason="通勤費差額，正值代表費用增加"))
    else:
        missing.append("monthly_commute_change")
    if rent_change is not None and commute is not None:
        derived.append(_fact("net_monthly_cash_flow_effect", -(rent_change + commute), ValueSource.derived,
                             "租金與通勤費變動的現金流淨影響"))
    for field, sourced in (("deposit", payload.deposit), ("moving_cost", payload.moving_cost), ("broker_fee", payload.broker_fee)):
        if sourced is None:
            continue
        if sourced.value < 0:
            raise ValueError(f"{field} cannot be negative")
        events.append(EventInput(type="one_time", name=field, month=start_month,
                                 start_period=str(request.target_period), amount=-float(sourced.value),
                                 source=EventSource.manual, display_source=display_source_label(sourced.source),
                                 reason=f"使用者提供的 {field}"))
    if payload.deposit and payload.deposit_refundable is None:
        warnings.append("押金是否可退尚未確認；模擬僅呈現支付時點，不推定為永久損失")
    return ScenarioBuildResult(scenario_request=request, events=events, loans=[], assumptions=request.assumptions,
                               missing_fields=list(dict.fromkeys(missing)), warnings=warnings, derived_values=derived)


def build_scenario(request: ScenarioRequest, start_period: YearMonth) -> ScenarioBuildResult:
    if isinstance(request.payload, VehiclePurchaseScenarioInput):
        return _vehicle(request, start_period)
    if isinstance(request.payload, HousingChangeScenarioInput):
        return _housing(request, start_period)
    raise ValueError("unsupported scenario type")


def _delta(baseline: ScenarioOptionResult, scenario: ScenarioOptionResult, start: YearMonth) -> ScenarioDelta:
    assert scenario.build is not None
    baseline_curve = baseline.simulation["simulation_curve"]
    scenario_curve = scenario.simulation["simulation_curve"]
    minimum_row = min(scenario_curve, key=lambda row: row["balance"])
    deficit = next((row for row in scenario_curve if row["balance"] < 0), None)
    build = scenario.build
    principal = sum((_money(loan.principal) for loan in build.loans), Decimal(0))
    interest = sum((_money(calculate_loan_payment(loan.principal, loan.apr, loan.months)) * loan.months - _money(loan.principal) for loan in build.loans), Decimal(0))
    one_time = sum((_money(-event.amount) for event in build.events if event.type == "one_time" and event.amount and event.amount < 0), Decimal(0))
    recurring = Decimal(0)
    for event in build.events:
        if event.type != "range" or not event.amount or event.amount >= 0:
            continue
        active = max(0, min(event.end_month or len(scenario_curve), len(scenario_curve)) - (event.start_month or 1) + 1)
        recurring += _money(-event.amount) * active
    avg_baseline = sum(_money(row["net_cashflow"]) for row in baseline_curve) / len(baseline_curve)
    avg_scenario = sum(_money(row["net_cashflow"]) for row in scenario_curve) / len(scenario_curve)
    return ScenarioDelta(
        baseline_option_id=baseline.option.option_id, scenario_option_id=scenario.option.option_id,
        final_cash_difference=_money(scenario_curve[-1]["balance"] - baseline_curve[-1]["balance"]),
        average_monthly_cash_flow_difference=_money(avg_scenario - avg_baseline),
        minimum_cash_balance=_money(minimum_row["balance"]),
        minimum_balance_period=start.add_months(minimum_row["month"]),
        first_deficit_period=start.add_months(deficit["month"]) if deficit else None,
        total_new_debt=_money(principal), total_interest=_money(interest),
        one_time_cost_total=_money(one_time), recurring_cost_total=_money(recurring),
        assumptions=build.assumptions,
    )


def compare_scenarios(request: ScenarioComparisonRequest) -> ScenarioComparisonResponse:
    baseline_option = find_baseline_option(request.options)
    horizon_values = {option.scenario_request.horizon_months for option in request.options if option.scenario_request}
    if any(value != request.horizon_months for value in horizon_values):
        raise ValueError("all scenario options must match the comparison horizon")
    horizon = request.horizon_months
    profile = request.confirmed_profile.model_dump()
    baseline_sim = simulate_finance(profile=profile, months=horizon, events=[], loans=[], seed=request.seed, include_details=True)
    baseline_result = ScenarioOptionResult(option=baseline_option, simulation=baseline_sim)
    results: list[ScenarioOptionResult] = []
    deltas: list[ScenarioDelta] = []
    for option in request.options:
        if option.is_baseline:
            continue
        build = build_scenario(option.scenario_request, request.start_period)
        if build.missing_fields:
            raise ValueError("scenario has missing fields: " + ", ".join(build.missing_fields))
        simulation = simulate_finance(profile=profile, months=horizon,
                                      events=[item.model_dump() for item in build.events],
                                      loans=[item.model_dump() for item in build.loans], seed=request.seed, include_details=True)
        result = ScenarioOptionResult(option=option, build=build, simulation=simulation)
        results.append(result)
        deltas.append(_delta(baseline_result, result, request.start_period))
    return ScenarioComparisonResponse(baseline=baseline_result, scenarios=results, deltas=deltas,
                                      baseline_only=not results)
