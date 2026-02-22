#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Téléchargement EOD via Stooq → ibkr_us.sqlite + Parquet price_historical/

1. Récupère les symboles US depuis nasdaqtrader.com
2. Les ajoute dans ibkr_us.sqlite (table us_symbols_raw)
3. Télécharge l'historique daily depuis Stooq (CSV gratuit)
4. Sauvegarde en Parquet partitionné (price_historical/year=/month=/day=/SYMBOL.parquet)
   → même format que download_history.py, compatible avec le dashboard

Notes Stooq:
  - URL: https://stooq.com/q/d/l/?s=aapl.us&i=d
  - Renvoie CSV avec colonnes: Date, Open, High, Low, Close, Volume
  - Symboles US : aapl.us, msft.us, brk.b.us, etc.

Usage:
  python src/data/download_stooq.py
  python src/data/download_stooq.py --days 365 --workers 16 --skip-existing
  python src/data/download_stooq.py --db /chemin/ibkr_us.sqlite --out price_historical
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import sqlite3
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Defaults (overridable via env vars or CLI args)
# ---------------------------------------------------------------------------
MAX_WORKERS      = int(os.environ.get("STOOQ_MAX_WORKERS",      "12"))
HTTP_TIMEOUT     = float(os.environ.get("STOOQ_HTTP_TIMEOUT",   "20"))
RETRIES          = int(os.environ.get("STOOQ_RETRIES",          "3"))
RETRY_BACKOFF    = float(os.environ.get("STOOQ_RETRY_BACKOFF",  "1.5"))
DEFAULT_DAYS     = int(os.environ.get("STOOQ_LAST_N_DAYS",      "365"))
DATA_ROOT_DEFAULT = "price_historical"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL  = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; StooqEOD/1.0)"})


def _http_get(url: str) -> str:
    last_exc = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = SESSION.get(url, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            last_exc = exc
            time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"GET failed after {RETRIES} tries → {url}  ({last_exc})")


# ---------------------------------------------------------------------------
# Symbol list from NASDAQ Trader
# ---------------------------------------------------------------------------

def _parse_nasdaqtrader(txt: str) -> pd.DataFrame:
    """Parse the pipe-delimited NASDAQ Trader symbol files."""
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    lines = [l for l in lines if not l.startswith("File Creation Time")]
    if not lines:
        return pd.DataFrame(columns=["symbol", "name"])
    header = lines[0].split("|")
    rows   = [l.split("|") for l in lines[1:]]
    return pd.DataFrame(rows, columns=header)


