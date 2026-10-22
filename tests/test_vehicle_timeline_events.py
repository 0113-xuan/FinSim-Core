"""Annual event compaction must preserve month-level behavior, even unrounded."""
import pytest
from app.services import vehicle_decision
from app.services.calendar_period import YearMonth
from tests.test_vehicle_decision import req, request_data


@pytest.mark.parametrize('purchase_month', [1, 12, 13, 24, 25, 58])
@pytest.mark.parametrize('round_output', [True, False])
def test_compact_events_equal_monthly_reference(monkeypatch, purchase_month, round_output):
    data = request_data()
    data['scenario']['target_period'] = str(YearMonth.parse(data['start_period']).add_months(purchase_month))
    data['profile'].update(inflation_rate=.037, raise_rate=.025, fixed_expense_inflates=True)
    data['scenario']['payload']['monthly_transportation_offset'] = dict(value=1234.56, source='user_provided')
    resolved, _ = vehicle_decision.resolve(req(data))
    original_simulate = vehicle_decision.simulate_finance
    captured = []

    def record(profile, **kwargs):
        captured.extend(kwargs['events'])
        return original_simulate(profile, **kwargs)

    monkeypatch.setattr(vehicle_decision, 'simulate_finance', record)
    compact, build = vehicle_decision.run_timeline(resolved, stress='unemployment', round_output=round_output)
    ownership = [e for e in captured if e.get('name') in vehicle_decision.OWNERSHIP]
    assert len(ownership) <= 6 * 5
    for month in range(1, 61):
        active = [e for e in ownership if e['start_month'] <= month <= e['end_month']]
        assert len(active) == (6 if month >= purchase_month else 0)
        original_amounts = {e.name:e.amount for e in build.events if e.type == 'range'}
        for event in active:
            assert event['amount'] == original_amounts[event['name']] * (1 + .037) ** ((month - 1) // 12)

    def monthly_reference(profile, **kwargs):
        expanded = []
        for event in kwargs['events']:
            if event.get('name') not in vehicle_decision.OWNERSHIP:
                expanded.append(event)
                continue
            for month in range(event['start_month'], event['end_month'] + 1):
                expanded.append({**event, 'start_month':month, 'end_month':month})
        return original_simulate(profile, **{**kwargs, 'events':expanded})

    monkeypatch.setattr(vehicle_decision, 'simulate_finance', monthly_reference)
    monthly, _ = vehicle_decision.run_timeline(resolved, stress='unemployment', round_output=round_output)
    assert compact == monthly
