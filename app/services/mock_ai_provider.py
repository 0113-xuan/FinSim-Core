from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel


StructuredResponse = TypeVar("StructuredResponse", bound=BaseModel)


class MockAIProvider:
    """Deterministic structured provider for tests and local development."""

    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self._responses = dict(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredResponse],
    ) -> StructuredResponse:
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response_schema": response_schema,
        })
        for marker, payload in self._responses.items():
            if marker in user_prompt:
                return response_schema.model_validate(deepcopy(payload))
        raise LookupError("No deterministic mock response matched the user prompt")

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        for marker, payload in self._responses.items():
            if marker in user:
                return deepcopy(dict(payload))
        raise LookupError("No deterministic mock response matched the user prompt")
