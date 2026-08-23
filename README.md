# PortfolioLens

Build a portfolio, see its risk. You enter tickers and weights; PortfolioLens pulls
historical prices and computes annualized return/volatility/Sharpe, a correlation
heatmap, the efficient frontier, a 10-year Monte Carlo simulation, sector/market-cap
exposure, a backtest against SPY through a few historical stress periods, a rebalance
calculator, and a contagion/shock simulation across correlated holdings. An optional
LLM narrates the results in plain English; without it, the same signals render as
templated text.

Two pieces: a FastAPI backend that does all the math, and a Next.js frontend that
renders it. Nothing is persisted server-side beyond an in-process cache.

## Features

- Portfolio analysis: per-holding and portfolio-level return, volatility, Sharpe
  ratio, correlation matrix, 1yr 95% VaR
- Efficient frontier (max-Sharpe and min-volatility portfolios, long-only)
- 10-year Monte Carlo simulation with percentile fan bands
- Historical stress-period backtests vs. SPY (2008 GFC, 2020 COVID crash, 2022 rate
  hikes, or a custom date range), with alpha/beta/max drawdown
- Rebalance calculator: target weights + total value → whole-share buy/sell orders
- Sector and market-cap breakdown with concentration warnings
- Contagion simulation: propagate a price shock through a correlation graph of your
  holdings
- AI assistant: risk signals, per-ticker research, and suggested allocations by risk
  profile (LLM-narrated if configured, rule-based otherwise)
- Fuzzy ticker/company search
- CSV/PDF report export

## Tech Stack

**Backend:** FastAPI, pandas/numpy/scipy (optimization, Monte Carlo), yfinance
(price data), rapidfuzz (ticker search), networkx (contagion graph), reportlab (PDF
export), OpenRouter (optional LLM narration).

**Frontend:** Next.js 16 (App Router), TypeScript, Tailwind v4, Zustand, Recharts +
lightweight-charts, Radix primitives.

## Running Locally

Requires Python 3.11+ and Node 20+.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python scripts/build_ticker_index.py   # optional but recommended, see backend/README.md
uvicorn app.main:app --reload --port 8000
```

```bash
# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend expects the API at
`http://localhost:8000` by default (`NEXT_PUBLIC_API_BASE_URL` to change it). For
LLM-narrated insights instead of the rule-based fallback, set `OPENROUTER_API_KEY`
in `backend/.env` (see `backend/.env.example`).

See `backend/README.md` and `frontend/README.md` for more detail on each half,
including the full API surface and project layout.

## Deploying Publicly

Both halves are stateless and hold no accounts, so there's no auth layer -- the security
model is entirely "don't trust anything from the browser" and "don't let the API be abused."
Before pointing a public URL at this:

- Set `ALLOWED_ORIGINS` on the backend to your actual frontend domain (not the localhost
  default) and `ENVIRONMENT=production` to hide `/docs`/`/redoc`/`/openapi.json`.
- Only set `TRUST_PROXY_HEADERS=true` if you're actually behind a reverse proxy/CDN that
  sets `X-Forwarded-For` -- otherwise every visitor's rate limit collapses onto the
  proxy's IP, or a client can spoof the header to dodge limits entirely.
- Run production builds (`next build` + `next start`, `uvicorn` without `--reload`), not
  dev servers.
- Rate limits and the `/analyze` concurrency cap are in-process (no Redis); if you ever
  run multiple backend workers/instances, limits apply per-process, not globally.
- Set spending/usage alerts on whatever hosts this -- the app has its own rate limits and
  a body-size cap, but a determined enough attacker can still generate load; the hosting
  platform's own limits are the backstop.

## How It Works

- **Historical returns**: daily adjusted closes come from yfinance, aligned across
  holdings on shared trading dates. Returns are simple (not log), so a portfolio's
  return is a weighted sum of its holdings' returns.
- **Risk**: volatility is the annualized standard deviation of daily returns
  (252 trading days/year, `sqrt(time)` scaling). Sharpe ratio nets out a fixed
  risk-free rate. Portfolio variance is `wᵀ Σ w` over the covariance matrix of
  holding returns.
- **Optimization**: the efficient frontier is built by minimizing portfolio
  volatility at a sweep of target returns (SciPy SLSQP), long-only and fully
  invested. Max-Sharpe and min-volatility portfolios are solved the same way.
- **Monte Carlo**: simulates 10,000+ correlated GBM price paths from the same
  historical mean/covariance, using a Cholesky decomposition to preserve the
  correlation structure between holdings. Reports percentile bands and a 1-year 95%
  VaR.

## Known Limitations

- Annualization uses a fixed 252-trading-day convention; actual trading calendars
  vary slightly year to year.
- Historical return, volatility, and correlation figures are backward-looking and
  are not a forecast — Monte Carlo and optimization outputs inherit that same
  historical bias.
- Optimization and Monte Carlo results depend entirely on the supplied constraints
  and historical inputs; short selling is not modeled (weights are long-only).
- Rebalancing and export math don't account for transaction costs, taxes, or
  fractional shares.
- Recently listed securities or illiquid tickers with under ~30 trading days of
  history are skipped rather than analyzed, and the rest of the portfolio is
  reweighted to fill the gap.
- The AI assistant only narrates numbers already computed elsewhere; without an
  `OPENROUTER_API_KEY`, insights fall back to deterministic templated text.
- Portfolio holdings are processed in memory for the current request only -- never
  written to disk or a database. If you request AI insights or research, your holdings
  and computed stats are sent to the configured LLM provider to generate that response.
- Rate limiting and the Monte Carlo concurrency cap are in-process, not distributed --
  see "Deploying Publicly" above if running more than one backend process/instance.
