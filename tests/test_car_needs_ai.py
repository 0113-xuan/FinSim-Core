"""P3 contract/security tests. Fixtures are labels, not live-model accuracy claims."""
import asyncio
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.car_needs_ai_schemas import NeedsExtractionRequest, ParsedCarNeeds
from app.recommendation_schemas import CarNeedsRequest
from app.services import car_needs_extraction as service
from app.services.ai_provider import AIProviderError
from main import app, get_onboarding_ai_provider

CASES = json.loads((Path(__file__).parent / 'fixtures/car_needs_p3_cases.json').read_text(encoding='utf-8'))
CONTEXT = dict(body_types=[], avoid_body_types=[], priorities=['comfort'], purposes=['commute'], powertrains=[], ownership_years=5)


class MockProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def extract(case=CASES[0], context=None):
    request = NeedsExtractionRequest(schema_version='2.0', text=case['text'], revision=12, related_answers=context or CONTEXT)
    provider = MockProvider(case['expected'])
    return asyncio.run(service.extract_car_needs(request, provider, provider_name='gemini')), provider


def handoff(metadata, text):
    context = copy.deepcopy(CONTEXT)
    for c in metadata.candidates:
        service.apply_confirmed(context, c.model_dump())
    metadata.accepted_ids = [c.id for c in metadata.candidates]
    return dict(schema_version='1.1', revision=12+len(metadata.candidates), status='confirmed', currency='TWD',
        background=dict(occupation=None),
        constraints=dict(budget_max=2000000, budget_basis='vehicle_price', min_seats=3, avoid_body_types=context['avoid_body_types']),
        usage=dict(purposes=context['purposes'], monthly_distance_km=1000, usual_passengers=3, ownership_years=context['ownership_years'],
                   parking_type='own', monthly_parking=0, home_charging='unknown', public_charging='unknown'),
        preferences={k:context[k] for k in ('body_types','priorities','powertrains')}, financial_profile=None,
        payment=dict(payment_method='cash',down_payment=None,annual_interest_rate=None,loan_term_months=None),
        free_text=text,extraction=metadata.model_dump(),field_sources={},
        recommendation_handoff=dict(status='ready_for_p2',engine_connected=True))


@pytest.mark.parametrize('case', CASES, ids=lambda c:c['id'])
def test_annotated_candidates_validate_and_preserve_evidence(case):
    metadata, provider = extract(case)
    assert [c.model_dump(include={'field','operation','value','evidence'}) for c in metadata.candidates] == case['expected']['candidates']
    assert metadata.accepted_ids == metadata.rejected_ids == []
    assert all(c.evidence in case['text'] for c in metadata.candidates)
    sent = json.loads(provider.calls[0]['user_prompt'])
    assert set(sent) == {'text','related_answers'}
    assert sent['related_answers'] == CONTEXT
    assert 'API' in provider.calls[0]['system_prompt'] or 'untrusted' in provider.calls[0]['system_prompt']


def test_signed_candidates_reach_existing_recommendations():
    metadata, _ = extract()
    payload = handoff(metadata, CASES[0]['text'])
    assert CarNeedsRequest.model_validate(payload).schema_version == '1.1'
    with TestClient(app) as client:
        result = client.post('/decisions/vehicle/recommendations',json=payload)
        assert result.status_code == 200
        assert result.json()['ranked']
        assert all(c['vehicle']['body_type'] != 'suv' for c in result.json()['ranked'])


@pytest.mark.parametrize('mutation', [
    lambda p:p['extraction'].update(receipt='x'*50),
    lambda p:p.update(free_text='changed'),
    lambda p:p['extraction'].update(revision=0),
    lambda p:p['extraction']['candidates'][0].update(evidence='偽造'),
    lambda p:p['extraction'].update(accepted_ids=[]),
    lambda p:p['extraction'].update(accepted_ids=['unknown']),
    lambda p:p['extraction'].update(rejected_ids=['c0']),
    lambda p:p['extraction'].update(expires_at=1),
    lambda p:p['constraints'].update(avoid_body_types=[]),
    lambda p:p.update(schema_version='1.0'),
    lambda p:p.update(revision=9999),
])
def test_tampered_or_unconfirmed_candidates_rejected(mutation):
    metadata, _ = extract()
    payload = handoff(metadata, CASES[0]['text'])
    mutation(payload)
    with pytest.raises(ValidationError):
        CarNeedsRequest.model_validate(payload)


@pytest.mark.parametrize('value', [True,1.0,{},[],None,'unknown'])
def test_strict_candidate_values(value):
    with pytest.raises(ValidationError):
        ParsedCarNeeds.model_validate(dict(candidates=[dict(field='ownership_years',operation='set',value=value,evidence='一年')],unclear=[]))


