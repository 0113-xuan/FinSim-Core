"""Guard that the direct comparison does not do discarded full analyses."""
from fastapi.testclient import TestClient
from main import app
from app.services import vehicle_decision
from tests.test_vehicle_cost_comparison import request_data, financial_context


def test_financial_comparison_does_not_run_full_decision_or_boundary(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Comparison must not calculate discarded stress tests or price searches')

    monkeypatch.setattr(vehicle_decision, 'find_limit', forbidden)
    monkeypatch.setattr(vehicle_decision, 'simulate_vehicle_decision', forbidden)
    data = request_data()
    data['financial_context'] = financial_context()
    for side in ('left', 'right'):
        data[side].update(payment_method='financed', down_payment=150000,
                          annual_interest_rate=.03, loan_term_months=60)
    response = TestClient(app).post('/decisions/vehicle/cost-comparison', json=data)
    assert response.status_code == 200
    for side in ('left', 'right'):
        financial = response.json()[side]['financial']
        assert set(financial) == {'baseline', 'metrics', 'constraints', 'ownership_costs', 'source'}
        assert financial['metrics']['monthly_loan_payment'] > 0
