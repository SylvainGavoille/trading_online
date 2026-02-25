#!/usr/bin/env python3
"""
Build a local SQLite database of US listed symbols (free source) and verify tradability in IBKR.

Data sources (free):
- NASDAQ Trader symbol directory:
  * nasdaqlisted.txt
  * otherlisted.txt

IBKR verification:
- Uses TWS / IB Gateway via ib_insync and reqContractDetails on Stock(symbol, "SMART", "USD")

Usage:
  python build_ibkr_sqlite.py --db ibkr_us.sqlite --ib-host 127.0.0.1 --ib-port 7497 --client-id 11
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable, Optional, List, Dict, Any, Tuple

import requests
from tqdm import tqdm
from ib_insync import IB, Stock


# ----------------------------
# Free US sources
# ----------------------------
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"


# ----------------------------
# SQLite schema
# ----------------------------
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT DEFAULT (datetime('now')),
  source_nasdaq_url TEXT,
  source_other_url TEXT,
  ibkr_host TEXT,
  ibkr_port INTEGER,
  ibkr_client_id INTEGER,
  notes TEXT
);

-- Raw symbols as published by NASDAQ Trader (US universe)
CREATE TABLE IF NOT EXISTS us_symbols_raw (
  symbol TEXT NOT NULL,
  security_name TEXT,
  exchange_source TEXT NOT NULL,      -- NASDAQ_LISTED / OTHER_LISTED
  exchange_code TEXT,                -- (for otherlisted) N/A for nasdaqlisted
  is_etf INTEGER,                    -- 0/1/NULL
  is_test_issue INTEGER,             -- 0/1/NULL
  raw_json TEXT,
  PRIMARY KEY(symbol, exchange_source)
);

-- IBKR verification + conId mapping (keyed by symbol; if you want multiple listings per symbol, use (symbol, conId))
CREATE TABLE IF NOT EXISTS ibkr_verification (
  symbol TEXT PRIMARY KEY,
  verified INTEGER NOT NULL,         -- 0/1
  conId INTEGER,
  exchange TEXT,
  primaryExchange TEXT,
  currency TEXT,
  secType TEXT,
  localSymbol TEXT,
  longName TEXT,
  industry TEXT,
  category TEXT,
  subcategory TEXT,
  timeZoneId TEXT,
  updated_at TEXT DEFAULT (datetime('now')),
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_symbol ON us_symbols_raw(symbol);
CREATE INDEX IF NOT EXISTS idx_ibkr_verified ON ibkr_verification(verified);
"""


# ----------------------------
# Models
# ----------------------------
@dataclass(frozen=True)
class RawSymbol:
    symbol: str
    security_name: str
    exchange_source: str
    exchange_code: Optional[str]
    is_etf: Optional[int]
    is_test_issue: Optional[int]
    raw_json: str


# ----------------------------
# Download & parsing helpers
# ----------------------------
def download_text(url: str, timeout_s: int = 30) -> str:
    r = requests.get(url, timeout=timeout_s)
    r.raise_for_status()
    return r.text


def strip_non_data_lines(text: str) -> List[str]:
    """
    NASDAQ Trader files include a footer like 'File Creation Time: ...' and sometimes blank lines.
    We keep only lines that contain the delimiter '|'.
    """
    lines = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        lines.append(line)
    return lines


def parse_nasdaqlisted(text: str) -> Iterable[RawSymbol]:
    """
    Expected columns (may evolve):
      Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares|...
    """
    lines = strip_non_data_lines(text)
    reader = csv.DictReader(lines, delimiter="|")
    for row in reader:
        sym = (row.get("Symbol") or "").strip()
        name = (row.get("Security Name") or "").strip()
        test_issue = (row.get("Test Issue") or "").strip().upper()  # Y/N
        etf = (row.get("ETF") or "").strip().upper()  # Y/N
        if not sym:
            continue
        yield RawSymbol(
            symbol=sym,
            security_name=name,
            exchange_source="NASDAQ_LISTED",
            exchange_code=None,
            is_etf=1 if etf == "Y" else 0 if etf == "N" else None,
            is_test_issue=1 if test_issue == "Y" else 0 if test_issue == "N" else None,
            raw_json=str(row),
        )


