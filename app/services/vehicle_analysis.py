"""One-at-a-time sensitivity and shared-context vehicle comparison."""
from decimal import Decimal

from app.decision_schemas import VehicleDecisionRequest, VehicleComparisonRequest, VehicleWhatIfRequest
from app.services.vehicle_decision import resolve, run_timeline, evaluate, constraints, simulate_vehicle_decision


FACTORS = (
    ('salary', '每月收入', .10, 'relative'),
    ('monthly_fuel_or_energy', '油電費', .20, 'relative'),
    ('monthly_parking', '停車費', .20, 'relative'),
    ('annual_maintenance_budget', '維護預算', .30, 'relative'),
    ('annual_insurance', '保險費', .20, 'relative'),
    ('inflation_rate', '通膨率', .01, 'percentage_points'),
    ('purchase_price', '車價', .10, 'relative'),
)


def evaluate_variant(req, key, value, base):
    candidate = req.model_copy(deep=True)
    if key in ('salary', 'inflation_rate'):
        setattr(candidate.profile, key, value)
    else:
        getattr(candidate.scenario.payload, key).value = Decimal(str(value))
        if key == 'purchase_price':
            candidate.scenario.payload.explicit_loan_amount = None
    try:
        candidate = VehicleDecisionRequest.model_validate(candidate.model_dump())
        rows, build = run_timeline(candidate)
        metrics = evaluate(rows, candidate, build)
        return dict(value=value, status='valid', metrics=metrics,
                    ending_cash_change=round(metrics['ending_cash'] - base['ending_cash'], 2),
                    constraints=constraints(metrics, candidate))
    except ValueError:
        return dict(value=value, status='not_applicable',
                    reason='變動後超出有效金額或貸款條件', metrics=None,
                    ending_cash_change=None, constraints=[])


def sensitivity_analysis(request: VehicleDecisionRequest):
    req, _ = resolve(request)
    rows, build = run_timeline(req)
    base = evaluate(rows, req, build)
    factors = []
    for key, label, amount, mode in FACTORS:
        original = (getattr(req.profile, key) if key in ('salary', 'inflation_rate')
                    else float(getattr(req.scenario.payload, key).value))
        variants = {}
        for direction, sign in (('low', -1), ('high', 1)):
            value = (original + sign * amount if mode == 'percentage_points'
                     else original * (1 + sign * amount))
            # Rates cannot fall below zero; disclose the actual tested endpoint.
            if key == 'inflation_rate':
                value = max(0, value)
            variants[direction] = evaluate_variant(req, key, value, base)
        changes = [v['ending_cash_change'] for v in variants.values() if v['status'] == 'valid']
        factors.append(dict(key=key, label=label, original_value=original, variation=amount,
                            variation_mode=mode, **variants,
                            impact_span=round(max(changes) - min(changes), 2) if len(changes) == 2 else None))
    factors.sort(key=lambda f: f['impact_span'] if f['impact_span'] is not None else -1, reverse=True)
    return dict(base_metrics=base, factors=factors, metric='ending_cash', source='derived',
                method='one_at_a_time', ranking='impact_span_under_specified_ranges',
                definition='每次只改一個因素；依指定幅度的五年期末現金變動範圍排序，非機率或因果重要性')


def vehicle_what_if(request: VehicleWhatIfRequest):
    req, _ = resolve(request.request)
    rows, build = run_timeline(req)
    base = evaluate(rows, req, build)
    original = req.profile.salary if request.field == 'salary' else float(getattr(req.scenario.payload, request.field).value)
    value = float(Decimal(str(original)) + Decimal(str(request.change)))
    variant = evaluate_variant(req, request.field, value, base)
    label = next(label for key, label, _, _ in FACTORS if key == request.field)
    return dict(base_metrics=base, factor=dict(key=request.field, label=label, original_value=original),
                variant=variant, source='derived', method='one_at_a_time')


def compare_vehicles(request: VehicleComparisonRequest):
    a, _ = resolve(request.a)
    b, _ = resolve(request.b)
    if a.profile != b.profile or a.constraints != b.constraints or a.start_period != b.start_period:
        raise ValueError('A/B 財務條件不一致')
    result_a = simulate_vehicle_decision(request.a)
    result_b = simulate_vehicle_decision(request.b)
    fields = ('monthly_surplus', 'minimum_cash_balance', 'minimum_emergency_fund_months',
              'one_time_cash_requirement', 'ending_cash', 'monthly_loan_payment', 'total_loan_interest')
    differences = {key: (round(result_b['scenario'][key] - result_a['scenario'][key], 6 if key == 'minimum_emergency_fund_months' else 2)
                         if result_a['scenario'][key] is not None and result_b['scenario'][key] is not None else None)
                   for key in fields}
    return dict(a=result_a, b=result_b, difference_b_minus_a=differences, source='derived',
                definition='相同基準月份與60個月觀察期；不同購買日期的貸款剩餘期數可能不同，不含殘值與淨資產')
