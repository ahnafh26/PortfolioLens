from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request

from app.limiter import MAX_CONCURRENT_ANALYSES, limit_concurrent_analysis, rate_limit


def _fake_request(client_host: str = "1.2.3.4") -> Request:
    scope = {
        "type": "http",
        "client": (client_host, 12345),
        "headers": [],
    }
    return Request(scope)


def test_rate_limit_allows_requests_under_the_cap():
    check = rate_limit("3/minute")
    for _ in range(3):
        check(_fake_request())  # no raise


def test_rate_limit_rejects_the_request_over_the_cap():
    check = rate_limit("3/minute")
    for _ in range(3):
        check(_fake_request())

    with pytest.raises(HTTPException) as exc_info:
        check(_fake_request())
    assert exc_info.value.status_code == 429


def test_rate_limit_tracks_each_client_ip_separately():
    check = rate_limit("1/minute")
    check(_fake_request("1.1.1.1"))  # exhausts 1.1.1.1's quota

    check(_fake_request("2.2.2.2"))  # different IP, own quota, should not raise


def test_concurrent_analysis_limiter_rejects_once_capacity_is_full():
    """Directly exercises the semaphore-backed dependency (not through a live HTTP
    request, which would need a genuinely slow endpoint to create real overlap)."""

    async def scenario():
        generators = [limit_concurrent_analysis() for _ in range(MAX_CONCURRENT_ANALYSES)]
        for gen in generators:
            await gen.__anext__()  # runs up to the yield, holding the semaphore open

        try:
            over_capacity = limit_concurrent_analysis()
            with pytest.raises(HTTPException) as exc_info:
                await over_capacity.__anext__()
            assert exc_info.value.status_code == 503
        finally:
            for gen in generators:
                with pytest.raises(StopAsyncIteration):
                    await gen.__anext__()  # advances past yield, releasing the semaphore

    asyncio.run(scenario())


def test_concurrent_analysis_limiter_allows_requests_again_after_release():
    async def scenario():
        gen = limit_concurrent_analysis()
        await gen.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()  # release

        # capacity is free again
        gen2 = limit_concurrent_analysis()
        await gen2.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen2.__anext__()

    asyncio.run(scenario())