def parse_otherlisted(text: str) -> Iterable[RawSymbol]:
    """
    Expected columns (may evolve):
      ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol|...
    """
    lines = strip_non_data_lines(text)
    reader = csv.DictReader(lines, delimiter="|")
    for row in reader:
        sym = (row.get("ACT Symbol") or "").strip()
        name = (row.get("Security Name") or "").strip()
        exch = (row.get("Exchange") or "").strip()  # A/N/P/Q/V/Z etc.
        test_issue = (row.get("Test Issue") or "").strip().upper()  # Y/N
        etf = (row.get("ETF") or "").strip().upper()  # Y/N
        if not sym:
            continue
        yield RawSymbol(
            symbol=sym,
            security_name=name,
            exchange_source="OTHER_LISTED",
            exchange_code=exch or None,
            is_etf=1 if etf == "Y" else 0 if etf == "N" else None,
            is_test_issue=1 if test_issue == "Y" else 0 if test_issue == "N" else None,
            raw_json=str(row),
        )


# ----------------------------
# SQLite helpers
# ----------------------------
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    return conn


def insert_run(
    conn: sqlite3.Connection, ib_host: str, ib_port: int, client_id: int, notes: str
) -> None:
    conn.execute(
        """
        INSERT INTO runs (source_nasdaq_url, source_other_url, ibkr_host, ibkr_port, ibkr_client_id, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (NASDAQ_LISTED_URL, OTHER_LISTED_URL, ib_host, ib_port, client_id, notes),
    )
    conn.commit()


def upsert_raw_symbols(conn: sqlite3.Connection, symbols: Iterable[RawSymbol]) -> int:
    rows = list(symbols)
    conn.executemany(
        """
        INSERT OR REPLACE INTO us_symbols_raw
          (symbol, security_name, exchange_source, exchange_code, is_etf, is_test_issue, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s.symbol,
                s.security_name,
                s.exchange_source,
                s.exchange_code,
                s.is_etf,
                s.is_test_issue,
                s.raw_json,
            )
            for s in rows
        ],
    )
    conn.commit()
    return len(rows)


def get_unique_symbols_to_verify(
    conn: sqlite3.Connection, include_etf: bool, exclude_test: bool
) -> List[str]:
    where = []
    if exclude_test:
        where.append("COALESCE(is_test_issue, 0) = 0")
    if not include_etf:
        # We exclude ETFs where explicitly flagged as ETF=1; keep NULL (unknown) to avoid losing coverage.
        where.append("COALESCE(is_etf, 0) = 0")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT symbol FROM us_symbols_raw {where_sql}")
    return [r[0] for r in cur.fetchall()]


def get_already_processed(conn: sqlite3.Connection) -> set[str]:
    """Return symbols in ibkr_verification that don't need retrying.

    Excludes symbols that failed due to connectivity errors so they get retried.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT symbol FROM ibkr_verification
        WHERE verified = 1
           OR (verified = 0 AND (error IS NULL
               OR (error NOT LIKE '%ConnectionError%'
                   AND error NOT LIKE '%TimeoutError%'
                   AND error NOT LIKE '%WinError%')))
    """
    )
    return {r[0] for r in cur.fetchall()}