def fetch_us_symbols() -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
      symbol, security_name, exchange_code, is_etf, is_test_issue
    """
    dfs = []

    # --- NASDAQ listed ---
    df_n = _parse_nasdaqtrader(_http_get(NASDAQ_LISTED_URL))
    df_n = df_n.rename(columns={"Symbol": "symbol", "Security Name": "security_name"})
    df_n["exchange_code"] = "Q"
    df_n["is_etf"]        = (
        df_n.get("ETF", pd.Series("N", index=df_n.index))
        .astype(str).str.upper().eq("Y").astype(int)
    )
    df_n["is_test_issue"] = (
        df_n.get("Test Issue", pd.Series("N", index=df_n.index))
        .astype(str).str.upper().eq("Y").astype(int)
    )
    dfs.append(df_n[["symbol", "security_name", "exchange_code", "is_etf", "is_test_issue"]])

    # --- Other listed (NYSE, AMEX, …) ---
    df_o = _parse_nasdaqtrader(_http_get(OTHER_LISTED_URL))
    df_o = df_o.rename(columns={"ACT Symbol": "symbol", "Security Name": "security_name"})
    df_o["exchange_code"] = df_o.get("Exchange", pd.Series("U", index=df_o.index)).astype(str)
    df_o["is_etf"]        = (
        df_o.get("ETF", pd.Series("N", index=df_o.index))
        .astype(str).str.upper().eq("Y").astype(int)
    )
    df_o["is_test_issue"] = (
        df_o.get("Test Issue", pd.Series("N", index=df_o.index))
        .astype(str).str.upper().eq("Y").astype(int)
    )
    dfs.append(df_o[["symbol", "security_name", "exchange_code", "is_etf", "is_test_issue"]])

    df = pd.concat(dfs, ignore_index=True)
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df = df[df["symbol"].str.len() > 0]
    df = df.drop_duplicates(subset=["symbol"])
    df = df.sort_values("symbol").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# SQLite helpers  (ibkr_us.sqlite, table us_symbols_raw)
# ---------------------------------------------------------------------------

def _find_db() -> str:
    env = os.environ.get("IBKR_SQLITE_PATH")
    if env and os.path.exists(env):
        return env
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(root, "ibkr_us.sqlite")
    if os.path.exists(candidate):
        return candidate
    cwd = os.path.join(os.getcwd(), "ibkr_us.sqlite")
    if os.path.exists(cwd):
        return cwd
    raise FileNotFoundError(
        "ibkr_us.sqlite introuvable. Définir IBKR_SQLITE_PATH ou lancer depuis la racine du projet."
    )


def upsert_symbols(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """
    Insert new symbols into us_symbols_raw.
    Existing symbols (by primary key) are left untouched (INSERT OR IGNORE).
    Returns the number of rows inserted.
    """
    rows = [
        (
            r.symbol,
            r.security_name,
            "nasdaqtrader",          # exchange_source
            r.exchange_code,
            int(r.is_etf),
            int(r.is_test_issue),
            None,                    # raw_json — not available here
        )
        for r in df.itertuples(index=False)
    ]
    cur = conn.executemany(
        """INSERT OR IGNORE INTO us_symbols_raw
           (symbol, security_name, exchange_source, exchange_code, is_etf, is_test_issue, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return cur.rowcount   # rows actually inserted


# ---------------------------------------------------------------------------
# Parquet helpers  (price_historical/)
# ---------------------------------------------------------------------------

def _parquet_path(root: str, day: datetime.date, symbol: str) -> str:
    return os.path.join(
        root,
        f"year={day.year}",
        f"month={day.month:02}",
        f"day={day.isoformat()}",
        f"{symbol}.parquet",
    )


def _save_parquet(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)


def _already_fetched(root: str) -> set[str]:
    """Return set of symbols that already have at least one Parquet file."""
    fetched: set[str] = set()
    if not os.path.isdir(root):
        return fetched
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith(".parquet"):
                fetched.add(fname[: -len(".parquet")])
    return fetched


# ---------------------------------------------------------------------------
# Stooq download
# ---------------------------------------------------------------------------

def _stooq_url(us_symbol: str) -> str:
    stooq_sym = us_symbol.strip().lower() + ".us"
    return f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d"


def download_stooq(us_symbol: str, days: int) -> Optional[pd.DataFrame]:
    """
    Download daily EOD data for *us_symbol* from Stooq.
    Returns a DataFrame with columns:
      symbol, date (Python date), open, high, low, close, volume
    or None if no data is available.
    """
    url = _stooq_url(us_symbol)
    last_exc = None

    for attempt in range(1, RETRIES + 1):
        try:
            r = SESSION.get(url, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            content = r.text.strip()

            if (
                not content
                or content.lower().startswith("nothing")
                or len(content.splitlines()) <= 1
            ):
                return None

            df = pd.read_csv(io.StringIO(content))
            if "Date" not in df.columns or "Close" not in df.columns:
                return None

            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")

            if days and days > 0:
                cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
                df = df[df["Date"] >= cutoff]

            if df.empty:
                return None

            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df.insert(0, "symbol", us_symbol.upper())
            # Convert date to Python date (matches download_history.py format)
            df["date"] = df["date"].dt.date

            keep = ["symbol", "date", "open", "high", "low", "close", "volume"]
            df = df[[c for c in keep if c in df.columns]]
            return df.reset_index(drop=True)

        except Exception as exc:
            last_exc = exc
            time.sleep(RETRY_BACKOFF * attempt)

    print(f"[WARN] {us_symbol}: {last_exc}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Per-symbol pipeline  (runs in thread-pool)
# ---------------------------------------------------------------------------

def _process_symbol(symbol: str, data_root: str, days: int) -> Tuple[str, int]:
    """Download Stooq data and save to Parquet. Returns (symbol, rows_saved)."""
    df = download_stooq(symbol, days)
    if df is None or df.empty:
        return symbol, 0

    saved = 0
    for day_val, group in df.groupby("date"):
        path = _parquet_path(data_root, day_val, symbol)
        if not os.path.exists(path):          # never overwrite existing files
            _save_parquet(group.reset_index(drop=True), path)
            saved += 1

    return symbol, saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Download Stooq EOD → ibkr_us.sqlite + Parquet price_historical/"
    )
    ap.add_argument("--db",      default=None,              help="Chemin ibkr_us.sqlite (auto-détecté)")
    ap.add_argument("--out",     default=DATA_ROOT_DEFAULT, help=f"Dossier Parquet (défaut: {DATA_ROOT_DEFAULT})")
    ap.add_argument("--days",    type=int, default=DEFAULT_DAYS, help="Jours d'historique (défaut: 365)")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS,  help=f"Threads parallèles (défaut: {MAX_WORKERS})")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Ne pas re-télécharger les symboles qui ont déjà des fichiers Parquet")
    ap.add_argument("--no-fetch-symbols", action="store_true",
                    help="Ne pas récupérer la liste NASDAQ Trader (utiliser uniquement us_symbols_raw)")
    args = ap.parse_args()

    db_path   = args.db or _find_db()
    data_root = args.out

    # Resolve data_root relative to project root if it's not absolute
    if not os.path.isabs(data_root):
        project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        data_root = os.path.join(project_root, data_root)

    print(f"[DB]      {db_path}")
    print(f"[PARQUET] {data_root}")
    print(f"[PÉRIODE] {args.days} jours")

    conn = sqlite3.connect(db_path, timeout=30)

    # ------------------------------------------------------------------
    # 1. Fetch + upsert symbols
    # ------------------------------------------------------------------
    if not args.no_fetch_symbols:
        print("\n[1/3] Récupération des symboles NASDAQ Trader…")
        try:
            df_syms = fetch_us_symbols()
            print(f"      {len(df_syms):,} symboles trouvés")
            # Filter out test issues
            df_syms = df_syms[df_syms["is_test_issue"] == 0]
            inserted = upsert_symbols(conn, df_syms)
            print(f"      {inserted:,} nouveaux symboles ajoutés dans us_symbols_raw")
        except Exception as exc:
            print(f"[WARN] Impossible de récupérer les symboles NASDAQ Trader: {exc}")
            print("       Les symboles existants dans us_symbols_raw seront utilisés.")
    else:
        print("\n[1/3] Récupération des symboles NASDAQ Trader ignorée (--no-fetch-symbols)")

    # ------------------------------------------------------------------
    # 2. Build the list of symbols to process
    # ------------------------------------------------------------------
    print("\n[2/3] Construction de la liste des symboles à télécharger…")
    cur = conn.execute("SELECT symbol FROM us_symbols_raw WHERE is_test_issue = 0 ORDER BY symbol")
    symbols = [r[0] for r in cur.fetchall()]
    print(f"      {len(symbols):,} symboles dans us_symbols_raw")

    if args.skip_existing:
        already = _already_fetched(data_root)
        before  = len(symbols)
        symbols = [s for s in symbols if s not in already]
        print(f"      {before - len(symbols):,} déjà présents → {len(symbols):,} restants")

    conn.close()   # each thread opens its own connection for writing

    if not symbols:
        print("[DONE] Rien à télécharger.")
        return

    # ------------------------------------------------------------------
    # 3. Parallel download → Parquet
    # ------------------------------------------------------------------
    print(f"\n[3/3] Téléchargement Stooq ({args.workers} threads)…")
    t0 = time.time()
    total_rows = 0
    done = 0
    errors = 0
    empty  = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(_process_symbol, sym, data_root, args.days): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            sym, n = fut.result()
            done  += 1
            if n > 0:
                total_rows += n
            elif n == 0:
                empty += 1

            if done % 500 == 0 or done == len(symbols):
                elapsed = time.time() - t0
                rate    = done / elapsed if elapsed > 0 else 0
                print(
                    f"  [{done:,}/{len(symbols):,}]  "
                    f"fichiers Parquet sauvegardés: {total_rows:,}  |  "
                    f"vides/introuvables: {empty:,}  |  "
                    f"{elapsed:.0f}s ({rate:.0f} sym/s)"
                )

    elapsed = time.time() - t0
    print(f"\n[DONE] Symboles traités: {len(symbols):,}")
    print(f"       Fichiers Parquet créés: {total_rows:,}")
    print(f"       Symboles sans données: {empty:,}")
    print(f"       Durée: {elapsed:.1f}s")
    print(f"       Sortie: {data_root}/")


if __name__ == "__main__":
    main()
