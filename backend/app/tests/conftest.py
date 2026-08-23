"""Shared pytest fixtures for the whole test suite."""
from __future__ import annotations

import pytest

from app.limiter import reset_rate_limits
from app.services.cache import clear_all_caches


@pytest.fixture(autouse=True)
def _isolated_caches():
    """Clears TTL caches before every test so mocked data doesn't leak between tests."""
    clear_all_caches()
    yield
    clear_all_caches()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """TestClient hits rate-limited endpoints from the same address across many tests in
    one run; without this, later tests in a file start getting 429s instead of the status
    codes they're actually asserting."""
    reset_rate_limits()
    yield
