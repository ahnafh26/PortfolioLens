"""Per-IP, in-process rate limiting (no Redis -- same "single process doesn't need
it" call as cache.py). A plain FastAPI dependency rather than a decorator: slowapi's
decorator wraps the endpoint and breaks FastAPI's forward-ref resolution under
`from __future__ import annotations`, which every module here uses.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

_storage = MemoryStorage()
_strategy = MovingWindowRateLimiter(_storage)

# Off by default: request.client.host (the direct TCP peer) is the only IP a client
# can't spoof. Only trust X-Forwarded-For if the deployment actually sits behind a
# reverse proxy/CDN that sets it -- otherwise anyone can fake their rate-limit identity
# by just sending that header themselves. Takes the last hop, i.e. exactly one trusted
# proxy in front; chained proxies need a hop-count, not just an on/off switch.
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"


def reset_rate_limits() -> None:
    """For tests, see conftest.py."""
    _storage.reset()


def _client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(limit_string: str):
    """Route dependency: dependencies=[Depends(rate_limit("10/minute"))]."""
    item = parse(limit_string)

    def check(request: Request) -> None:
        if not _strategy.hit(item, _client_ip(request)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded, try again shortly")

    return check


# Caps how many Monte Carlo simulations (n_simulations x n_checkpoints x n_assets arrays)
# run at once -- rate limiting alone still lets many different IPs pile up simultaneously.
MAX_CONCURRENT_ANALYSES = int(os.environ.get("MAX_CONCURRENT_ANALYSES", "2"))
_analysis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)


async def limit_concurrent_analysis():
    """Yield dependency: dependencies=[Depends(limit_concurrent_analysis)]. Rejects with 503
    instead of queuing -- an unbounded queue is the same memory problem one step later."""
    if _analysis_semaphore.locked():
        raise HTTPException(status_code=503, detail="Server is busy running other analyses, please try again shortly")
    async with _analysis_semaphore:
        yield
