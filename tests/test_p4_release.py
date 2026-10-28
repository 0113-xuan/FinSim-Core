import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from app.config import Settings, PINNED_GEMINI_MODEL, resolve_gemini_model
from app.car_needs_ai_schemas import ParsedCarNeeds
from app.services import gemini_provider as module
from app.services.ai_provider import AIProviderError


def test_fixed_model_defaults_and_legacy_alias_resolution(monkeypatch):
    assert Settings().gemini_model == PINNED_GEMINI_MODEL
    monkeypatch.setenv('GEMINI_MODEL','gemini-flash-lite-latest')
    assert Settings.from_env().gemini_model == PINNED_GEMINI_MODEL
    assert module.GeminiProvider(model='gemini-flash-lite-latest').model == PINNED_GEMINI_MODEL
    assert resolve_gemini_model('models/gemini-2.5-flash-lite') == 'gemini-2.5-flash-lite'


@pytest.mark.parametrize('status,count',[(400,1),(401,1),(403,1),(429,3),(503,3)])
def test_only_transient_http_failures_retry(monkeypatch,status,count,caplog):
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(kwargs)
            response=httpx.Response(status,request=httpx.Request('POST',url))
            response.raise_for_status()
    async def sleep(_):pass
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    monkeypatch.setattr(module.asyncio,'sleep',sleep)
    provider=module.GeminiProvider(api_key='private-test-key',model=PINNED_GEMINI_MODEL,max_retries=2)
    with caplog.at_level('INFO'):
        with pytest.raises(AIProviderError):
            asyncio.run(provider.generate_structured(system_prompt='system',user_prompt='private demand',response_schema=ParsedCarNeeds))
    assert len(calls)==count
    assert f'attempts={count}' in caplog.text and 'http_ms=' in caplog.text
    assert 'private demand' not in caplog.text and 'private-test-key' not in caplog.text


def test_live_eval_can_limit_each_request_without_changing_app_defaults(monkeypatch):
    captured=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            captured.append(kwargs['json'])
            return httpx.Response(200,request=httpx.Request('POST',url),json=dict(candidates=[dict(content=dict(parts=[dict(text=json.dumps(dict(candidates=[],unclear=[])))]))]))
    monkeypatch.setattr(module.httpx,'AsyncClient',Client)
    provider=module.GeminiProvider(api_key='test',max_retries=0,max_output_tokens=1024)
    asyncio.run(provider.generate_structured(system_prompt='s',user_prompt='u',response_schema=ParsedCarNeeds))
    assert captured[0]['generationConfig']['maxOutputTokens']==1024
    assert provider.max_retries==0
    assert module.GeminiProvider().max_output_tokens is None


def test_outer_deadline_cancels_initial_http_without_retry(monkeypatch):
    from app.car_needs_ai_schemas import NeedsExtractionRequest
    from app.services import car_needs_extraction as extraction
    calls=[]
    class SlowClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(1)
            await asyncio.sleep(1)
    monkeypatch.setattr(module.httpx,'AsyncClient',SlowClient)
    monkeypatch.setattr(extraction,'settings',replace(extraction.settings,ai_onboarding_timeout_seconds=.01))
    context=dict(body_types=[],avoid_body_types=[],priorities=[],purposes=[],powertrains=[],ownership_years=None)
    request=NeedsExtractionRequest(schema_version='2.0',text='test',revision=0,related_answers=context)
    provider=module.GeminiProvider(api_key='test',max_retries=2)
    with pytest.raises(AIProviderError,match='逾時'):
        asyncio.run(extraction.extract_car_needs(request,provider,provider_name='gemini'))
    assert len(calls)==1
