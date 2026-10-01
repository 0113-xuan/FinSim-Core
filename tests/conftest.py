import pytest

from app.services.rate_limit import ai_rate_limiter


@pytest.fixture(autouse=True)
def reset_ai_rate_limit_between_tests():
    """Keep API tests independent while preserving production rate limiting."""
    ai_rate_limiter.hits.clear()
    yield
    ai_rate_limiter.hits.clear()
