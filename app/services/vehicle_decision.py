"""Deterministic typed vehicle simulation, evaluation and bounded search."""
from decimal import Decimal

from app.core.simulation import simulate_finance
from app.core.events import calculate_loan_payment, get_recurring_event_amount
from app.core.financial_rules import inflation_factor
from app.decision_assumptions import ASSUMPTIONS, STRESS_DEFAULTS, registry
from app.decision_schemas import VehicleDecisionRequest
from app.scenario_schemas import SourcedDecimal, ValueSource
from app.services.calendar_period import YearMonth
from app.services.scenario_engine import build_scenario
from app.vehicle_catalog import get_vehicle


OWNERSHIP = ("annual_insurance", "annual_tax", "annual_maintenance_budget", "monthly_fuel_or_energy", "monthly_parking", "monthly_transportation_offset")


def resolve(request):
    req = request.model_copy(deep=True)
    provenance = []
    for key in type(req.profile).model_fields:
        value = getattr(req.profile, key)
        if key == 'existing_debts':
            if value is not None:
                provenance.append(dict(key='profile.existing_debts', value=[d.model_dump() for d in value], source='user'))
            continue
        source = req.assumption_sources.get("profile." + key, "user")
        if value is None:
            value = ASSUMPTIONS[key]["value"]
            setattr(req.profile, key, value)
            source = "system_assumption"
        provenance.append(dict(key="profile." + key, value=value, source=source))
    for key in type(req.constraints).model_fields:
        value = getattr(req.constraints, key)
        source = req.assumption_sources.get(key, "user")
        if value is None:
            value = ASSUMPTIONS[key]["value"]
            setattr(req.constraints, key, value)
            source = "system_assumption"
        provenance.append(dict(key=key, value=value, source=source))
    p = req.scenario.payload
    for key in OWNERSHIP:
        if getattr(p, key) is None:
            setattr(p, key, SourcedDecimal(value=ASSUMPTIONS[key]["value"], source=ValueSource.system_assumption))
    for key in type(p).model_fields:
        value = getattr(p, key)
        if value is not None:
            provenance.append(dict(key=key, value=float(value.value) if isinstance(value, SourcedDecimal) else value,
                                   source=({'system_assumption':'system_assumption','derived':'derived','backend_normalized':'derived','user_provided':'user'}[value.source.value]) if isinstance(value, SourcedDecimal) else "user",
                                   basis=value.original_text if isinstance(value, SourcedDecimal) else None))
    provenance.extend([dict(key='start_period', value=req.start_period, source='user'),
                       dict(key='target_period', value=str(req.scenario.target_period), source='user'),
                       dict(key='horizon_months', value=60, source='system_assumption')])
    if p.monthly_transportation_offset.value > Decimal(str(req.profile.fixed_expense + req.profile.variable_expense)):
        raise ValueError("交通抵減不得超過原本生活支出，且必須已包含在原支出中")
    return req, provenance


def run_timeline(req, *, baseline=False, stress=None, round_output=True):
    scenario = req.scenario.model_copy(deep=True)
    if stress == "interest_rate" and scenario.payload.payment_method == "financed":
        scenario.payload.annual_interest_rate.value += Decimal(str(STRESS_DEFAULTS['rate_increase']))
    build = None if baseline else build_scenario(scenario, YearMonth.parse(req.start_period))
    if build and build.missing_fields:
        raise ValueError("缺少必要購車資料：" + ", ".join(build.missing_fields))
    events = []
    start = YearMonth.parse(req.start_period).months_until(scenario.target_period)
    if build:
        for event in build.events:
            raw = event.model_dump()
            if raw['type'] != 'range':
                events.append(raw)
                continue
            # Inflation is constant within simulation months 1-12, 13-24, ... .
            # Keep the same amount and active months, but avoid scanning up to
            # 360 individual monthly ownership events in every expense category.
            # A purchase in month 12 gets one month at year-one prices, not 12.
            for year_start in range(1, 61, 12):
                month = max(start, year_start)
                end = year_start + 11
                if month > end:
                    continue
                events.append({**raw, 'start_month': month, 'end_month': end,
                               'amount': raw['amount'] * inflation_factor(month, req.profile.inflation_rate)})
    if stress == 'income_reduction':
        events.append(dict(type='range', start_month=start, end_month=60, income_multiplier=STRESS_DEFAULTS['income_multiplier']))
    elif stress == 'unemployment':
        events.append(dict(type='range', start_month=start, end_month=start + STRESS_DEFAULTS['unemployment_months'] - 1, income_multiplier=0))
    elif stress == 'emergency_expense':
        events.append(dict(type='one_time', month=start, amount=-STRESS_DEFAULTS['emergency_expense']))
    result = simulate_finance(req.profile.model_dump(), months=60, events=events,
                              loans=[x.model_dump() for x in build.loans] if build else [],
                              seed=0, evaluate_legacy_risk=False, round_output=round_output)
    rows = [{key: value for key, value in row.items() if key not in ('fsi', 'risk_level', 'debt_to_income')} for row in result['simulation_curve']]
    period = YearMonth.parse(req.start_period)
    for row in rows:
        row['period'] = str(period.add_months(row['month']))
    return rows, build


