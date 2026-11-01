"""Shared annual-step inflation for events built by the vehicle scenario engine."""
from app.core.financial_rules import inflation_factor


def inflate_vehicle_events(events, purchase_month, months, inflation_rate):
    result = []
    for event in events:
        raw = event.model_dump()
        if raw['type'] != 'range':
            result.append(raw)
            continue
        # Simulation years are months 1-12, 13-24, etc.; a month-12 purchase
        # incurs only one month at year-one prices. Never extend the horizon.
        for year_start in range(1, months + 1, 12):
            month = max(purchase_month, year_start)
            end = min(year_start + 11, months)
            if month > end:
                continue
            result.append({**raw, 'start_month': month, 'end_month': end,
                           'amount': raw['amount'] * inflation_factor(month, inflation_rate)})
    return result
