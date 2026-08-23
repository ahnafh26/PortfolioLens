from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ai, contagion, portfolio, tickers

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="PortfolioLens API",
    description="Portfolio risk analysis and optimization engine.",
    version="1.0.0",
)

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
