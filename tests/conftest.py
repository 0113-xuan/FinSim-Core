from dataclasses import replace

import pytest

from app.services.rate_limit import ai_rate_limiter
from app.services import intent_router


@pytest.fixture(autouse=True)
def reset_ai_rate_limit_between_tests():
    """Keep API tests independent while preserving production rate limiting."""
    ai_rate_limiter.hits.clear()
    yield
    ai_rate_limiter.hits.clear()


@pytest.fixture(autouse=True)
def disable_live_intent_router(monkeypatch):
    monkeypatch.setattr(intent_router, "settings", replace(intent_router.settings, typesafe_api_key=""))