def upsert_ibkr_result(
    conn: sqlite3.Connection,
    symbol: str,
    verified: int,
    details: Dict[str, Any],
    error: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO ibkr_verification
          (symbol, verified, conId, exchange, primaryExchange, currency, secType, localSymbol,
           longName, industry, category, subcategory, timeZoneId, updated_at, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """,
        (
            symbol,
            verified,
            details.get("conId"),
            details.get("exchange"),
            details.get("primaryExchange"),
            details.get("currency"),
            details.get("secType"),
            details.get("localSymbol"),
            details.get("longName"),
            details.get("industry"),
            details.get("category"),
            details.get("subcategory"),
            details.get("timeZoneId"),
            error,
        ),
    )


def stats(conn: sqlite3.Connection) -> Tuple[int, int, int]:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM us_symbols_raw")
    raw = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ibkr_verification WHERE verified = 1")
    ok = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ibkr_verification WHERE verified = 0")
    ko = cur.fetchone()[0]
    return raw, ok, ko


# ----------------------------
# IBKR verification
# ----------------------------
def verify_symbols_in_ibkr(
    conn: sqlite3.Connection,
    symbols: List[str],
    ib_host: str,
    ib_port: int,
    client_id: int,
    throttle_s: float,
    commit_every: int,
    resume: bool,
) -> None:
    ib = IB()
    ib.connect(ib_host, ib_port, clientId=client_id)

    done = get_already_processed(conn) if resume else set()
    todo = [s for s in symbols if s not in done]

    print(
        f"[INFO] New symbols to verify: {len(todo)} (skipping {len(done)} already processed)"
    )
    pbar = tqdm(todo, desc="IBKR verify", unit="sym")
    n_since_commit = 0

    for sym in pbar:
        try:
            # SMART routing, USD. This is the usual way to resolve US stocks.
            contract = Stock(sym, "SMART", "USD")
            cds = ib.reqContractDetails(contract)
            time.sleep(throttle_s)

            if not cds:
                upsert_ibkr_result(conn, sym, 0, {}, "No contractDetails returned")
            else:
                cd0 = cds[0]
                c = cd0.contract
                details = {
                    "conId": c.conId,
                    "exchange": c.exchange,
                    "primaryExchange": c.primaryExchange,
                    "currency": c.currency,
                    "secType": c.secType,
                    "localSymbol": c.localSymbol,
                    "longName": getattr(cd0, "longName", None),
                    "industry": getattr(cd0, "industry", None),
                    "category": getattr(cd0, "category", None),
                    "subcategory": getattr(cd0, "subcategory", None),
                    "timeZoneId": getattr(cd0, "timeZoneId", None),
                }
                upsert_ibkr_result(conn, sym, 1, details, None)

        except Exception as e:
            upsert_ibkr_result(conn, sym, 0, {}, repr(e))

        n_since_commit += 1
        if n_since_commit >= commit_every:
            conn.commit()
            n_since_commit = 0

    conn.commit()
    ib.disconnect()


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="ibkr_us.sqlite", help="SQLite database file path")
    ap.add_argument("--ib-host", default="127.0.0.1", help="IBKR TWS/IB Gateway host")
    ap.add_argument(
        "--ib-port",
        type=int,
        default=7497,
        help="IBKR port (7497 paper, 7496 live typical)",
    )
    ap.add_argument("--client-id", type=int, default=11, help="IBKR clientId")

    ap.add_argument(
        "--include-etf",
        action="store_true",
        help="Include ETFs in the verification universe",
    )
    ap.add_argument(
        "--include-test-issues", action="store_true", help="Include test issues"
    )
    ap.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume: re-verify all symbols including already processed ones",
    )

    ap.add_argument(
        "--throttle",
        type=float,
        default=0.02,
        help="Sleep seconds between IBKR requests",
    )
    ap.add_argument(
        "--commit-every", type=int, default=200, help="Commit every N symbols"
    )
    ap.add_argument(
        "--skip-ibkr",
        action="store_true",
        help="Only build raw tables, skip IBKR verification",
    )

    args = ap.parse_args()

    conn = init_db(args.db)
    insert_run(
        conn,
        ib_host=args.ib_host,
        ib_port=args.ib_port,
        client_id=args.client_id,
        notes="Build US universe from NASDAQ Trader; verify with IBKR reqContractDetails (ib_insync).",
    )

    # 1) Download + parse
    nasdaq_txt = download_text(NASDAQ_LISTED_URL)
    other_txt = download_text(OTHER_LISTED_URL)

    n1 = upsert_raw_symbols(conn, parse_nasdaqlisted(nasdaq_txt))
    n2 = upsert_raw_symbols(conn, parse_otherlisted(other_txt))

    raw_count, ok_count, ko_count = stats(conn)
    print(
        f"[OK] Raw inserted: NASDAQ_LISTED={n1}, OTHER_LISTED={n2}. Total raw rows={raw_count}."
    )
    print(
        f"[INFO] Current IBKR verification counts: verified={ok_count}, not_verified={ko_count}"
    )

    if args.skip_ibkr:
        print("[DONE] skip-ibkr enabled. Database filled with raw US symbols only.")
        conn.close()
        return

    # 2) Build verification universe
    exclude_test = not args.include_test_issues
    include_etf = args.include_etf

    universe = get_unique_symbols_to_verify(
        conn, include_etf=include_etf, exclude_test=exclude_test
    )
    already = get_already_processed(conn)
    new_count = len([s for s in universe if s not in already])
    print(
        f"[INFO] Verification universe size: {len(universe)} symbols ({new_count} new, {len(already)} already processed)"
    )

    verify_symbols_in_ibkr(
        conn=conn,
        symbols=universe,
        ib_host=args.ib_host,
        ib_port=args.ib_port,
        client_id=args.client_id,
        throttle_s=args.throttle,
        commit_every=args.commit_every,
        resume=not args.no_resume,
    )

    raw_count, ok_count, ko_count = stats(conn)
    print(
        f"[DONE] Final counts: raw_rows={raw_count}, ibkr_verified={ok_count}, ibkr_not_verified={ko_count}"
    )
    print(f"[DONE] SQLite DB: {args.db}")

    conn.close()


if __name__ == "__main__":
    main()
