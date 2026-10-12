"""Vehicle-only costs; no personal profile or affordability inference."""
from pydantic import Field
from typing import Literal
from app.decision_schemas import StrictModel, VehicleDecisionRequest
from app.scenario_schemas import VehiclePurchaseScenarioInput, SourcedDecimal, ValueSource
from app.services.vehicle_decision import resolve, ownership_cost_summary
from app.services.scenario_engine import build_scenario
from app.services.calendar_period import YearMonth
from app.vehicle_catalog import get_vehicle


class StandaloneVehicleCostRequest(StrictModel):
    vehicle_catalog_id: str | None = Field(default=None, max_length=80)
    payload: VehiclePurchaseScenarioInput
    ownership_years: Literal[1,3,5] = 5


def estimate_vehicle_costs(request: StandaloneVehicleCostRequest):
    payload=request.payload.model_copy(deep=True)
    # Without personal expenses, an existing transportation offset cannot be verified.
    payload.monthly_transportation_offset=SourcedDecimal(value=0, source=ValueSource.system_assumption)
    req=VehicleDecisionRequest.model_validate(dict(
        vehicle_catalog_id=request.vehicle_catalog_id,
        profile=dict(salary=0,balance=0,fixed_expense=0,variable_expense=0,required_monthly_debt=0,raise_rate=0,inflation_rate=0),
        start_period='2000-01',scenario=dict(scenario_id='standalone-costs',scenario_type='vehicle_purchase',
                                           target_period='2000-02',horizon_months=60,payload=payload.model_dump(mode='json'))))
    req,_=resolve(req)
    build=build_scenario(req.scenario,YearMonth.parse(req.start_period))
    if build.missing_fields:
        raise ValueError('請完成車價與貸款條件。')
    months=request.ownership_years*12
    costs=ownership_cost_summary(req,build,horizon_months=months)
    for item in costs['items']:
        item['annual_amount']=round(item['period_total']/request.ownership_years,2)
    return dict(purchase_price=float(payload.purchase_price.value),ownership_years=request.ownership_years,
                annual_running_cost=round(costs['ownership_total']/request.ownership_years,2),
                ownership_costs=costs,
                selected_vehicle=get_vehicle(request.vehicle_catalog_id) if request.vehicle_catalog_id else None,
                loan_details=[fact.model_dump(mode='json') for fact in build.derived_values],
                source='derived',scope='vehicle_only',horizon_months=months,
                excludes=['affordability','personal_cash_balance','inflation','resale_value','depreciation','transportation_offset'])
