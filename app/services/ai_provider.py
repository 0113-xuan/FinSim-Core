from __future__ import annotations

import json
from typing import Any, Dict, Protocol

import requests

from app.config import settings


class AIProvider(Protocol):
    def complete_json(self, *, system: str, user: str) -> Dict[str, Any]:
        ...


class OpenAIProvider:
    def complete_json(self, *, system: str, user: str) -> Dict[str, Any]:
        if not settings.ai_api_key:
            raise RuntimeError("AI_API_KEY is not configured")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"},
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
        return json.loads(content)


def get_ai_provider() -> AIProvider | None:
    if not settings.ai_enabled:
        return None
    if settings.ai_provider == "openai":
        return OpenAIProvider()
    return None
