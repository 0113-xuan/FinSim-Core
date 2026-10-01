"""Planning assumptions, not market price estimates. All are editable."""

ASSUMPTIONS = {
    "raise_rate": dict(value=0, unit="annual_rate", description="薪資維持不變"),
    "inflation_rate": dict(value=.02, unit="annual_rate", description="年度支出通膨規劃假設"),
    "annual_insurance": dict(value=20000, unit="TWD/year", description="保險規劃預算，非報價"),
    "annual_tax": dict(value=12000, unit="TWD/year", description="稅費規劃預算，非稅額查詢"),
    "annual_maintenance_budget": dict(value=18000, unit="TWD/year", description="維護預算，非實際報價"),
    "monthly_fuel_or_energy": dict(value=3000, unit="TWD/month", description="油電規劃預算"),
    "monthly_parking": dict(value=2000, unit="TWD/month", description="停車規劃預算"),
    "monthly_transportation_offset": dict(value=0, unit="TWD/month", description="已包含於原生活費的可取代交通費"),
    "minimum_emergency_fund_months": dict(value=3, unit="months", description="最低預備金要求"),
    "minimum_cash_balance": dict(value=0, unit="TWD", description="最低現金要求"),
    "minimum_monthly_surplus": dict(value=5000, unit="TWD/month", description="購車後最低每月結餘要求"),
}
STRESS_DEFAULTS = dict(income_multiplier=.9, unemployment_months=3, emergency_expense=100000, rate_increase=.02)


def registry():
    return [{"key": key, **value, "source": "system_assumption", "reference": None} for key, value in ASSUMPTIONS.items()]
