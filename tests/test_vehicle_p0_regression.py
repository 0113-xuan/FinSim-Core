"""Full formal-route regression snapshots captured before P0 final changes."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from main import app

SNAPSHOTS = json.loads((Path(__file__).parent / 'fixtures/p0/vehicle_api_snapshots.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', SNAPSHOTS, ids=lambda case: case['name'])
def test_complete_api_response_matches_preoptimization_snapshot(case):
    response = TestClient(app).post(case['route'], json=case['input'])
    assert response.status_code == 200
    assert response.json() == case['response']


def test_wealthy_unemployment_via_formal_api():
    case = next(c for c in SNAPSHOTS if c['name'] == 'claude_wealthy_unemployment')
    # All actual inputs, including the remaining profile/loan fields, are in the fixture.
    assert case['input']['profile']['balance'] == 5000000
    assert case['input']['profile']['salary'] == 200000
    assert case['input']['scenario']['payload']['purchase_price']['value'] == 500000
    response = TestClient(app).post('/decisions/vehicle', json=case['input'])
    assert response.status_code == 200
    result = response.json()
    unemployment = next(s for s in result['stress_tests'] if s['name'] == 'unemployment')
    assert unemployment['passed'] is True
    checks = {c['key']: c for c in unemployment['constraints']}
    assert checks['minimum_monthly_surplus']['applicable'] is False
    assert checks['minimum_monthly_surplus']['passed'] is None
    for key in ('minimum_cash_balance', 'minimum_emergency_fund_months'):
        check = checks[key]
        assert check.get('applicable', True) is True
        assert check['passed'] is True
        assert check['actual'] >= check['required']
    before = {s['name']: s for s in case['response']['stress_tests']}
    for stress in result['stress_tests']:
        if stress['name'] != 'unemployment':
            assert stress == before[stress['name']]
            assert stress['passed'] is True