@pytest.mark.parametrize('change', ['unknown_field','extra','fabricated','contradiction','multiple_duration'])
def test_invalid_provider_results_fail_closed(change):
    result = copy.deepcopy(CASES[0])
    c = result['expected']['candidates'][0]
    if change == 'unknown_field':c['field'] = 'budget_max'
    if change == 'extra':c['price'] = 1
    if change == 'fabricated':c['evidence'] = 'never said this'
    if change == 'contradiction':result['expected']['candidates'].append(dict(c,operation='remove'))
    if change == 'multiple_duration':
        result['text'] = '預計持有五年'
        result['expected']['candidates'] = [dict(field='ownership_years',operation='set',value=v,evidence='預計持有五年') for v in (1,5)]
    with pytest.raises(AIProviderError):extract(result)


def test_conflicts_are_backend_derived_and_receipt_expires(monkeypatch):
    metadata, _ = extract(context=dict(CONTEXT,body_types=['suv']))
    assert metadata.candidates[0].conflict
    metadata, _ = extract(CASES[1])
    assert metadata.candidates[0].operation == 'remove'
    assert metadata.candidates[0].conflict
    payload = handoff(metadata, CASES[1]['text'])
    monkeypatch.setattr(service.time,'time',lambda:metadata.expires_at+1)
    with pytest.raises(ValidationError):CarNeedsRequest.model_validate(payload)


def test_timeout_and_missing_provider(monkeypatch):
    class Slow:
        async def generate_structured(self,**kwargs):await asyncio.sleep(1)
    request = NeedsExtractionRequest(schema_version='2.0',text='test',revision=0,related_answers=CONTEXT)
    monkeypatch.setattr(service,'settings',replace(service.settings,ai_onboarding_timeout_seconds=.001))
    with pytest.raises(AIProviderError,match='逾時'):
        asyncio.run(service.extract_car_needs(request,Slow(),provider_name='gemini'))
    with pytest.raises(AIProviderError):
        asyncio.run(service.extract_car_needs(request,None,provider_name='gemini'))


def test_endpoint_errors_are_safe_and_minimal_context_enforced(monkeypatch):
    monkeypatch.setattr(service,'settings',replace(service.settings,ai_provider='gemini'))
    provider = MockProvider(CASES[0]['expected'])
    app.dependency_overrides[get_onboarding_ai_provider] = lambda:provider
    body = dict(schema_version='2.0',text=CASES[0]['text'],revision=0,related_answers=copy.deepcopy(CONTEXT))
    try:
        with TestClient(app) as client:
            assert client.post('/ai/car-needs/extract',json=body).status_code == 200
            body['related_answers']['salary'] = 50000
            assert client.post('/ai/car-needs/extract',json=body).status_code == 422
            del body['related_answers']['salary']
            provider.result = 'not JSON'
            response = client.post('/ai/car-needs/extract',json=body)
            assert response.status_code == 503
            assert 'not JSON' not in response.text
    finally:app.dependency_overrides.pop(get_onboarding_ai_provider,None)


def test_prompt_uses_existing_native_gemini_schema():
    from app.services.gemini_provider import gemini_json_schema
    schema = gemini_json_schema(ParsedCarNeeds.model_json_schema())
    assert len(json.dumps(schema).encode()) < 8000
    assert 'candidates' in schema['properties']


def test_calendar_statement_cannot_be_promoted_to_ownership_duration():
    case = dict(text='五年後我要出國', expected=dict(candidates=[dict(field='ownership_years',operation='set',value=5,evidence='五年後我要出國')],unclear=[]))
    metadata, _ = extract(case)
    assert metadata.candidates == []
    assert metadata.unclear[0].reason == 'uncertain'


@pytest.mark.parametrize('raw', ['not JSON','```json\n{}\n```','{"candidates":[],"unclear":[],"price":1}'])
def test_existing_provider_parser_rejects_invalid_p3_json(raw):
    from app.services.ai_provider import parse_structured_content
    with pytest.raises(AIProviderError):parse_structured_content(raw,ParsedCarNeeds)


def test_browser_serializer_and_backend_receipt_contract_roundtrip():
    import subprocess
    metadata, _ = extract()
    script = """
const fs=require('fs'),m=require('./static/car-needs-state'),ai=require('./static/car-needs-ai');
const input=JSON.parse(fs.readFileSync(0,'utf8'));let s=m.createState();
Object.assign(s.answers,{budget_max:2000000,usual_passengers:3,monthly_distance_km:1000,parking_type:'own',monthly_parking:0,payment_method:'cash',free_text:input.text},input.context);
s.revision=12;s=ai.attach(s,input.metadata);
for(const c of s.extraction.candidates)s=ai.decide(s,c.id,true,{resolveConflict:true});
process.stdout.write(JSON.stringify(m.serialize(m.confirm(s))));
"""
    result = subprocess.run(['node','-e',script],input=json.dumps(dict(text=CASES[0]['text'],context=CONTEXT,metadata=metadata.model_dump())),
        text=True,capture_output=True,check=True,cwd=Path(__file__).parents[1],encoding='utf-8')
    parsed = CarNeedsRequest.model_validate_json(result.stdout)
    assert parsed.constraints.avoid_body_types == ['suv']
    assert parsed.extraction.accepted_ids == ['c0','c1']


