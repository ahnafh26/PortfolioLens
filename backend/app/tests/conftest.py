"""Shared pytest fixtures for the whole test suite."""
from __future__ import annotations

import pytest

from app.services.cache import clear_all_caches


@pytest.fixture(autouse=True)
def _isolated_caches():
    """Clears TTL caches before every test so mocked data doesn't leak between tests."""
    clear_all_caches()
    yield
    clear_all_caches()
