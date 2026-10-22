"""Catalog-based running costs using the existing vehicle event builder."""
from typing import Literal
from pydantic import Field, model_validator
from app.decision_schemas import StrictModel, VehicleDecisionRequest, DecisionProfile, DecisionConstraints
from app.decision_assumptions import ASSUMPTIONS
from app.vehicle_catalog import VehiclePresetRequest, vehicle_preset
from app.services.vehicle_decision import resolve, run_timeline, evaluate, constraints, ownership_cost_summary
from app.services.scenario_engine import build_scenario
from app.services.calendar_period import YearMonth


class CostAmount(StrictModel):
    value: float = Field(ge=0, le=20000000)
    source: Literal['user_provided', 'system_assumption'] = 'user_provided'


class CustomCostVehicle(StrictModel):
    name: str = Field(min_length=1, max_length=100, pattern=r'\S')
    monthly_fuel_or_energy: CostAmount
    purchase_price: float | None = Field(default=None, gt=0, le=20000000)


class CostVehicle(StrictModel):
    vehicle_id: str | None = Field(default=None, min_length=1, max_length=80)
    custom_vehicle: CustomCostVehicle | None = None
    annual_insurance: CostAmount | None = None
    annual_tax: CostAmount | None = None
    annual_maintenance_budget: CostAmount | None = None
    monthly_parking: CostAmount | None = None
    payment_method: Literal['cash','financed'] = 'cash'
    down_payment: float = Field(default=0, ge=0, le=20000000)
    annual_interest_rate: float = Field(default=0, ge=0, le=.98)
    loan_term_months: int = Field(default=60, ge=1, le=600, strict=True)

    @model_validator(mode='after')
    def require_one_vehicle(self):
        if bool(self.vehicle_id) == bool(self.custom_vehicle):
            raise ValueError('請選擇清單車款或自訂車款，不能同時提供。')
        return self


class ComparisonFinancialContext(StrictModel):
    profile: DecisionProfile
    constraints: DecisionConstraints = Field(default_factory=DecisionConstraints)
    start_period: str = Field(pattern=r'^\d{4}-\d{2}$')
    target_period: str = Field(pattern=r'^\d{4}-\d{2}$')
    assumption_sources: dict[str, Literal['user','system_assumption']] = Field(default_factory=dict)
    monthly_transportation_offset: CostAmount = Field(default_factory=lambda:CostAmount(value=0, source='system_assumption'))


class VehicleCostComparisonRequest(StrictModel):
    left: CostVehicle
    right: CostVehicle
    annual_distance_km: float = Field(ge=0, le=200000)
    fuel_price_twd_l: float = Field(ge=0, le=200)
    ownership_years: Literal[1, 3, 5] = 5
    financial_context: ComparisonFinancialContext | None = None


