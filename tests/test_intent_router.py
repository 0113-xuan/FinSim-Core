import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from app.services import intent_router as router
from app.services import plan_qa as qa


def decision(choice='knowledge', confidence=0.9):
    return {'type': 'choice', 'choice': choice, 'confidence': confidence,
            'probabilities': {key: float(key == choice) for key in router.CRITERIA}}


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setattr(router, 'settings', replace(router.settings, typesafe_api_key='test-key'))


def transport(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(router.httpx, 'AsyncClient',
                        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_api_contract_and_minimal_state(monkeypatch):
    def handler(request):
        assert str(request.url) == 'https://api.typesafe.ai/v1/systemone'
        assert request.headers['Authorization'] == 'Bearer test-key'
        payload = json.loads(request.content)
        assert payload['state'] == {'question': '什麼是淨資產？'}
        assert payload['questions']['intent']['criteria'] == router.CRITERIA
        return httpx.Response(200, json={'answers': {'intent': decision()}})
    transport(monkeypatch, handler)
    assert asyncio.run(router.route_question('什麼是淨資產？')).choice == 'knowledge'


@pytest.mark.parametrize('payload', [None, {}, {'answers': []},
    {'answers': {'intent': decision(confidence=float('nan'))}},
    {'answers': {'intent': {**decision(), 'choice': 'delete_plan'}}}])
def test_invalid_responses_fall_back(monkeypatch, payload):
    transport(monkeypatch, lambda request: httpx.Response(200, content=json.dumps(payload)))
    assert asyncio.run(router.route_question('問題')) is None


@pytest.mark.parametrize('status', [401, 429, 500])
def test_http_failure_falls_back(monkeypatch, status):
    transport(monkeypatch, lambda request: httpx.Response(status))
    assert asyncio.run(router.route_question('問題')) is None


def test_timeout_falls_back(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout('timeout')
    transport(monkeypatch, handler)
    assert asyncio.run(router.route_question('問題')) is None


def test_missing_key_skips_http(monkeypatch):
    monkeypatch.setattr(router, 'settings', replace(router.settings, typesafe_api_key=''))
    def forbidden(request):
        pytest.fail('unexpected HTTP request')
    transport(monkeypatch, forbidden)
    assert asyncio.run(router.route_question('問題')) is None


def test_unsure_route_falls_through_to_retrieval(monkeypatch):
    async def route(question):
        return router.Decision.model_validate(decision('compare', 0.2))
    monkeypatch.setattr(qa, 'route_question', route)
    result = asyncio.run(qa.answer_plan_question(qa.PlanQARequest(question='什麼是淨資產？'), None))
    assert result['source'] != 'guidance'
    assert result['answer']


@pytest.mark.parametrize('choice,action', [('compare', 'compare'), ('stress', 'stress')])
def test_guidance_routes_skip_calculation_and_generation(monkeypatch, choice, action):
    async def route(question):
        return router.Decision.model_validate(decision(choice, 0.9))
    monkeypatch.setattr(qa, 'route_question', route)
    def forbidden(*args):
        pytest.fail('guidance should not calculate or retrieve')
    monkeypatch.setattr(qa, 'retrieve', forbidden)
    result = asyncio.run(qa.answer_plan_question(qa.PlanQARequest(question='半年後買車呢？'), None))
    assert result['source'] == 'guidance'
    assert result['action'] == action
    assert result['answer']


def test_knowledge_skips_personal_calculation(monkeypatch):
    async def route(question):
        return router.Decision.model_validate(decision())
    monkeypatch.setattr(qa, 'route_question', route)
    def forbidden(*args):
        pytest.fail('knowledge should not calculate private finances')
    monkeypatch.setattr(qa, 'run_plan_calculations', forbidden)
    request = qa.PlanQARequest.model_validate({'question': '現金不足機率是什麼意思？',
        'start_period': '2026-11', 'simulation': {'user_id': 'private', 'months': 12,
        'profile': {'salary': 52000, 'balance': 300000, 'fixed_expense': 18000,
                    'variable_expense': 15000}}})
    result = asyncio.run(qa.answer_plan_question(request, None))
    assert result['source'] == 'extractive'


def test_declined_question_never_reaches_router(monkeypatch):
    async def forbidden(*args):
        pytest.fail('declined question reached router')
    monkeypatch.setattr(qa, 'route_question', forbidden)
    result = asyncio.run(qa.answer_plan_question(qa.PlanQARequest(question='保證我一定賺'), None))
    assert result['source'] == 'declined'
