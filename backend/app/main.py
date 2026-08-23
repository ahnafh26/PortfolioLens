from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.routers import ai, contagion, portfolio, tickers

logging.basicConfig(level=logging.INFO)

MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024  # 1MB; largest legitimate payload is an export request

app = FastAPI(
    title="PortfolioLens API",
    description="Portfolio risk analysis and optimization engine.",
    version="1.0.0",
)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized requests via Content-Length before they reach body parsing."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)

# frontend is on a different origin, needs CORS. comma-separated list via env in prod.
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(tickers.router)
app.include_router(ai.router)
app.include_router(contagion.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
