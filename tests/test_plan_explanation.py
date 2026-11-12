import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

from app.services import plan_explanation as service
from app.services.ai_provider import AIProviderError
from app.services.mock_ai_provider import MockAIProvider
from app.services.plan_explanation import (
    AIPlanExplanation,
    ExplanationRejected,
    PlanExplanationRequest,
    build_facts,
    explain_plan,
    template_explanation,
    validate_explanation,
    validate_text,
)
from main import app, get_plan_explanation_provider


CLIENT = TestClient(app)
PROFILE = dict(salary=52000, balance=300000, fixed_expense=18000, variable_expense=15000,
               investment_value=100000, monthly_investment=5000, target_emergency_months=6,
               existing_debts=[dict(name='學貸', monthly_payment=3000, remaining_months=24)])
SIMULATION = dict(profile=PROFILE, months=60,
                  events=[dict(type='one_time', name='出國', month=5, amount=-80000)])
EVENTS = [dict(name='出國', type='one_time', start_period='2027-03', summary='-$80,000.00')]
BODY = dict(simulation=SIMULATION, start_period='2026-11', events=EVENTS, emergency_target_months=6)
VEHICLE = dict(purchase_price=849000, payment_method='financed', down_payment=300000,
               loan_term_months=60, annual_interest_rate=.025)
VALID = dict(
    headline='最低現金會在 {minimum_cash_period} 降到 {minimum_cash}',
    paragraphs=['每月收入 {monthly_income}，扣掉支出、貸款與投資後還剩 {monthly_surplus}。',
                '期末淨資產中位數是 {net_worth_p50}。這是模擬結果，不是財務建議。'],
    watch_points=['「{event_1_name}」會在 {event_1_period} 讓現金減少。'],
    suggestions=['可以考慮提高預備金。'],
)
MARKER = '事實表'
_CALCULATED = {}
_run_plan_calculations = service.run_plan_calculations


def memoized_calculations(simulation):
    # The calculation is deterministic; reuse it so each test does not rerun 300 trials.
    key = simulation.model_dump_json()
    if key not in _CALCULATED:
        _CALCULATED[key] = _run_plan_calculations(simulation)
    return copy.deepcopy(_CALCULATED[key])


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    monkeypatch.setattr(service, 'run_plan_calculations', memoized_calculations)
    service._cache.clear()
    yield
    service._cache.clear()
    app.dependency_overrides.pop(get_plan_explanation_provider, None)


def facts_for(body):
    request = PlanExplanationRequest.model_validate(body)
    result, mc = memoized_calculations(request.simulation)
    return build_facts(request.simulation, result, mc, start_period=request.start_period, events=request.events,
                       vehicles=request.vehicles, emergency_target_months=request.emergency_target_months)


def by_id(facts):
    return {fact['id']: fact for fact in facts}


