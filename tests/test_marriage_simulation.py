import json
import subprocess
from fastapi.testclient import TestClient
from main import app


def test_legacy_marriage_request_includes_one_time_and_monthly_cash():
    script = """
const M=require('./static/planner-model.js');
const profile={monthly_income:60000,cash_balance:1000000,fixed_expense:20000,variable_expense:15000,investment_value:0,monthly_investment:0,emergency_target_months:6};
const event={type:'marriage',name:'結婚',start_period:'2026-11',amount:-200000,monthly_amount:-1000,details:{wedding_cost:500000,gift_income:300000}};
process.stdout.write(JSON.stringify(M.buildSimulationRequest({profile,events:[event],startPeriod:'2026-11',months:12}).request));
"""
    request = json.loads(subprocess.check_output(['node', '-e', script], text=True, encoding='utf-8'))
    client = TestClient(app)
    with_event = client.post('/simulate', json={**request, 'seed': 42})
    baseline = client.post('/simulate', json={**request, 'events': [], 'seed': 42})
    assert with_event.status_code == baseline.status_code == 200
    event_month = with_event.json()['result']['simulation_curve'][0]['balance']
    base_month = baseline.json()['result']['simulation_curve'][0]['balance']
    assert event_month - base_month == -201000
