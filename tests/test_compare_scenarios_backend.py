"""The comparison page runs each scenario through the existing endpoints with one seed.

These tests pin the two properties its wording relies on: every scenario sees the same
historical draws, and the inputs the page sends (car + job events from different plans)
are accepted and move the numbers in the expected direction.
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
START = '2027-01'
PROFILE = dict(salary=60000, fixed_expense=20000, variable_expense=15000, balance=900000,
               investment_value=300000, monthly_investment=5000, target_emergency_months=6)


def vehicle(name, price, period='2027-02', financed=False):
    details = dict(purchase_price=price, payment_method='financed' if financed else 'cash')
    if financed:
        details.update(down_payment=price * 0.2, loan_term_months=60, annual_interest_rate=0.03)
    return dict(name=name, purchase_period=period, details=details)


def scenario_request(vehicles=(), job_salary=None, months=60):
    request = dict(profile=PROFILE, months=months, events=[], loans=[], assets=[])
    if vehicles:
        converted = client.post('/planner/vehicle-events', json=dict(
            start_period=START, months=months, inflation_rate=None, vehicles=list(vehicles)))
        assert converted.status_code == 200, converted.text
        body = converted.json()
        request['events'] += body['events']
        request['loans'] += body['loans']
        request['assets'] += body['assets']
    if job_salary is not None:
        request['events'].append(dict(type='salary_change', name='換工作', start_month=3, new_salary=job_salary))
    return request


def monte_carlo(request):
    response = client.post('/monte-carlo', json={**request, 'simulations': 60, 'seed': 42, 'sample_paths': 3})
    assert response.status_code == 200, response.text
    return response.json()


def test_scenarios_with_different_events_share_the_same_historical_draws():
    baseline = monte_carlo(scenario_request())
    car = monte_carlo(scenario_request([vehicle('進口車', 1_500_000, financed=True)]))
    both = monte_carlo(scenario_request([vehicle('進口車', 1_500_000, financed=True)], job_salary=90000))
    periods = [[path['history_periods'] for path in run['sample_paths']] for run in (baseline, car, both)]
    assert periods[0] == periods[1] == periods[2]
    # Same draws, different events: only the events can explain a different result.
    assert baseline['net_worth_percentiles'] != car['net_worth_percentiles']
    assert car['net_worth_percentiles'] != both['net_worth_percentiles']


def test_same_inputs_and_seed_reproduce_the_same_comparison():
    request = scenario_request([vehicle('國產車', 800_000)], job_salary=80000)
    assert monte_carlo(request) == monte_carlo(request)


def test_two_different_cars_in_separate_scenarios_are_ranked_by_cost():
    cheap = scenario_request([vehicle('國產車', 600_000)])
    pricey = scenario_request([vehicle('進口車', 2_000_000)])
    cheap_result, pricey_result = monte_carlo(cheap), monte_carlo(pricey)
    assert cheap_result['net_worth_percentiles']['p50'] > pricey_result['net_worth_percentiles']['p50']


def test_a_higher_paying_job_improves_the_median_net_worth_of_the_same_car():
    car = [vehicle('國產車', 800_000)]
    same_job = monte_carlo(scenario_request(car))
    better_job = monte_carlo(scenario_request(car, job_salary=100000))
    assert better_job['net_worth_percentiles']['p50'] > same_job['net_worth_percentiles']['p50']


def test_the_payload_sizes_the_page_sends_stay_small():
    # The page asks for no sample paths, so scenarios do not carry unused path data.
    request = scenario_request([vehicle('國產車', 800_000)])
    response = client.post('/monte-carlo', json={**request, 'simulations': 30, 'seed': 42, 'sample_paths': 0})
    assert response.status_code == 200
    assert response.json()['sample_paths'] == []
    assert response.json()['monthly_bands']['net_worth']['p50']
