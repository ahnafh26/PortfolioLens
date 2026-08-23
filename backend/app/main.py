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

# "production" hides /docs, /redoc, /openapi.json and adds HSTS -- set on the public deployment,
# left unset (defaults to dev-friendly) for local development.
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "development") == "production"

MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024  # 1MB; largest legitimate payload is an export request

app = FastAPI(
    title="PortfolioLens API",
    description="Portfolio risk analysis and optimization engine.",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects oversized requests via Content-Length before they reach body parsing."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)

# frontend is on a different origin, needs CORS. comma-separated list via env in prod.
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
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
