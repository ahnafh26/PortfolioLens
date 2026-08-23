"""In-memory fuzzy search over the ticker universe. Loads data/tickers.db at startup, searches in memory (rapidfuzz)."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tickers.db"

# used if the index hasn't been built yet, so the app still boots
_FALLBACK_SEED: list[tuple[str, str, str]] = [
    ("AAPL", "Apple Inc.", "NASDAQ"), ("MSFT", "Microsoft Corporation", "NASDAQ"),
    ("GOOGL", "Alphabet Inc.", "NASDAQ"), ("GOOG", "Alphabet Inc.", "NASDAQ"),
    ("AMZN", "Amazon.com, Inc.", "NASDAQ"), ("NVDA", "NVIDIA Corporation", "NASDAQ"),
    ("META", "Meta Platforms, Inc.", "NASDAQ"), ("TSLA", "Tesla, Inc.", "NASDAQ"),
    ("BRK.B", "Berkshire Hathaway Inc.", "NYSE"), ("JPM", "JPMorgan Chase & Co.", "NYSE"),
    ("V", "Visa Inc.", "NYSE"), ("JNJ", "Johnson & Johnson", "NYSE"),
    ("WMT", "Walmart Inc.", "NYSE"), ("PG", "Procter & Gamble Company", "NYSE"),
    ("MA", "Mastercard Incorporated", "NYSE"), ("HD", "Home Depot, Inc.", "NYSE"),
    ("DIS", "Walt Disney Company", "NYSE"), ("NFLX", "Netflix, Inc.", "NASDAQ"),
    ("KO", "Coca-Cola Company", "NYSE"), ("PEP", "PepsiCo, Inc.", "NASDAQ"),
    ("SPY", "SPDR S&P 500 ETF Trust", "ARCA"), ("QQQ", "Invesco QQQ Trust", "NASDAQ"),
    ("VOO", "Vanguard S&P 500 ETF", "ARCA"), ("VTI", "Vanguard Total Stock Market ETF", "ARCA"),
    ("AMD", "Advanced Micro Devices, Inc.", "NASDAQ"), ("INTC", "Intel Corporation", "NASDAQ"),
    ("BA", "Boeing Company", "NYSE"), ("XOM", "Exxon Mobil Corporation", "NYSE"),
    ("BAC", "Bank of America Corporation", "NYSE"), ("PFE", "Pfizer Inc.", "NYSE"),
]


@dataclass(frozen=True)
class TickerRecord:
    symbol: str
    name: str
    exchange: str


class TickerIndex:
    def __init__(self, records: list[TickerRecord]):
        self.records = records
        self._by_symbol = {r.symbol: r for r in records}
        self._symbols = [r.symbol for r in records]
        self._names = [r.name for r in records]

    def __len__(self) -> int:
        return len(self.records)

    def search(self, query: str, limit: int = 50) -> list[TickerRecord]:
        """Exact/prefix symbol hits beat fuzzy matches on symbol or name."""
        query = query.strip()
        if not query:
            return []
        query_upper = query.upper()

        scored: dict[str, float] = {}

        # exact/prefix matches score above anything fuzzy can produce (fuzzy tops out at 100)
        for record in self.records:
            if record.symbol == query_upper:
                scored[record.symbol] = 1000.0
            elif record.symbol.startswith(query_upper):
                scored[record.symbol] = 900.0 - len(record.symbol)

        # plain ratio for symbols, not WRatio: WRatio's partial-match scoring ranks "AP"
        # above "AAPL" for a query like "APPL" since AP is a substring, which is wrong here
        for symbol, score, _ in process.extract(query_upper, self._symbols, scorer=fuzz.ratio, limit=limit * 2):
            scored[symbol] = max(scored.get(symbol, 0.0), score)

        # names are long, people type fragments ("apple"), WRatio's partial matching fits here
        for name, score, idx in process.extract(query, self._names, scorer=fuzz.WRatio, limit=limit * 2):
            record = self.records[idx]
            # discount name matches a bit vs symbol matches at the same score
            scored[record.symbol] = max(scored.get(record.symbol, 0.0), score * 0.95)

        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [self._by_symbol[symbol] for symbol, _ in ranked]


def load_ticker_index(db_path: Path = DB_PATH) -> TickerIndex:
    if not db_path.exists():
        logger.warning(
            "Ticker index not found at %s, using built-in seed list. Run scripts/build_ticker_index.py.",
            db_path,
        )
        return TickerIndex([TickerRecord(*row) for row in _FALLBACK_SEED])

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT symbol, name, exchange FROM tickers ORDER BY symbol").fetchall()
    finally:
        conn.close()

    records = [TickerRecord(symbol=r[0], name=r[1], exchange=r[2]) for r in rows]
    logger.info("Loaded %d tickers from %s", len(records), db_path)
    return TickerIndex(records)
