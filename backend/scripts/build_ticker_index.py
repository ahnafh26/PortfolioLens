"""Builds the local ticker search index from NASDAQ Trader's public symbol directory.

Downloads nasdaqlisted.txt + otherlisted.txt, filters out test issues/warrants/rights/units,
writes to data/tickers.db. Run from backend/: python scripts/build_ticker_index.py
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from urllib.request import urlopen

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tickers.db"

# filter out rights/warrants/units/preferred, just noise for search
NOISE_PATTERN = re.compile(r"\b(warrant|warrants|right|rights|unit|units|preferred)\b", re.IGNORECASE)

EXCHANGE_NAMES = {
    "A": "NYSE American",
    "N": "NYSE",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}


def _download(url: str) -> str:
    print(f"Downloading {url} ...")
    with urlopen(url, timeout=30) as response:  # noqa: S310 (fixed, hardcoded https URL)
        return response.read().decode("utf-8", errors="replace")


def _parse_pipe_delimited(raw: str) -> list[dict[str, str]]:
    lines = raw.splitlines()
    if not lines:
        return []
    header = lines[0].split("|")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line or line.startswith("File Creation Time"):
            continue  # footer line
        fields = line.split("|")
        if len(fields) != len(header):
            continue  # malformed row
        rows.append(dict(zip(header, fields)))
    return rows


def _is_noise(name: str, test_issue_flag: str) -> bool:
    return test_issue_flag.strip().upper() == "Y" or bool(NOISE_PATTERN.search(name))


def parse_nasdaq_listed(raw: str) -> list[tuple[str, str, str]]:
    records = []
    for row in _parse_pipe_delimited(raw):
        symbol = row.get("Symbol", "").strip()
        name = row.get("Security Name", "").strip()
        if not symbol or not name or _is_noise(name, row.get("Test Issue", "N")):
            continue
        records.append((symbol, name, "NASDAQ"))
    return records


def parse_other_listed(raw: str) -> list[tuple[str, str, str]]:
    records = []
    for row in _parse_pipe_delimited(raw):
        symbol = row.get("ACT Symbol", "").strip()
        name = row.get("Security Name", "").strip()
        if not symbol or not name or _is_noise(name, row.get("Test Issue", "N")):
            continue
        exchange = EXCHANGE_NAMES.get(row.get("Exchange", "").strip(), "Other")
        records.append((symbol, name, exchange))
    return records


def build_database(records: list[tuple[str, str, str]], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE tickers (symbol TEXT PRIMARY KEY, name TEXT NOT NULL, exchange TEXT NOT NULL)"
        )
        # a symbol can appear in both files; nasdaqlisted wins since it's processed first
        conn.executemany(
            "INSERT OR IGNORE INTO tickers (symbol, name, exchange) VALUES (?, ?, ?)", records
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    try:
        nasdaq_raw = _download(NASDAQ_LISTED_URL)
        other_raw = _download(OTHER_LISTED_URL)
    except Exception as exc:
        print(f"ERROR: failed to download symbol directory files: {exc}", file=sys.stderr)
        print("The API will still run using a small built-in fallback ticker list.", file=sys.stderr)
        return 1

    records = parse_nasdaq_listed(nasdaq_raw) + parse_other_listed(other_raw)
    print(f"Parsed {len(records)} tradable listings (noise filtered out).")

    build_database(records, DB_PATH)
    print(f"Wrote ticker index to {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
