# PortfolioLens

Build a portfolio, see its risk. Annualized return/volatility/Sharpe, a correlation
heatmap, efficient frontier plot, 10-year Monte Carlo run with a 95% VaR, sector
breakdown, a backtest against SPY through a couple historical crashes, a rebalance
calculator, a contagion graph that simulates a price shock rippling across correlated
holdings, and an AI assistant for insights and per-ticker research. PDF/CSV export
too. All the numbers come from the FastAPI backend in `../backend`, this is just the
frontend.

## Requirements

- Node.js 20+
- Backend running locally (see `../backend/README.md`). Nothing here works without it.

## Setup

```bash
cd frontend
npm install
```

Build the backend's ticker index first (`python scripts/build_ticker_index.py` from
`backend/`) or search will just fall back to a small hardcoded list.

## Dev server

```bash
npm run dev
```

Open http://localhost:3000. Talks to `http://localhost:8000` by default. Different
backend URL? Set it:

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Other scripts

```bash
npm run build
npm run start
npm run lint
```

## Stack

Next.js 15 App Router, TypeScript, Tailwind v4. UI components are hand-rolled
shadcn-style stuff on top of Radix, not CLI-generated. Transitions are plain CSS
via tailwindcss-animate, no JS animation library. Recharts for the donut/frontier
scatter, lightweight-charts for the Monte Carlo fan and backtest line, React Flow
for the contagion graph. Zustand holds the builder state (holdings + lookback),
not persisted anywhere.

## Layout

```
src/
  app/
    page.tsx                 builder: ticker search + holdings + Analyze
    analyze/page.tsx          results dashboard
    layout.tsx, globals.css   fonts, theme, tokens
  components/
    ui/                       button, card, popover, etc
    TickerSearch.tsx           virtualized combobox
    StatCard.tsx, AllocationDonut.tsx, CorrelationHeatmap.tsx
    EfficientFrontierChart.tsx, MonteCarloChart.tsx, HoldingsTable.tsx
    AIAssistantSidebar.tsx     insights, research, suggested allocation
    BacktestChart.tsx          vs-SPY stress test
    RebalanceCalculator.tsx    buy/sell order calc
    ContagionGraph.tsx         shock simulation + correlation graph (React Flow)
    SectorBreakdown.tsx
  lib/
    api.ts       backend client
    store.ts      builder state
    chart-colors.ts
    format.ts, utils.ts
  hooks/
    use-debounce.ts, use-count-up.ts, use-chart-theme.ts, use-has-mounted.ts
```

## Notes

- Opens in light mode regardless of system preference; the toggle's in the
  header and remembers your choice via next-themes.
- Every async section has a skeleton and a real empty/error state. Turn off
  the backend and hit "Analyze portfolio" to see it.
- AI Assistant badges tell you whether an insight was LLM-generated or a
  rule-based fallback. See `../backend/README.md` for enabling the LLM path.