def compare_running_costs(request: VehicleCostComparisonRequest):
    def calculate(selection):
        preset = vehicle_preset(VehiclePresetRequest(vehicle_id=selection.vehicle_id,
                                annual_distance_km=request.annual_distance_km,
                                fuel_price_twd_l=request.fuel_price_twd_l)) if selection.vehicle_id else None
        custom = selection.custom_vehicle
        vehicle = preset['vehicle'] if preset else dict(brand='', model=custom.name.strip(), trim='', source='user_provided')
        payload = dict(scenario_type='vehicle_purchase', payment_method='cash',
                       # Purchase price is excluded from running costs; 1 only satisfies the shared builder.
                       purchase_price=dict(value=preset['purchase_price'] if preset else 1, source='backend_normalized'),
                       monthly_fuel_or_energy=dict(value=preset['monthly_fuel_or_energy'], source='derived') if preset else custom.monthly_fuel_or_energy.model_dump(),
                       monthly_transportation_offset=dict(value=0, source='system_assumption'))
        for key in ('annual_insurance', 'annual_tax', 'annual_maintenance_budget', 'monthly_parking'):
            amount = getattr(selection, key)
            payload[key] = amount.model_dump() if amount else dict(value=ASSUMPTIONS[key]['value'], source='system_assumption')
        # Dates only anchor the shared builder; this is a fixed-price ownership window.
        req = VehicleDecisionRequest.model_validate(dict(
            vehicle_catalog_id=selection.vehicle_id, start_period='2000-01',
            profile=dict(salary=0, balance=0, fixed_expense=0, variable_expense=0,
                         required_monthly_debt=0, raise_rate=0, inflation_rate=0),
            scenario=dict(scenario_id='running-costs', scenario_type='vehicle_purchase',
                          target_period='2000-02', horizon_months=60, payload=payload)))
        req, _ = resolve(req)
        build = build_scenario(req.scenario, YearMonth.parse(req.start_period))
        costs = ownership_cost_summary(req, build, horizon_months=request.ownership_years * 12)
        financial = None
        if request.financial_context:
            context = request.financial_context
            if custom and custom.purchase_price is None:
                raise ValueError('自訂車款進行財務比較時，請提供車價。')
            financial_payload = {**payload, 'payment_method':selection.payment_method,
                                 'purchase_price':dict(value=preset['purchase_price'] if preset else custom.purchase_price,
                                                       source='backend_normalized' if preset else 'user_provided'),
                                 'monthly_transportation_offset':context.monthly_transportation_offset.model_dump()}
            if selection.payment_method == 'financed':
                financial_payload.update(down_payment=dict(value=selection.down_payment,source='user_provided'),
                                         annual_interest_rate=dict(value=selection.annual_interest_rate,source='user_provided'),
                                         loan_term_months=selection.loan_term_months)
            decision = VehicleDecisionRequest.model_validate(dict(
                vehicle_catalog_id=selection.vehicle_id, profile=context.profile.model_dump(),
                constraints=context.constraints.model_dump(), assumption_sources=context.assumption_sources,
                start_period=context.start_period,
                scenario=dict(scenario_id='vehicle-comparison',scenario_type='vehicle_purchase',
                              target_period=context.target_period,horizon_months=60,payload=financial_payload)))
            # This response exposes neither stress tests nor a price boundary.
            # Use exactly the same timeline/metric functions without those searches.
            decision, _ = resolve(decision)
            baseline_rows, _ = run_timeline(decision, baseline=True)
            rows, financial_build = run_timeline(decision)
            metrics = evaluate(rows, decision, financial_build)
            financial=dict(baseline=evaluate(baseline_rows, decision), metrics=metrics,
                           constraints=constraints(metrics, decision),
                           ownership_costs=ownership_cost_summary(decision, financial_build),
                           source='derived')
        return dict(vehicle=vehicle, financial=financial, monthly_cost=costs['monthly_ownership'],
                    annual_cost=round(costs['ownership_total'] / request.ownership_years, 2),
                    period_cost=round(costs['ownership_total'], 2),
                    structure=[item for item in costs['items'] if not item['is_offset']],
                    budgets={key:payload[key] for key in ('annual_insurance', 'annual_tax', 'annual_maintenance_budget', 'monthly_parking')})
    left, right = calculate(request.left), calculate(request.right)
    financial_difference = None
    if request.financial_context:
        financial_difference={key:round(right['financial']['metrics'][key]-left['financial']['metrics'][key],2)
                              for key in ('monthly_surplus','minimum_cash_balance','ending_cash')}
    return dict(left=left, right=right, ownership_years=request.ownership_years,
                financial_difference_right_minus_left=financial_difference,
                difference_right_minus_left=dict(monthly_cost=round(right['monthly_cost']-left['monthly_cost'], 2),
                                                 period_cost=round(right['period_cost']-left['period_cost'], 2)),
                usage=dict(annual_distance_km=request.annual_distance_km, fuel_price_twd_l=request.fuel_price_twd_l),
                source='derived', excludes=['purchase_price', 'loan_payments', 'depreciation', 'inflation'])
