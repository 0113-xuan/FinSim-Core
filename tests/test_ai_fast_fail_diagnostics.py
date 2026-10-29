"""Offline diagnosis and API regression. No real AI requests or credentials."""
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from app.services import ai_provider, car_needs_extraction, gemini_provider
from app.services.ai_provider import AIProviderError
from scripts import diagnose_car_needs_ai as probe
from tests.test_car_needs_ai import CASES, CONTEXT, MockProvider, extract, handoff


def configured(monkeypatch, **changes):
    value = replace(ai_provider.settings, ai_provider='gemini', ai_enabled=True,
                    gemini_api_key='test-only-not-a-real-key', car_needs_signing_key='', **changes)
    for module in (ai_provider, car_needs_extraction, gemini_provider, probe):
        monkeypatch.setattr(module, 'settings', value)
    return value


@pytest.fixture(autouse=True)
def block_real_ai_http(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail('Offline test attempted external async HTTP')
    monkeypatch.setattr(httpx.AsyncClient, 'post', forbidden)


def body():
    return dict(schema_version='2.0', text=CASES[0]['text'], revision=12, related_answers=CONTEXT)


def test_process_false_overrides_dotenv_true_and_fast_fails(monkeypatch):
    monkeypatch.setenv('AI_ENABLED', 'false')
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only-not-a-real-key')
    value = ai_provider.settings.from_env()
    for module in (ai_provider, car_needs_extraction, probe): monkeypatch.setattr(module, 'settings', value)
    assert ai_provider.get_ai_provider() is None
    assert probe.diagnose()['error_category'] == 'ai_disabled'
    with TestClient(main.app) as client:
        assert client.post('/ai/car-needs/extract', json=body()).status_code == 503


def test_missing_key_returns_503_without_external_request(monkeypatch):
    configured(monkeypatch)
    value = replace(ai_provider.settings, gemini_api_key='')
    for module in (ai_provider, car_needs_extraction, gemini_provider, probe): monkeypatch.setattr(module, 'settings', value)
    assert probe.diagnose()['error_category'] == 'missing_api_key'
    with TestClient(main.app) as client:
        assert client.post('/ai/car-needs/extract', json=body()).status_code == 503


def test_initialization_failure_is_identified_without_secret_output(monkeypatch):
    configured(monkeypatch)
    def broken(): raise ValueError('test-only-not-a-real-key private details')
    monkeypatch.setattr(probe, 'get_ai_provider', broken)
    result = probe.diagnose()
    assert result['error_category'] == 'provider_initialization_failed'
    assert result['initialization_error_type'] == 'ValueError'
    assert result['configuration_ready'] is False
    assert 'private details' not in str(result)
    assert 'test-only-not-a-real-key' not in str(result)


def test_initialization_exception_is_currently_outside_endpoint_handler(monkeypatch):
    configured(monkeypatch)
    def broken(): raise AIProviderError('test-only-private-initialization')
    monkeypatch.setattr(main, 'get_ai_provider', broken)
    # Document the existing boundary, not a claim that initialization errors degrade to 503.
    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.post('/ai/car-needs/extract', json=body())
        assert response.status_code == 500
        assert 'test-only-private' not in response.text


def test_mock_candidate_confirmation_reaches_recommendations(monkeypatch):
    configured(monkeypatch)
    provider = MockProvider(CASES[0]['expected'])
    monkeypatch.setattr(main, 'get_ai_provider', lambda: provider)
    with TestClient(main.app) as client:
        response = client.post('/ai/car-needs/extract', json=body())
        assert response.status_code == 200
        from app.car_needs_ai_schemas import AIExtractionMetadata
        metadata = AIExtractionMetadata.model_validate(response.json())
        assert metadata.accepted_ids == []
        payload = handoff(metadata, CASES[0]['text'])
        recommendation = client.post('/decisions/vehicle/recommendations', json=payload)
        assert recommendation.status_code == 200
        assert recommendation.json()['ranked']


def test_provider_error_preserves_non_ai_recommendations(monkeypatch):
    configured(monkeypatch)
    class Broken:
        async def generate_structured(self, **kwargs): raise AIProviderError('private-test-error')
    monkeypatch.setattr(main, 'get_ai_provider', lambda: Broken())
    with TestClient(main.app) as client:
        response = client.post('/ai/car-needs/extract', json=body())
        assert response.status_code == 503
        assert 'private-test-error' not in response.text
        metadata, _ = extract()
        payload = handoff(metadata, CASES[0]['text'])
        payload.update(schema_version='1.0', extraction=dict(provider='mock', is_real_ai=False, status='not_requested', candidates=[]))
        assert client.post('/decisions/vehicle/recommendations', json=payload).status_code == 200


def test_ready_probe_initializes_without_contacting_model(monkeypatch):
    configured(monkeypatch)
    result = probe.diagnose()
    assert result['configuration_ready'] is True
    assert result['provider_initialized'] is True
    assert result['prompt_loaded'] is True
    assert result['external_http_attempted'] is False
