import asyncio
import json
import logging
from dataclasses import replace

import pytest
from pydantic import BaseModel

import app.services.ai_provider as ai_provider_module
import app.services.gemini_provider as gemini_provider_module
from app.config import Settings
from app.extraction_schemas import FinancialExtractionResult
from app.services.ai_provider import AIProviderError, get_ai_provider
from app.services.financial_answer_extraction import extract_financial_answer
from app.services.gemini_provider import GeminiProvider
from app.services.mock_ai_provider import MockAIProvider
from app.services.prompt_loader import load_prompt


def extraction_payload(**overrides):
    payload = {
        "fields": [],
        "variable_expense_allocation": [],
        "debts": [],
        "future_plans": [],
        "future_plan_conflicts": [],
        "ambiguities": [],
        "conflicts": [],
    }
    payload.update(overrides)
    return payload


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [{
                "content": {
                    "parts": [{"text": self.text}],
                },
            }],
        }


class FailingResponse:
    def __init__(self):
        self.request = gemini_provider_module.httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com/test",
        )
        self.status_code = 429

    def raise_for_status(self):
        response = gemini_provider_module.httpx.Response(
            429,
            request=self.request,
        )
        raise gemini_provider_module.httpx.HTTPStatusError(
            "rate limited",
            request=self.request,
            response=response,
        )


def install_fake_client(monkeypatch, text, captured=None):
    captured = captured if captured is not None else {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse(text)

    monkeypatch.setattr(gemini_provider_module.httpx, "AsyncClient", FakeClient)
    return captured


def test_gemini_provider_initialization():
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash-lite")
    assert provider.model == "gemini-2.5-flash-lite"
    assert provider._endpoint().endswith(
        "/gemini-2.5-flash-lite:generateContent"
    )


def test_missing_gemini_api_key_fails_safely(caplog):
    provider = GeminiProvider(api_key="", model="gemini-2.5-flash-lite")
    with caplog.at_level(logging.INFO):
        with pytest.raises(AIProviderError, match="缺少 GEMINI_API_KEY"):
            asyncio.run(
                provider.generate_structured(
                    system_prompt="system",
                    user_prompt="user",
                    response_schema=FinancialExtractionResult,
                )
            )
    assert "provider=gemini" in caplog.text
    assert "success=False" in caplog.text


def test_gemini_uses_prompt_loader_and_validates_complex_json_schema(monkeypatch, caplog):
    payload = extraction_payload()
    captured = install_fake_client(monkeypatch, json.dumps(payload))
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash-lite")
    with caplog.at_level(logging.INFO):
        result = asyncio.run(
            extract_financial_answer(
                provider=provider,
                answer="我月薪五萬",
                current_values={},
                current_question=None,
            )
        )
    request = captured["request"]
    generation_config = request["json"]["generationConfig"]
    assert result == FinancialExtractionResult.model_validate(payload)
    system_text = request["json"]["systemInstruction"]["parts"][0]["text"]
    assert system_text.startswith(load_prompt("financial_answer_extraction.md"))
    assert "## Runtime response schema" in system_text
    assert generation_config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" not in generation_config
    assert "schema_mode=json_with_backend_validation" in caplog.text
    assert request["headers"]["x-goog-api-key"] == "test-key"
    assert "test-key" not in caplog.text
    assert "我月薪五萬" not in caplog.text
    assert "success=True" in caplog.text


def test_gemini_uses_native_schema_for_small_responses(monkeypatch):
    class SmallResponse(BaseModel):
        value: str

    captured = install_fake_client(monkeypatch, json.dumps({"value": "ok"}))
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-lite-latest")
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="system",
            user_prompt="user",
            response_schema=SmallResponse,
        )
    )
    generation_config = captured["request"]["json"]["generationConfig"]
    assert result.value == "ok"
    assert "value" in generation_config["responseJsonSchema"]["properties"]
    assert "pattern" not in json.dumps(generation_config["responseJsonSchema"])


@pytest.mark.parametrize(
    "response_text",
    [
        "not-json",
        json.dumps(extraction_payload(unknown_property=True)),
    ],
)
def test_invalid_json_or_schema_returns_controlled_error(monkeypatch, response_text):
    install_fake_client(monkeypatch, response_text)
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash-lite")
    with pytest.raises(AIProviderError, match="Gemini 回傳格式無效"):
        asyncio.run(
            provider.generate_structured(
                system_prompt="system",
                user_prompt="user",
                response_schema=FinancialExtractionResult,
            )
        )


def test_gemini_http_failure_returns_controlled_error(monkeypatch):
    class FailingClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            return FailingResponse()

    monkeypatch.setattr(gemini_provider_module.httpx, "AsyncClient", FailingClient)
    monkeypatch.setattr(
        gemini_provider_module,
        "settings",
        replace(gemini_provider_module.settings, ai_max_retries=0),
    )
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash-lite")
    with pytest.raises(AIProviderError, match="Gemini 請求失敗"):
        asyncio.run(
            provider.generate_structured(
                system_prompt="system",
                user_prompt="user",
                response_schema=FinancialExtractionResult,
            )
        )


def test_mock_provider_remains_compatible():
    payload = extraction_payload()
    provider = MockAIProvider({"測試訊息": payload})
    result = asyncio.run(
        extract_financial_answer(
            provider=provider,
            answer="測試訊息",
            current_values={},
            current_question=None,
        )
    )
    assert result == FinancialExtractionResult.model_validate(payload)


def test_provider_switching_uses_gemini(monkeypatch):
    configured = replace(
        ai_provider_module.settings,
        ai_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="gemini-2.5-flash-lite",
    )
    monkeypatch.setattr(ai_provider_module, "settings", configured)
    provider = get_ai_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.5-flash-lite"


def test_gemini_environment_variables_are_loaded(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.delenv("AI_ENABLED", raising=False)
    configured = Settings.from_env()
    assert configured.ai_provider == "gemini"
    assert configured.gemini_api_key == "test-key"
    assert configured.gemini_model == "gemini-2.5-flash-lite"
    assert configured.ai_enabled is True
    assert configured.ai_provider_ready() is True