def evaluate(rows, req, build=None, *, round_output=True):
    minimum = min(rows, key=lambda row: row['balance'])
    coverage = [r['emergency_fund_months'] for r in rows if r['emergency_fund_months'] is not None]
    start = YearMonth.parse(req.start_period).months_until(req.scenario.target_period)
    steady = rows[start - 1]
    one_time = sum(-e.amount for e in build.events if e.type == 'one_time' and e.amount < 0) if build else 0
    payment = sum(calculate_loan_payment(l.principal, l.apr, l.months) for l in build.loans) if build else 0
    interest = sum(calculate_loan_payment(l.principal, l.apr, l.months) * l.months - l.principal for l in build.loans) if build else 0
    display = lambda value, places: round(value, places) if round_output else value
    return dict(monthly_surplus=display(steady['income']-steady['living_expense']-steady['debt_payment'], 2),
                minimum_cash_balance=minimum['balance'], minimum_cash_month=minimum['period'],
                minimum_emergency_fund_months=display(min(coverage), 6) if coverage else None,
                one_time_cash_requirement=round(one_time, 2), ending_cash=rows[-1]['balance'],
                monthly_loan_payment=round(payment, 2), total_loan_interest=round(interest, 2))


def constraints(metrics, req):
    mapping = dict(minimum_emergency_fund_months='minimum_emergency_fund_months', minimum_cash_balance='minimum_cash_balance', minimum_monthly_surplus='monthly_surplus')
    return [dict(key=key, actual=metrics[field], required=value,
                 passed=metrics[field] is None or metrics[field] >= value)
            for key, field in mapping.items() for value in [getattr(req.constraints, key)]]


def price_metrics(req, price):
    copy = req.model_copy(deep=True)
    copy.scenario.payload.purchase_price.value = Decimal(str(price))
    copy.scenario.payload.explicit_loan_amount = None
    rows, build = run_timeline(copy, round_output=False)
    metrics = evaluate(rows, copy, build, round_output=False)
    checks = constraints(metrics, copy)
    return metrics, checks


def find_limit(req):
    # Fixed down payment and fixed ownership budgets keep price affordability monotonic.
    p = req.scenario.payload
    lower = float(p.down_payment.value) + 1 if p.payment_method == 'financed' else 1
    _, checks = price_metrics(req, lower)
    if not all(c['passed'] for c in checks):
        return dict(status='no_feasible_price', maximum_affordable_vehicle_price=None,
                    binding_constraint=[c['key'] for c in checks if not c['passed']], constraint_results=checks)
    upper = max(lower * 2, float(p.purchase_price.value), 100000)
    upper = min(upper, 20000000)
    while True:
        _, checks = price_metrics(req, upper)
        if not all(c['passed'] for c in checks):
            break
        if upper >= 20000000:
            return dict(status='search_limit_reached', maximum_affordable_vehicle_price=None, binding_constraint=[], constraint_results=checks)
        upper = min(upper * 2, 20000000)
    while upper - lower > .000001:
        midpoint = (lower + upper) / 2
        _, checks = price_metrics(req, midpoint)
        if all(c['passed'] for c in checks):
            lower = midpoint
        else:
            upper = midpoint
    price = int(lower * 100) / 100
    # An exact-cent boundary can sit between the converged endpoints.
    next_cent = float(Decimal(str(price)) + Decimal('.01'))
    if next_cent <= upper:
        _, next_checks = price_metrics(req, next_cent)
        if all(c['passed'] for c in next_checks):
            price = next_cent
    _, checks = price_metrics(req, price)
    if price * 1.01 > 20000000:
        return dict(status='verification_limit_reached', maximum_affordable_vehicle_price=None,
                    binding_constraint=[], constraint_results=checks)
    _, above = price_metrics(req, price * 1.01)
    return dict(status='bounded', maximum_affordable_vehicle_price=price,
                binding_constraint=[c['key'] for c in above if not c['passed']],
                constraint_results=checks, above_limit_constraint_results=above,
                policy='fixed_down_payment_and_ownership_costs', tolerance_twd=.01)


