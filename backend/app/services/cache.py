"""In-process TTL cache for yfinance calls. No Redis, single process doesn't need it."""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import threading
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from cachetools import TTLCache

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# separate cache per data shape so one kind of lookup can't evict another
PRICE_HISTORY_TTL_SECONDS = 60 * 60
COMPANY_INFO_TTL_SECONDS = 24 * 60 * 60  # sector/name barely change
LATEST_PRICE_TTL_SECONDS = 5 * 60  # rebalance needs this fresher

PRICE_HISTORY_CACHE: TTLCache = TTLCache(maxsize=512, ttl=PRICE_HISTORY_TTL_SECONDS)
COMPANY_INFO_CACHE: TTLCache = TTLCache(maxsize=1024, ttl=COMPANY_INFO_TTL_SECONDS)
LATEST_PRICE_CACHE: TTLCache = TTLCache(maxsize=512, ttl=LATEST_PRICE_TTL_SECONDS)

_ALL_CACHES = (PRICE_HISTORY_CACHE, COMPANY_INFO_CACHE, LATEST_PRICE_CACHE)

# TTLCache isn't thread-safe, FastAPI runs sync handlers in a thread pool
_locks = {id(c): threading.Lock() for c in _ALL_CACHES}


def clear_all_caches() -> None:
    """For tests, see conftest.py."""
    for c in _ALL_CACHES:
        c.clear()


def _make_key(*args: object, **kwargs: object) -> str:
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cached_call(cache: TTLCache, *, key_prefix: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Memoize a function's result in `cache`, keyed on its args."""

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        lock = _locks[id(cache)]

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = f"{key_prefix}:{_make_key(*args, **kwargs)}"
            with lock:
                if key in cache:
                    return cache[key]  # type: ignore[no-any-return]
            result = fn(*args, **kwargs)
            with lock:
                cache[key] = result
            return result

        return wrapper

    return decorator
