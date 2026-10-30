import pytest

from app import ratelimit


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Each test starts with an empty rate-limit window so tests cannot affect each other."""
    ratelimit.triage_limiter._hits.clear()
    yield
    ratelimit.triage_limiter._hits.clear()
