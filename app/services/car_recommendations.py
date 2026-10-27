"""Hard filters and auditable cash ranking using existing deterministic services."""
from datetime import date
from decimal import Decimal
from app.decision_assumptions import ASSUMPTIONS
from app.decision_schemas import VehicleDecisionRequest
from app.recommendation_catalog import recommendation_catalog
from app.recommendation_schemas import CarNeedsRequest
from app.services.calendar_period import YearMonth, resolve_reference_date
from app.services.vehicle_decision import resolve, run_timeline, evaluate, constraints, ownership_cost_summary
from app.services.scenario_engine import build_scenario


def sourced(value, source='system_assumption'):
    return dict(value=value, source=source)


def preference_checks(needs, car):
    checks = []
    for key, wanted, actual in [('車型偏好', needs.preferences.body_types, car.get('body_type')),
                                 ('動力偏好', needs.preferences.powertrains, car.get('powertrain'))]:
        if wanted:
            checks.append(dict(label=key, status='insufficient_data' if actual is None else 'match' if actual in wanted else 'mismatch'))
    if car.get('powertrain') == 'bev':
        charging = [needs.usage.home_charging, needs.usage.public_charging]
        checks.append(dict(label='充電條件', status='match' if 'yes' in charging else 'mismatch' if charging == ['no', 'no'] else 'insufficient_data'))
    for priority in needs.preferences.priorities:
        checks.append(dict(label={'space':'空間', 'comfort':'舒適度', 'energy_cost':'能源成本偏好', 'maintenance_cost':'保養費偏好', 'safety':'安全性'}[priority],
                           status='insufficient_data', note='尚無一致、可查證的比較標準；不給分、不影響排名'))
    return checks


