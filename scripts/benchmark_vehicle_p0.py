"""Reproducible full API snapshots and warm timings; no AI/network provider calls.

Capture once before changing services:
  python scripts/benchmark_vehicle_p0.py --capture --output docs/p0-final-before.json
Compare after changes:
  python scripts/benchmark_vehicle_p0.py --output docs/p0-final-after.json
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from main import app

FIXTURES = ROOT / 'tests/fixtures/p0/vehicle_api_snapshots.json'


def cases():
    single = dict(
        profile=dict(salary=60000, balance=600000, fixed_expense=15000,
                     variable_expense=10000, required_monthly_debt=2000),
        start_period='2026-09',
        scenario=dict(scenario_id='p0-regression', scenario_type='vehicle_purchase',
                      target_period='2026-10', horizon_months=60,
                      payload=dict(scenario_type='vehicle_purchase', payment_method='financed',
                                   purchase_price=dict(value=650000, source='user_provided'),
                                   down_payment=dict(value=150000, source='user_provided'),
                                   loan_term_months=60,
                                   annual_interest_rate=dict(value=.03, source='user_provided'))))
    singles = []

    def add(name, data):
        singles.append(dict(name=name, route='/decisions/vehicle', input=data))

    add('financed_defaults', deepcopy(single))
    cash = deepcopy(single)
    cash['scenario']['target_period'] = '2027-10'  # Month 13: annual-step boundary.
    cash['profile'].update(balance=2000000, raise_rate=.03, inflation_rate=.05,
                           fixed_expense_inflates=True)
    payload = cash['scenario']['payload']
    payload['payment_method'] = 'cash'
    for key in ('down_payment', 'loan_term_months', 'annual_interest_rate'):
        del payload[key]
    payload['monthly_transportation_offset'] = dict(value=2000, source='user_provided')
    add('cash_month13_inflation_offset', cash)

    zero = deepcopy(single)
    zero['profile'].update(inflation_rate=0, raise_rate=0, fixed_expense=0,
                           variable_expense=0, required_monthly_debt=0)
    for key in ('annual_insurance', 'annual_tax', 'annual_maintenance_budget',
                'monthly_fuel_or_energy', 'monthly_parking', 'monthly_transportation_offset',
                'annual_interest_rate'):
        zero['scenario']['payload'][key] = dict(value=0, source='user_provided')
    zero['scenario']['payload']['loan_term_months'] = 12
    add('zero_budget_zero_apr_short_loan', zero)

    late = deepcopy(single)
    late['scenario']['target_period'] = '2031-07'  # Month 58, three-month shock fits.
    late['scenario']['payload']['loan_term_months'] = 84
    late['profile'].update(required_monthly_debt=0, raise_rate=-.01,
                           inflation_rate=.03, fixed_expense_inflates=True,
                           existing_debts=[dict(name='existing', monthly_payment=3500,
                                               remaining_months=14)])
    add('month58_long_loan_expiring_debt', late)

    wealthy = deepcopy(single)
    wealthy['profile'].update(balance=5000000, salary=200000)
    wealthy['scenario']['payload']['purchase_price']['value'] = 500000
    add('claude_wealthy_unemployment', wealthy)

    poor = deepcopy(single)
    poor['profile'].update(balance=50000, salary=30000)
    add('no_feasible_price', poor)

    comparison = dict(
        left=dict(vehicle_id='toyota-cross-gas-luxury', payment_method='financed',
                  down_payment=150000, annual_interest_rate=.03, loan_term_months=60),
        right=dict(vehicle_id='toyota-cross-hybrid-luxury', payment_method='financed',
                   down_payment=150000, annual_interest_rate=.03, loan_term_months=60),
        annual_distance_km=15000, fuel_price_twd_l=30, ownership_years=5,
        financial_context=dict(profile=deepcopy(single['profile']), start_period='2026-09',
                               target_period='2026-10',
                               constraints=dict(minimum_monthly_surplus=5000,
                                                minimum_cash_balance=0,
                                                minimum_emergency_fund_months=3)))
    comparisons = [dict(name='comparison_catalog_financed',
                        route='/decisions/vehicle/cost-comparison', input=deepcopy(comparison))]
    mixed = deepcopy(comparison)
    mixed['financial_context'].update(profile=deepcopy(late['profile']), target_period='2027-09',
                                     monthly_transportation_offset=dict(value=1500))
    mixed['left'] = dict(custom_vehicle=dict(name='custom cash', purchase_price=400000,
                                           monthly_fuel_or_energy=dict(value=1000)))
    mixed['right']['loan_term_months'] = 84
    mixed['ownership_years'] = 3
    comparisons.append(dict(name='comparison_mixed_payment_month12',
                            route='/decisions/vehicle/cost-comparison', input=mixed))
    running = deepcopy(comparison)
    del running['financial_context']
    running['ownership_years'] = 1
    comparisons.append(dict(name='comparison_running_costs_only',
                            route='/decisions/vehicle/cost-comparison', input=running))
    return singles + comparisons


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    if args.capture and FIXTURES.exists():
        parser.error('Refusing to overwrite the pre-change snapshots')
    entries = cases() if args.capture else json.loads(FIXTURES.read_text(encoding='utf-8'))
    report = dict(python=sys.version, platform=platform.platform(), repeats=args.repeats,
                  measurement='TestClient real API, one untimed warm-up per case; no cloud/network latency',
                  cases=[])
    with TestClient(app) as client:
        for entry in entries:
            # Warm up and capture the complete formal-route response.
            response = client.post(entry['route'], json=entry['input'])
            assert response.status_code == 200, (entry['name'], response.text)
            actual = response.json()
            if args.capture:
                entry['response'] = actual
            assert canonical(actual) == canonical(entry['response']), entry['name']
            times = []
            for _ in range(args.repeats):
                start = time.perf_counter()
                response = client.post(entry['route'], json=entry['input'])
                times.append(time.perf_counter() - start)
                assert response.status_code == 200
                assert canonical(response.json()) == canonical(entry['response']), entry['name']
            item = dict(name=entry['name'], route=entry['route'], json_identical=True,
                        sha256=hashlib.sha256(canonical(actual).encode('utf-8')).hexdigest(),
                        seconds=times, median_seconds=statistics.median(times), max_seconds=max(times))
            report['cases'].append(item)
            print(json.dumps(item), flush=True)
    if args.capture:
        FIXTURES.parent.mkdir(parents=True, exist_ok=True)
        FIXTURES.write_text(json.dumps(entries, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