def test_unexpected_provider_error_is_safe_and_manual_fallback_works(monkeypatch, caplog):
    class Broken:
        async def generate_structured(self, **kwargs):
            raise RuntimeError('PRIVATE financial text secret API key')
    monkeypatch.setattr(service,'settings',replace(service.settings,ai_provider='gemini'))
    app.dependency_overrides[get_onboarding_ai_provider] = lambda:Broken()
    try:
        with TestClient(app) as client:
            response = client.post('/ai/car-needs/extract',json=dict(schema_version='2.0',text=CASES[0]['text'],revision=12,related_answers=CONTEXT))
            assert response.status_code == 503
            assert 'PRIVATE' not in response.text and 'PRIVATE' not in caplog.text
            assert 'RuntimeError' in caplog.text and 'generate_structured' in caplog.text
            metadata, _ = extract()
            payload = handoff(metadata,CASES[0]['text'])
            payload.update(schema_version='1.0',extraction=dict(provider='mock',is_real_ai=False,status='not_requested',candidates=[]))
            assert client.post('/decisions/vehicle/recommendations',json=payload).status_code == 200
    finally:app.dependency_overrides.pop(get_onboarding_ai_provider,None)


def test_post_provider_development_errors_are_not_silenced(monkeypatch):
    def broken_key():raise RuntimeError('development error')
    monkeypatch.setattr(service,'_key',broken_key)
    with pytest.raises(RuntimeError,match='development error'):extract()


@pytest.mark.parametrize('field', ['salary','budget_max','balance','receipt','ownership_years','priorities'])
def test_ai_sources_cannot_claim_finances_or_unaccepted_fields(field):
    metadata, _ = extract()
    payload = handoff(metadata,CASES[0]['text'])
    payload['field_sources'][field] = 'user_confirmed_ai'
    with pytest.raises(ValidationError):CarNeedsRequest.model_validate(payload)


def test_partial_acceptance_sources_and_implicit_conflict_removal():
    metadata, _ = extract(context=dict(CONTEXT,body_types=['suv']))
    payload = handoff(metadata,CASES[0]['text'])
    payload['extraction'].update(accepted_ids=['c0'],rejected_ids=['c1'])
    payload['usage']['purposes'] = ['commute']
    payload['field_sources'] = dict(avoid_body_types='user_confirmed_ai',body_types='user_confirmed_ai')
    assert CarNeedsRequest.model_validate(payload)
    payload['field_sources']['purposes'] = 'user_confirmed_ai'
    with pytest.raises(ValidationError):CarNeedsRequest.model_validate(payload)


@pytest.mark.parametrize('key,warn', [('',True),('short',True),('x'*32,False),('金'*11,False)])
def test_signing_startup_warnings_do_not_expose_keys(key,warn):
    warnings = replace(service.settings,car_needs_signing_key=key).startup_warnings()
    relevant = [w for w in warnings if 'CAR_NEEDS_SIGNING_KEY' in w]
    assert bool(relevant) == warn
    if key:assert key not in ' '.join(warnings)


def test_fixed_key_survives_process_key_changes_and_short_key_fails_closed(monkeypatch):
    monkeypatch.setattr(service,'settings',replace(service.settings,car_needs_signing_key='x'*32))
    metadata, _ = extract()
    payload = handoff(metadata,CASES[0]['text'])
    monkeypatch.setattr(service,'_PROCESS_KEY',b'new-worker-key')
    assert CarNeedsRequest.model_validate(payload)
    monkeypatch.setattr(service,'settings',replace(service.settings,car_needs_signing_key='short'))
    with pytest.raises(ValidationError):CarNeedsRequest.model_validate(payload)
    with pytest.raises(AIProviderError):extract()


def test_fixed_signatures_verify_in_an_independent_worker():
    import os
    import sys
    import subprocess
    env = dict(os.environ,CAR_NEEDS_SIGNING_KEY='test-only-worker-key-'+'x'*32)
    writer = 'import time; from app.services.car_needs_extraction import _sign; print(_sign(dict(version=2,issued_at=time.time())))'
    reader = 'import sys; from app.services.car_needs_extraction import _read; assert _read(sys.stdin.read().strip())["version"] == 2; print("verified")'
    receipt = subprocess.run([sys.executable,'-B','-c',writer],env=env,text=True,capture_output=True,check=True).stdout
    result = subprocess.run([sys.executable,'-B','-c',reader],input=receipt,env=env,text=True,capture_output=True,check=True)
    assert result.stdout.strip() == 'verified'
