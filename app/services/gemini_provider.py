from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.config import settings
from app.services.ai_provider import (
    AIProviderError,
    StructuredResponse,
    UnsupportedAIProviderOperation,
    parse_structured_content,
)


logger = logging.getLogger(__name__)

MAX_NATIVE_SCHEMA_BYTES = 8_000

GEMINI_SCHEMA_KEYS = {
    "$id",
    "$defs",
    "$ref",
    "$anchor",
    "type",
    "format",
    "title",
    "description",
    "enum",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "anyOf",
    "oneOf",
    "properties",
    "additionalProperties",
    "required",
}


def gemini_json_schema(schema: Any, *, container_key: str | None = None) -> Any:
    if isinstance(schema, list):
        return [gemini_json_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    if container_key in ("properties", "$defs"):
        return {
            key: gemini_json_schema(value)
            for key, value in schema.items()
        }
    return {
        key: gemini_json_schema(value, container_key=key)
        for key, value in schema.items()
        if key in GEMINI_SCHEMA_KEYS
    }


class GeminiProvider:
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = settings.gemini_api_key if api_key is None else api_key
        self.model = settings.gemini_model if model is None else model

    def _endpoint(self) -> str:
        model = self.model.removeprefix("models/").strip()
        if not model:
            raise AIProviderError("Gemini 模型名稱未設定。")
        return f"{self.base_url}/{quote(model, safe='')}:generateContent"

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise AIProviderError("缺少 GEMINI_API_KEY，無法呼叫 Gemini。")
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredResponse],
    ) -> StructuredResponse:
        started = perf_counter()
        success = False
        response_json_schema = gemini_json_schema(
            response_schema.model_json_schema()
        )
        compact_schema = json.dumps(
            response_json_schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        schema_mode = "native"
        request_system_prompt = system_prompt
        generation_config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        }
        if len(compact_schema.encode("utf-8")) <= MAX_NATIVE_SCHEMA_BYTES:
            generation_config["responseJsonSchema"] = response_json_schema
        else:
            schema_mode = "json_with_backend_validation"
            request_system_prompt = (
                f"{system_prompt}\n\n"
                "## Runtime response schema\n"
                "Return JSON that exactly matches this schema. The backend will reject "
                f"all invalid or additional fields.\n{compact_schema}"
            )
        payload = {
            "systemInstruction": {
                "parts": [{"text": request_system_prompt}],
            },
            "contents": [{
                "role": "user",
                "parts": [{"text": user_prompt}],
            }],
            "generationConfig": generation_config,
        }
        last_error: Exception | None = None
        attempts = max(1, settings.ai_max_retries + 1)
        try:
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
                for attempt in range(attempts):
                    try:
                        response = await client.post(
                            self._endpoint(),
                            headers=self._headers(),
                            json=payload,
                        )
                        response.raise_for_status()
                        content = self._extract_text(response.json())
                        try:
                            result = parse_structured_content(content, response_schema)
                        except AIProviderError as exc:
                            raise AIProviderError(
                                "Gemini 回傳格式無效，無法通過後端結構驗證。"
                            ) from exc
                        success = True
                        return result
                    except AIProviderError:
                        raise
                    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                        last_error = exc
                        if attempt == attempts - 1:
                            break
            raise AIProviderError("Gemini 請求失敗，請稍後再試。") from last_error
        finally:
            logger.info(
                "AI provider request provider=gemini model=%s schema_mode=%s "
                "duration_ms=%.1f success=%s",
                self.model,
                schema_mode,
                (perf_counter() - started) * 1000,
                success,
            )

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        raise UnsupportedAIProviderOperation(
            "Gemini provider 不支援舊版情境解析操作。"
        )

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not candidates:
            block_reason = payload.get("promptFeedback", {}).get("blockReason")
            if block_reason:
                raise AIProviderError(f"Gemini 已阻擋此請求：{block_reason}")
            raise AIProviderError("Gemini 未回傳可用的候選結果。")
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
        if not text:
            raise AIProviderError("Gemini 回應不含可驗證的 JSON 內容。")
        return text