def explain(body, provider):
    app.dependency_overrides[get_plan_explanation_provider] = lambda: provider
    response = CLIENT.post('/ai/plan-explanation', json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_facts_match_simulate_and_monte_carlo_endpoints_exactly():
    facts = by_id(facts_for(BODY))
    simulated = CLIENT.post('/simulate', json={**SIMULATION, 'seed': 42}).json()['result']['summary']
    mc = CLIENT.post('/monte-carlo', json={**SIMULATION, 'simulations': 2000, 'seed': 42}).json()
    assert facts['minimum_cash']['raw'] == simulated['minimum_cash_balance']
    assert facts['shortfall_probability']['raw'] == mc['probability_cash_shortfall']
    assert facts['net_worth_p50']['raw'] == mc['net_worth_percentiles']['p50']
    assert facts['ending_net_worth']['raw'] == simulated['final_net_worth']
    assert facts['real_net_worth_p50']['raw'] == mc['real_net_worth_percentiles']['p50']


def test_facts_without_vehicle_have_formatted_values_and_no_vehicle_entries():
    facts = by_id(facts_for(BODY))
    assert facts['monthly_income']['value'] == 'NT$52,000'
    assert facts['monthly_expense']['raw'] == 33000
    assert facts['monthly_debt_payment']['raw'] == 3000
    assert facts['monthly_surplus']['value'] == 'NT$11,000'
    assert facts['minimum_cash_period']['value'] == '2027-03'
    assert facts['end_period']['value'] == '2031-10'
    assert facts['months']['value'] == '60 個月'
    assert facts['emergency_target_months']['value'] == '6 個月'
    assert 'first_negative_period' not in facts and facts['never_negative']['raw'] is True
    assert facts['shortfall_probability']['value'].endswith('%')
    assert facts['event_1_name']['value'] == '出國' and facts['event_1_summary']['value'] == '-$80,000.00'
    assert facts['largest_drop_period']['value'] == '2027-03'
    assert facts['largest_drop_event']['value'] == '出國'
    assert not any(fact_id.startswith('vehicle_') for fact_id in facts)
    assert all(fact['value'].count('.') == 0 for fact in facts.values() if fact['value'].startswith('NT$'))


def test_facts_with_vehicle_use_planner_vehicle_conversion():
    converted = CLIENT.post('/planner/vehicle-events', json=dict(
        start_period='2026-11', months=60, inflation_rate=None,
        vehicles=[dict(name='買車', purchase_period='2027-03', details=VEHICLE)])).json()
    simulation = copy.deepcopy(SIMULATION)
    simulation['events'] = converted['events']
    simulation['loans'] = converted['loans']
    simulation['assets'] = converted['assets']
    body = dict(simulation=simulation, start_period='2026-11', vehicles=converted['vehicles'],
                events=[dict(name='買車', type='vehicle_purchase', start_period='2027-03', summary='車價 $849,000.00，貸款 60 期')])
    facts = by_id(facts_for(body))
    car = converted['vehicles'][0]
    assert facts['vehicle_1_one_time_cash']['raw'] == car['one_time_cash']
    assert facts['vehicle_1_monthly_payment']['raw'] == car['monthly_loan_payment'] > 0
    assert facts['vehicle_1_total_interest']['raw'] == car['total_loan_interest']
    assert facts['vehicle_1_period']['value'] == '2027-03'
    simulated = CLIENT.post('/simulate', json={**simulation, 'seed': 42}).json()['result']['summary']
    assert facts['minimum_cash']['raw'] == simulated['minimum_cash_balance']
    assert facts['largest_drop_period']['value'] == '2027-03'
    assert facts['largest_drop_event']['value'] == '買車'


def test_negative_cash_adds_first_negative_period():
    body = copy.deepcopy(BODY)
    body['simulation']['events'][0]['amount'] = -2_000_000
    facts = by_id(facts_for(body))
    assert facts['first_negative_period']['value'] == '2027-03'
    assert facts['never_negative']['raw'] is False
    explanation = template_explanation(list(facts.values()))
    assert '{first_negative_period}' in explanation.headline
    assert not any('{minimum_emergency_months}' in point for point in explanation.watch_points)


@pytest.mark.parametrize('text', ['最低現金是 751822', '最低現金是 ７５萬', '最低現金是 {made_up_fact}', '現' * 201])
def test_validation_rejects_digits_unknown_ids_and_long_text(text):
    facts = by_id(facts_for(BODY))
    with pytest.raises(ExplanationRejected):
        validate_text(text, facts, 200)


def test_validation_splits_valid_text_into_segments():
    facts = by_id(facts_for(BODY))
    segments = validate_text('最低現金會在 {minimum_cash_period} 降到 {minimum_cash}。', facts, 200)
    assert segments == [
        {'text': '最低現金會在 '},
        {'fact': 'minimum_cash_period', 'value': '2027-03', 'label': '最低現金發生月份'},
        {'text': ' 降到 '},
        {'fact': 'minimum_cash', 'value': facts['minimum_cash']['value'], 'label': '最低現金'},
        {'text': '。'},
    ]
    # Fact ids may contain digits; only the free text is checked.
    assert validate_text('{event_1_name}會讓現金減少', facts, 200)[0]['value'] == '出國'
    with pytest.raises(ExplanationRejected):
        validate_text('{event_1_name}', facts, 200)


def test_template_passes_the_same_validation_and_mentions_vehicle_and_uncertainty():
    facts = facts_for(BODY)
    facts.append(dict(id='vehicle_1_name', label='購車名稱', value='買車', raw='買車'))
    facts.append(dict(id='vehicle_1_period', label='購車月份', value='2027-03', raw=5))
    facts.append(dict(id='vehicle_1_one_time_cash', label='一次支出', value='NT$300,000', raw=300000))
    facts.append(dict(id='vehicle_1_monthly_payment', label='每月車貸', value='NT$9,756', raw=9756))
    shortfall = next(f for f in facts if f['id'] == 'shortfall_probability')
    shortfall.update(raw=.12, value='12%')
    emergency = next(f for f in facts if f['id'] == 'minimum_emergency_months')
    emergency.update(raw=2.0, value='2.0 個月')
    sections = validate_explanation(template_explanation(facts), by_id(facts))
    text = lambda items: ''.join(s.get('text') or s['value'] for s in items)
    paragraphs = [text(p) for p in sections['paragraphs']]
    watch = [text(p) for p in sections['watch_points']]
    assert any('NT$300,000' in p and 'NT$9,756' in p for p in paragraphs)
    assert any('不是預測' in w for w in watch)
    assert any('低於你設定的目標' in w for w in watch)
    assert sections['suggestions'] == []


def test_disabled_provider_returns_template():
    data = explain(BODY, None)
    assert data['source'] == 'template' and data['fallback_reason'] == 'disabled'
    assert data['model'] is None
    assert data['disclaimer'].startswith('這段說明由系統依規則產生')


def test_provider_error_returns_template():
    class Broken:
        calls = 0

        async def generate_structured(self, **kwargs):
            Broken.calls += 1
            raise AIProviderError('down')

    data = explain(BODY, Broken())
    assert data['source'] == 'template' and data['fallback_reason'] == 'provider_error'
    assert Broken.calls == 1


def test_timeout_returns_provider_error(monkeypatch):
    class Slow:
        async def generate_structured(self, **kwargs):
            await asyncio.sleep(1)

    monkeypatch.setattr(service, 'AI_BUDGET_SECONDS', .01)
    data = asyncio.run(explain_plan(PlanExplanationRequest.model_validate(BODY), Slow()))
    assert data['fallback_reason'] == 'provider_error'


def test_digits_twice_returns_invalid_output_after_exactly_two_calls():
    bad = {**VALID, 'headline': '最低現金是 751,822 元'}
    provider = MockAIProvider({MARKER: bad})
    data = explain(BODY, provider)
    assert data['source'] == 'template' and data['fallback_reason'] == 'invalid_output'
    assert len(provider.calls) == 2
    assert '751,822 元' not in str(data)
    assert '沒有通過檢查' in provider.calls[1]['user_prompt']


def test_retry_succeeds_after_one_invalid_output():
    class Flaky(MockAIProvider):
        async def generate_structured(self, **kwargs):
            payload = {**VALID, 'headline': '有 3 個問題'} if not self.calls else VALID
            self.calls.append(kwargs)
            return AIPlanExplanation.model_validate(payload)

    provider = Flaky({})
    data = explain(BODY, provider)
    assert data['source'] == 'ai' and len(provider.calls) == 2


def test_same_request_is_cached_and_ai_called_once():
    provider = MockAIProvider({MARKER: VALID})
    first = explain(BODY, provider)
    second = explain(BODY, provider)
    assert first == second and len(provider.calls) == 1
    changed = copy.deepcopy(BODY)
    changed['emergency_target_months'] = 3
    explain(changed, provider)
    assert len(provider.calls) == 2


def test_template_results_are_not_cached():
    explain(BODY, None)
    assert service._cache == {}


def test_endpoint_with_mock_provider_values_all_come_from_facts():
    provider = MockAIProvider({MARKER: VALID})
    data = explain(BODY, provider)
    assert data['source'] == 'ai' and data['fallback_reason'] is None
    assert data['disclaimer'].startswith('這段說明由 AI')
    facts = {(f['id'], f['value']) for f in data['facts']}
    sections = [data['headline'], *data['paragraphs'], *data['watch_points'], *data['suggestions']]
    fact_segments = [s for section in sections for s in section if 'fact' in s]
    assert fact_segments
    assert all((s['fact'], s['value']) in facts for s in fact_segments)
    assert all(set(f) == {'id', 'label', 'value'} for f in data['facts'])


def test_prompt_sends_only_fact_table_without_account_data():
    provider = MockAIProvider({MARKER: VALID})
    body = copy.deepcopy(BODY)
    body['simulation']['user_id'] = 'user-secret-id'
    explain(body, provider)
    prompt = provider.calls[0]['user_prompt']
    assert 'user-secret-id' not in prompt and 'raw' not in prompt
    assert '"id": "minimum_cash"' in prompt and '出國' in prompt
    system = provider.calls[0]['system_prompt']
    assert '{minimum_cash}' in system and '不是預測' in system and '不是財務建議' in system


def test_logs_exclude_event_names_and_prompt(caplog):
    caplog.set_level('INFO', logger='app.services.plan_explanation')
    explain(BODY, MockAIProvider({MARKER: VALID}))
    logged = caplog.text
    assert 'source=ai' in logged
    assert '出國' not in logged and 'NT$' not in logged


@pytest.mark.parametrize('text', ['約三十萬元', '六個月', '十二個月', '百分之五', '兩成', '三倍', '半年',
                                  '三十萬', '一千元', '一筆', '百分之十二'])
def test_validation_rejects_chinese_numerals(text):
    facts = by_id(facts_for(BODY))
    with pytest.raises(ExplanationRejected, match='中文數字'):
        validate_text(f'{text}的情況', facts, 200)


@pytest.mark.parametrize('text', ['一次性支出', '第一次現金小於零', '一年後', '一起', '同一個月', '一直', '{minimum_cash}',
                                  '一般', '一定要', '一些', '每一個月', '一部分', '{event_1_name}在同一個月'])
def test_validation_keeps_everyday_words(text):
    facts = by_id(facts_for(BODY))
    assert validate_text(f'{text}的情況', facts, 200)


def vehicle_body():
    converted = CLIENT.post('/planner/vehicle-events', json=dict(
        start_period='2026-11', months=60, inflation_rate=None,
        vehicles=[dict(name='買車', purchase_period='2027-03', details=VEHICLE)])).json()
    simulation = {**copy.deepcopy(SIMULATION), 'events': converted['events'], 'loans': converted['loans'],
                  'assets': converted['assets']}
    return dict(simulation=simulation, start_period='2026-11', vehicles=converted['vehicles'],
                events=[dict(name='買車', type='vehicle_purchase', start_period='2027-03', summary='車價 $849,000.00，貸款 60 期')])


def negative_body():
    body = copy.deepcopy(BODY)
    body['simulation']['events'][0]['amount'] = -2_000_000
    return body


@pytest.mark.parametrize('make_body', [lambda: BODY, vehicle_body, negative_body], ids=['no_vehicle', 'vehicle', 'negative'])
def test_template_passes_chinese_numeral_rule(make_body):
    facts = facts_for(make_body())
    explanation = template_explanation(facts)
    sections = validate_explanation(explanation, by_id(facts))
    assert sections['headline'] and len(sections['paragraphs']) >= 3
    if make_body is vehicle_body:
        assert any('{vehicle_1_one_time_cash}' in p for p in explanation.paragraphs)
    if make_body is negative_body:
        assert any('{first_negative_period}' in w for w in explanation.watch_points)


def test_amounts_percents_and_months_are_rounded_without_decimals():
    from app.services.plan_explanation import format_money, format_months, format_percent

    assert format_money(1234567.89) == 'NT$1,234,600'
    assert format_money(-249.9) == '-NT$200'
    assert format_money(-30) == 'NT$0'
    assert format_percent(0.0333) == '3%'
    assert format_percent(0.002) == '不到 1%'
    assert format_percent(0) == '0%'
    assert format_months(6.4) == '6 個月'
