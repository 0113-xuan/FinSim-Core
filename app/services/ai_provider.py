from __future__ import annotations

import json
from typing import Any, Dict, Protocol, TypeVar

import httpx
import requests
from pydantic import BaseModel, ValidationError

from app.config import settings


StructuredResponse = TypeVar("StructuredResponse", bound=BaseModel)


class AIProviderError(RuntimeError):
    pass


class UnsupportedAIProviderOperation(AIProviderError):
    pass


def parse_structured_content(
    content: str,
    response_schema: type[StructuredResponse],
) -> StructuredResponse:
    if not isinstance(content, str):
        raise AIProviderError("AI provider returned no JSON content")
    try:
        return response_schema.model_validate_json(content)
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIProviderError("AI provider returned invalid structured output") from exc


class AIProvider(Protocol):
    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredResponse],
    ) -> StructuredResponse:
        ...

    def complete_json(self, *, system: str, user: str) -> Dict[str, Any]:
        ...


class OpenAIProvider:
    endpoint = "https://api.openai.com/v1/chat/completions"

    def _headers(self) -> Dict[str, str]:
        if not settings.ai_api_key:
            raise AIProviderError("AI_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredResponse],
    ) -> StructuredResponse:
        payload = {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            },
            "temperature": 0.1,
        }
        last_error: Exception | None = None
        attempts = max(1, settings.ai_max_retries + 1)
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(
                        self.endpoint,
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    message = response.json()["choices"][0]["message"]
                    if message.get("refusal"):
                        raise AIProviderError(f"AI provider refused the request: {message['refusal']}")
                    content = message.get("content")
                    return parse_structured_content(content, response_schema)
                except (httpx.HTTPError, KeyError, IndexError, TypeError, AIProviderError) as exc:
                    last_error = exc
                    if attempt == attempts - 1:
                        break
        if isinstance(last_error, AIProviderError):
            raise last_error
        raise AIProviderError("AI provider request failed") from last_error

    def complete_json(self, *, system: str, user: str) -> Dict[str, Any]:
        """Compatibility path for the existing scenario parser."""
        try:
            response = requests.post(
                self.endpoint,
                headers=self._headers(),
                timeout=settings.ai_timeout_seconds,
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (requests.RequestException, KeyError, IndexError) as exc:
            raise AIProviderError("AI provider request failed") from exc
        except (json.JSONDecodeError, TypeError) as exc:
            raise AIProviderError("AI provider returned non-JSON content") from exc
        if not isinstance(parsed, dict):
            raise AIProviderError("AI provider JSON response must be an object")
        return parsed


def get_ai_provider() -> AIProvider | None:
    if not settings.ai_enabled:
        return None
    if settings.ai_provider == "openai":
        return OpenAIProvider()
    if settings.ai_provider == "gemini":
        from app.services.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
    return None