def simulate_vehicle_decision(request: VehicleDecisionRequest):
    req, provenance = resolve(request)
    baseline_rows, _ = run_timeline(req, baseline=True)
    rows, build = run_timeline(req)
    baseline = evaluate(baseline_rows, req)
    scenario = evaluate(rows, req, build)
    stresses = []
    for name in ('income_reduction', 'unemployment', 'emergency_expense', 'interest_rate'):
        stressed, stress_build = run_timeline(req, stress=name)
        metrics = evaluate(stressed, req, stress_build)
        stresses.append(dict(name=name, applicable=name != 'interest_rate' or req.scenario.payload.payment_method == 'financed',
                             metrics=metrics, constraints=constraints(metrics, req)))
    return dict(baseline=baseline, scenario=scenario,
                baseline_monthly_surplus=baseline['monthly_surplus'],
                scenario_steady_monthly_surplus=scenario['monthly_surplus'],
                five_year_cash_delta=round(scenario['ending_cash']-baseline['ending_cash'], 2),
                timeline=dict(baseline=baseline_rows, scenario=rows),
                constraints=constraints(scenario, req), stress_tests=stresses,
                affordability=find_limit(req), provenance=provenance,
                ownership_costs=ownership_cost_summary(req, build),
                selected_vehicle=get_vehicle(req.vehicle_catalog_id) if req.vehicle_catalog_id else None,
                assumptions=effective_assumptions(req, provenance),
                derived_values=[f.model_dump(mode='json') for f in build.derived_values],
                stress_definitions=STRESS_DEFAULTS, stress_source='system_assumption', metric_source='derived',
                definitions=dict(monthly_surplus='購車生效月份，不含一次性支出；非全期平均',
                                 minimum_cash='每月底現金餘額，未模擬月內付款先後',
                                 zero_expense_coverage='無必要支出時回傳 null，表示不適用',
                                 inflation='每滿12個月調整變動支出、車輛持有成本及交通抵減；固定支出可選；債務固定名目',
                                 annual_costs='年度預算按月提列，非實際繳款日期',
                                 cash='僅計現金，不含車輛殘值、投資收益或淨資產',
                                 existing_debt='明細依基準後第1個月起計剩餘期數，最後一期後停止；僅填總額則全期固定'))


def ownership_cost_summary(req, build, *, horizon_months=60):
    """Summarize the exact events used by the engine, without adding price twice."""
    start = YearMonth.parse(req.start_period).months_until(req.scenario.target_period)
    factors = [inflation_factor(m, req.profile.inflation_rate) for m in range(start, horizon_months + 1)]
    items = []
    for event in build.events:
        if event.type != 'range':
            continue
        offset = event.name == 'monthly_transportation_offset'
        amount = abs(event.amount)
        items.append(dict(key=event.name, monthly_amount=round(amount * factors[0], 2),
                          period_total=round(amount * sum(factors), 2),
                          is_offset=offset, source=getattr(req.scenario.payload, event.name).source.value))
    gross = sum(abs(e.amount) for e in build.events if e.type == 'range' and e.amount < 0)
    offset = sum(e.amount for e in build.events if e.type == 'range' and e.amount > 0)
    loan_payment = sum(round(calculate_loan_payment(l.principal, l.apr, l.months), 2) for l in build.loans)
    loan_total = sum(round(calculate_loan_payment(l.principal, l.apr, l.months), 2)
                     * max(0, min(horizon_months, l.start_month + l.months - 1) - l.start_month + 1)
                     for l in build.loans)
    one_time = sum(-e.amount for e in build.events if e.type == 'one_time' and e.amount < 0)
    ownership_total = gross * sum(factors)
    offset_total = offset * sum(factors)
    recurring = [-get_recurring_event_amount(month, [
        {**event.model_dump(), 'amount': event.amount * factor}
        for event in build.events if event.type == 'range'])
        for month, factor in zip(range(start, horizon_months + 1), factors)]
    add_cost_percentages(items)
    return dict(items=items, purchase_period=str(req.scenario.target_period),
                ownership_months=len(factors), monthly_ownership=round(gross * factors[0], 2),
                monthly_offset=round(offset * factors[0], 2), monthly_loan_payment=round(loan_payment, 2),
                monthly_vehicle_outflow=round(round(gross * factors[0], 2) + loan_payment, 2),
                monthly_net_increase=round(recurring[0] + loan_payment, 2),
                one_time_payment=round(one_time, 2), ownership_total=round(ownership_total, 2),
                offset_total=round(offset_total, 2), loan_payments_total=round(loan_total, 2),
                rounding_adjustment=round(sum(recurring) - sum(i['period_total'] * (-1 if i['is_offset'] else 1) for i in items), 2),
                net_cash_outlay=round(one_time + loan_total + sum(recurring), 2),
                remaining_loan_months=max((max(0, l.start_month + l.months - 1 - horizon_months) for l in build.loans), default=0),
                source='derived')


def add_cost_percentages(items):
    eligible = [i for i in items if not i['is_offset']]
    total = sum(Decimal(str(i['monthly_amount'])) for i in eligible)
    for item in items:
        item['percentage'] = 0
    if not total:
        return
    exact = [Decimal(str(i['monthly_amount'])) / total * 10000 for i in eligible]
    points = [int(value) for value in exact]
    remainder = 10000 - sum(points)
    order = sorted(range(len(exact)), key=lambda i: exact[i] - points[i], reverse=True)
    for index in order[:remainder]:
        points[index] += 1
    for item, value in zip(eligible, points):
        item['percentage'] = value / 100


def effective_assumptions(req, provenance):
    sources = {p['key']: p for p in provenance}
    records = []
    for item in registry():
        key = item['key']
        actual = sources.get('profile.' + key, sources.get(key))
        records.append({**item, 'default_value': item['value'], 'value': actual['value'],
                        'source': actual['source'], 'user_override': actual['source'] == 'user'})
    return records
