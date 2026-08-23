# PortfolioLens API

FastAPI backend for PortfolioLens. Fetches price history, runs the risk/return/optimization math, backtests against real historical stress periods, computes rebalancing trades, simulates how a price shock propagates across correlated holdings, generates AI-assisted portfolio insights, and exports PDF/CSV reports.

Quant core is in `app/services/analysis.py`, ticker search in `app/services/ticker_index.py`.

## Requirements

- Python 3.11+
- Internet access (yfinance for prices, NASDAQ Trader for the ticker index build)

## Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Build the ticker search index (once, before first run)

`GET /api/tickers/search` reads from a local SQLite file that isn't checked into the repo:

```bash
python scripts/build_ticker_index.py
```

Downloads `nasdaqlisted.txt` and `otherlisted.txt`, filters out test issues/warrants/rights/units, writes `data/tickers.db` (~11-12k symbols, NASDAQ/NYSE/NYSE American/NYSE Arca/Cboe BZX). Re-run occasionally for new listings. Skipping this step just falls back to a small built-in seed list (~30 tickers), search still works but over a much smaller universe.

## Optional: LLM-narrated AI Assistant

Works fine without any setup, risk signals are computed deterministically and rendered as templated English. For free-form prose instead, wire up a free OpenRouter model:

```bash
cp .env.example .env
# edit .env, set OPENROUTER_API_KEY
```

Free key at [openrouter.ai/keys](https://openrouter.ai/keys), no card needed. See `.env.example` if the default model stops working. The LLM only narrates numbers that were already computed, never invents figures or picks allocations itself.

## Run the dev server

```bash
uvicorn app.main:app --reload --port 8000
```

API at `http://localhost:8000`, docs at `http://localhost:8000/docs`.

Frontend expects this exact host/port, if you change it update `NEXT_PUBLIC_API_BASE_URL` on that side.

## Run the tests

```bash
pytest
```

Covers the quant/backtest/rebalance/classification engines against hand-computed fixtures, plus API validation/error paths. Everything that would hit yfinance or OpenRouter is mocked, so it's offline and deterministic. `app/tests/conftest.py` has the cache-isolation fixture.

## API surface

- `GET /api/health` - liveness check
- `GET /api/tickers/search?q=...` - fuzzy ticker/company search, ranked, capped at 50
- `POST /api/portfolio/analyze` - main endpoint: holdings + weights + lookback window in, per-holding stats, portfolio risk/return, correlation matrix, efficient frontier (max-Sharpe + min-vol), 10yr Monte Carlo w/ 1yr 95% VaR, sector/market-cap breakdown out
- `POST /api/portfolio/backtest` - replays target weights over a historical stress period (`gfc_2008`, `covid_2020`, `rate_hikes_2022`, or custom dates) vs SPY, returns value paths + alpha/beta/max drawdown
- `POST /api/portfolio/rebalance` - given portfolio value and current holdings, returns whole-share buy/sell orders to hit target weights
- `POST /api/v1/simulate-shock` - shocks one holding's price and diffuses the impact across a correlation graph of the rest, BFS-style with per-hop decay
- `POST /api/ai/insights` - natural-language risk flags (LLM if configured, rule-based otherwise)
- `GET /api/ai/research?ticker=...` - short summary blending yfinance fundamentals with LLM narration
- `POST /api/ai/suggested-allocation` - deterministic reweighting toward a risk profile
- `POST /api/portfolio/export/csv` / `/export/pdf` - formats an analysis as a downloadable report

Bad input (weights that don't sum to 1, duplicate tickers, unresolvable tickers) returns 422 with a message, not a 500.

## Caching

`app/services/cache.py` is an in-process TTL cache in front of every yfinance call. No Redis, this is a single local process so it's not worth the infra. Price history: 1hr. Fundamentals: 1 day. Live quotes (rebalance calculator): 5 min.

## Project layout

```
app/
  main.py                 FastAPI app, CORS, router wiring
  models.py                Pydantic request/response models
  routers/
    portfolio.py            analyze / backtest / rebalance / export
    tickers.py               GET /api/tickers/search
    ai.py                    AI Assistant endpoints
    contagion.py             POST /api/v1/simulate-shock
  services/
    analysis.py               the quant engine
    backtest.py                stress-period backtesting
    rebalance.py                 trade-order calculator
    classification.py            sector / market-cap breakdown
    contagion.py                  correlation graph + shock diffusion
    ai_assistant.py            rule-based signals + optional LLM narration
    llm_client.py               OpenRouter client, never raises
    report.py                    CSV/PDF report generation
    cache.py                    shared in-process TTL cache
    ticker_index.py               in-memory fuzzy search over the ticker DB
  tests/
    test_*.py               fixture tests per service
    conftest.py               cache-isolation fixture
scripts/
  build_ticker_index.py    NASDAQ Trader ingestion -> data/tickers.db
data/
  tickers.db               generated, not checked in
.env.example                OpenRouter config template
```
