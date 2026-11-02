"""Translate planner vehicles using the existing vehicle scenario builder."""
from app.core.balance_sheet import asset_value, loan_interest_through
from app.core.market_data import load_market_history
from app.decision_assumptions import ASSUMPTIONS, VEHICLE_DEPRECIATION
from app.planner_schemas import PlannerVehicleRequest
from app.scenario_schemas import ScenarioRequest
from app.schemas import EventInput
from app.services.calendar_period import YearMonth
from app.services.scenario_engine import build_scenario
from app.services.vehicle_event_costs import inflate_vehicle_events


OWNERSHIP_FIELDS = ('annual_insurance', 'annual_tax', 'annual_maintenance_budget',
                    'monthly_fuel_or_energy', 'monthly_parking')
NOTE = ('購車持有成本以固定通膨率每年調整；Monte Carlo 的抽樣通膨不套用在購車成本上。'
        '車輛估值依固定折舊率計算，不是成交價，Monte Carlo 不抽樣。')


def _money(value):
    return round(float(value), 2)


def convert_vehicle_events(request: PlannerVehicleRequest):
    inflation = (request.inflation_rate if request.inflation_rate is not None
                 else load_market_history().annual_inflation_rate)
    # The existing builder starts in the month AFTER its base period. Planner
    # starts IN start_period, so move only the builder's base back one month.
    base = YearMonth.parse(request.start_period).add_months(-1)
    events, loans, assets, vehicles = [], [], [], []
    for index, vehicle in enumerate(request.vehicles):
        details = vehicle.details.model_dump(exclude_none=True, exclude={
            'vehicle_catalog_id', 'displacement_cc', 'fuel_type', 'insurance_items'})
        defaults = []
        for key in OWNERSHIP_FIELDS:
            if key not in details:
                details[key] = ASSUMPTIONS[key]['value']
                defaults.append(key)
        depreciation = details.pop('annual_depreciation_rate', None)
        if depreciation is None:
            depreciation = VEHICLE_DEPRECIATION['value']
            defaults.append(VEHICLE_DEPRECIATION['key'])
        payload = {'scenario_type': 'vehicle_purchase'}
        for key, value in details.items():
            payload[key] = (value if key in ('payment_method', 'loan_term_months') else
                            {'value': value, 'source': 'system_assumption' if key in defaults else 'user_provided'})
        scenario = ScenarioRequest(scenario_id=f'planner-vehicle-{index}', scenario_type='vehicle_purchase',
                                   target_period=vehicle.purchase_period, horizon_months=request.months, payload=payload)
        build = build_scenario(scenario, base)
        if build.missing_fields:
            raise ValueError('缺少必要購車資料，請補齊車價及貸款條件')
        month = base.months_until(scenario.target_period)
        converted = inflate_vehicle_events(build.events, month, request.months, inflation)
        # Guarantee that the emitted events fit the calculation APIs' limits,
        # including inflated ownership costs near the end of long horizons.
        for event in converted:
            EventInput.model_validate(event)
        events.extend(converted)
        vehicle_loans = [loan.model_dump(mode='json') for loan in build.loans]
        loans.extend(vehicle_loans)
        asset = dict(name=vehicle.name, start_month=month, value=float(vehicle.details.purchase_price),
                     annual_depreciation_rate=depreciation)
        assets.append(asset)
        derived = {fact.field: float(fact.value) for fact in build.derived_values if fact.value is not None}
        # Economic cost is value lost plus expenses inside the horizon, not a second cash outflow.
        ending_value = asset_value(asset, request.months)
        depreciation_cost = asset['value'] - ending_value
        interest = sum(loan_interest_through(loan, request.months) for loan in vehicle_loans)
        ownership = sum(-event['amount'] * (event['end_month'] - event['start_month'] + 1)
                        for event in converted if event['type'] == 'range')
        vehicles.append(dict(
            name=vehicle.name, purchase_month=month,
            one_time_cash=round(sum(-event.amount for event in build.events if event.type == 'one_time'), 2),
            monthly_loan_payment=derived.get('monthly_loan_payment', 0),
            total_loan_interest=derived.get('total_interest', 0),
            first_year_monthly_ownership_cost=round(sum(-event.amount for event in build.events if event.type == 'range'), 2),
            defaults_used=defaults,
            annual_depreciation_rate=depreciation,
            ending_vehicle_value=_money(ending_value),
            depreciation_in_horizon=_money(depreciation_cost),
            interest_in_horizon=_money(interest),
            ownership_cost_in_horizon=_money(ownership),
            economic_cost_in_horizon=_money(depreciation_cost + interest + ownership),
        ))
    return dict(events=events, loans=loans, assets=assets, vehicles=vehicles, inflation_rate_used=inflation, note=NOTE)