def recommend_cars(needs: CarNeedsRequest, *, reference_date: date | None = None):
    reference_date = resolve_reference_date(reference_date, 'Asia/Taipei')
    start = reference_date.strftime('%Y-%m')
    target = str(YearMonth.parse(start).add_months(1))
    assumptions = [dict(key=key, **ASSUMPTIONS[key], source='system_assumption') for key in
                   ('annual_insurance', 'annual_tax', 'annual_maintenance_budget', 'inflation_rate', 'raise_rate',
                    'minimum_emergency_fund_months', 'minimum_cash_balance', 'minimum_monthly_surplus')]
    assumptions.append(dict(key='fuel_price', value=30, unit='TWD/L', source='system_assumption', description='比較用油價假設，非即時油價'))
    for assumption in assumptions:
        key = assumption['key']
        if key in ('raise_rate', 'inflation_rate') and needs.financial_profile and getattr(needs.financial_profile, key) is not None:
            assumption.update(value=getattr(needs.financial_profile, key), source='user_provided')
    ranked, incomplete, excluded = [], [], []
    common_missing = []
    if needs.usage.monthly_distance_km is None: common_missing.append('請補充每月行駛里程（可明確填 0）')
    if needs.payment.payment_method is None: common_missing.append('請選擇現金或貸款付款方式')
    if needs.usage.monthly_parking is None: common_missing.append('請填寫每月停車預算（免費停車請明確填 0）')
    for car in recommendation_catalog():
        reasons, missing = [], list(common_missing)
        price, seats, body = car.get('price_twd'), car.get('seats'), car.get('body_type')
        if price is None: missing.append('參考車價未知，無法驗證預算')
        elif price > needs.constraints.budget_max: reasons.append('超過車價預算')
        if seats is None: missing.append('座位數未知，無法驗證乘車人數')
        elif seats < needs.constraints.min_seats: reasons.append('座位數不足')
        if body is None and needs.constraints.avoid_body_types: missing.append('車型類別未知')
        elif body in needs.constraints.avoid_body_types: reasons.append('使用者明確排除此車型')
        if car.get('powertrain') == 'bev' and needs.usage.home_charging == needs.usage.public_charging == 'no':
            reasons.append('住家與公共充電條件皆明確不可用')
        if reasons:
            excluded.append(dict(vehicle=car, reasons=reasons))
            continue
        if car.get('efficiency') is None or car['efficiency'] <= 0: missing.append('缺少可核對的官方油耗／電耗')
        if car.get('powertrain') == 'bev':
            missing.append('尚未校準純電車稅費、充電單價與車型維護成本')
        if needs.payment.payment_method == 'financed' and price is not None and needs.payment.down_payment >= price:
            missing.append('此車價低於或等於頭期款，請調整付款方式，不能建立負本金貸款')
        item = dict(vehicle=car, preferences=preference_checks(needs, car))
        if missing:
            incomplete.append(dict(**item, reasons=missing, five_year_cash_outflow=None, affordability=None))
            continue
        monthly_energy = Decimal(str(needs.usage.monthly_distance_km)) / Decimal(str(car['efficiency'])) * 30
        payload = dict(scenario_type='vehicle_purchase', purchase_price=sourced(price, 'derived'),
                       vehicle_condition='new', payment_method=needs.payment.payment_method,
                       monthly_fuel_or_energy=sourced(monthly_energy.quantize(Decimal('.01')), 'derived'),
                       monthly_parking=sourced(needs.usage.monthly_parking, 'user_provided'),
                       monthly_transportation_offset=sourced(0))
        for key in ('annual_insurance', 'annual_tax', 'annual_maintenance_budget'):
            payload[key] = sourced(ASSUMPTIONS[key]['value'])
        if needs.payment.payment_method == 'financed':
            payload.update(down_payment=sourced(needs.payment.down_payment, 'user_provided'),
                           annual_interest_rate=sourced(needs.payment.annual_interest_rate, 'user_provided'),
                           loan_term_months=needs.payment.loan_term_months)
        profile = needs.financial_profile.model_dump() if needs.financial_profile else dict(salary=0, balance=0, fixed_expense=0, variable_expense=0, required_monthly_debt=0)
        req, _ = resolve(VehicleDecisionRequest.model_validate(dict(profile=profile, start_period=start,
            scenario=dict(scenario_id='p2-'+car['id'], scenario_type='vehicle_purchase', target_period=target, horizon_months=60, payload=payload))))
        build = build_scenario(req.scenario, YearMonth.parse(start))
        costs = ownership_cost_summary(req, build)
        affordability = None
        if needs.financial_profile:
            rows, build = run_timeline(req)
            baseline, _ = run_timeline(req, baseline=True)
            metrics = evaluate(rows, req, build)
            checks = constraints(metrics, req)
            affordability = dict(metrics=metrics, baseline=evaluate(baseline, req), constraints=checks, passed=all(c['passed'] for c in checks),
                                 five_year_cash_change=round(metrics['ending_cash']-baseline[-1]['balance'], 2))
        ranked.append(dict(**item, five_year_cash_outflow=costs['net_cash_outlay'], costs=costs,
                           affordability=affordability, ranking_reason='相同使用條件與付款方式下，五年車輛現金支出由低至高；同額依目錄 ID 排序',
                           remaining_loan_payments=round(costs['remaining_loan_months']*costs['monthly_loan_payment'], 2),
                           energy_formula=f"{needs.usage.monthly_distance_km} km/月 ÷ {car['efficiency']} km/L × NT$30/L"))
    ranked.sort(key=lambda item: (item['five_year_cash_outflow'], item['vehicle']['id']))
    for rank, item in enumerate(ranked, 1): item['rank'] = rank
    return dict(schema_version='1.0', revision=needs.revision, provider='deterministic', is_real_ai=False,
                ranked=ranked, incomplete=incomplete, excluded=excluded, assumptions=assumptions,
                start_period=start, purchase_period=target, reference_date=reference_date.isoformat(),
                timezone='Asia/Taipei', horizon_months=60, currency='TWD',
                missing_inputs=common_missing, scope='five_year_vehicle_cash_outflow',
                limitations=['現金支出不是總持有成本或淨資產損失；不含折舊、殘值、投資報酬、領牌與未列雜費',
                             '即使預計持有 1 或 3 年，本頁仍統一比較 60 個月；不模擬提前出售',
                             '五年後剩餘貸款付款另列，不能視為無須清償；不是本金餘額',
                             '偏好只標記符合情形，不是硬性限制；職業與自由文字不直接決定排名',
                             '財務通過僅代表系統預設限制，不保證一定負擔得起；不是風險機率'])
