#!/usr/bin/env python3
"""
Historique EOD sur la derniere annee (365 jours) pour tous les symboles
presents dans ibkr_us.sqlite, stocke en Parquet partitionne par date.

Source des prix : Yahoo Finance (yfinance) - telechargement par batch
Granularite     : EOD (1 jour)
Symboles        : ibkr_verification (verified=1) ou us_symbols_raw (--all)

Structure de sortie :
  <DATA_ROOT>/
    year=2025/month=01/day=2025-01-02/<SYMBOL>.parquet
    ...

Usage :
  python download_history.py
  python download_history.py --db /chemin/ibkr_us.sqlite --days 365 --batch-size 200
  python download_history.py --all --skip-existing
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

DATA_ROOT = "price_historical"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    env = os.environ.get("IBKR_SQLITE_PATH")
    if env and os.path.exists(env):
        return env
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(this_dir, "..", ".."))
    candidate = os.path.join(project_root, "ibkr_us.sqlite")
    if os.path.exists(candidate):
        return candidate
    cwd = os.path.join(os.getcwd(), "ibkr_us.sqlite")
    if os.path.exists(cwd):
        return cwd
    raise FileNotFoundError(
        "ibkr_us.sqlite introuvable. Definir IBKR_SQLITE_PATH ou lancer depuis la racine du projet."
    )


def get_symbols(db_path: str, all_symbols: bool) -> list[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if all_symbols:
        cur.execute("SELECT DISTINCT symbol FROM us_symbols_raw ORDER BY symbol")
    else:
        cur.execute(
            "SELECT symbol FROM ibkr_verification WHERE verified = 1 ORDER BY symbol"
        )
    symbols = [r[0] for r in cur.fetchall()]
    conn.close()
    return symbols


# ---------------------------------------------------------------------------
# Parquet helpers
# ---------------------------------------------------------------------------

def parquet_path(root: str, day: date, symbol: str) -> str:
    return os.path.join(
        root,
        f"year={day.year}",
        f"month={day.month:02}",
        f"day={day.isoformat()}",
        f"{symbol}.parquet",
    )


def save_parquet(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# Telechargement par batch
# ---------------------------------------------------------------------------

def fetch_batch(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """
    Telecharge un batch de symboles en une seule requete yfinance.
    Retourne un dict {symbol: DataFrame} avec colonnes date/open/high/low/close/volume.
    """
    results = {}

    # Bounded retry with exponential backoff: only retry on a thrown exception
    # (transient network/rate-limit failure). A successful call that returns no
    # data is genuine "no data" and is not retried.
    max_attempts = 3
    df = None
    for attempt in range(1, max_attempts + 1):
        try:
            df = yf.download(
                symbols,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
            break
        except Exception as exc:
            if attempt == max_attempts:
                print(
                    f"[ERR batch] failed after {max_attempts} attempts ({exc}); "
                    f"symbols={symbols[:5]}{'...' if len(symbols) > 5 else ''}"
                )
                return results
            backoff = 2 ** attempt  # 2s, 4s, 8s
            print(f"[WARN batch] attempt {attempt}/{max_attempts} failed ({exc}); retrying in {backoff}s")
            time.sleep(backoff)

    if df is None or df.empty:
        return results

    # Un seul symbole — yfinance peut retourner un MultiIndex selon la version
    if len(symbols) == 1:
        sym = symbols[0]
        try:
            if isinstance(df.columns, pd.MultiIndex):
                # Nouvelle version yfinance : MultiIndex même pour un seul symbole
                if sym in df.columns.get_level_values(0):
                    d = df[sym].copy().reset_index()
                else:
                    return results
            else:
                d = df.reset_index()
            d.columns = [c.lower() for c in d.columns]
            d["date"] = pd.to_datetime(d["date"]).dt.date
            d["symbol"] = sym
            d = d.dropna(subset=["close"])
            keep = [c for c in ["symbol", "date", "open", "high", "low", "close", "volume"] if c in d.columns]
            if not d.empty:
                results[sym] = d[keep]
        except Exception as exc:
            print(f"[ERR] {sym}: {exc}")
        return results

    # Plusieurs symboles -> MultiIndex (ticker, field)
    for sym in symbols:
        try:
            if sym not in df.columns.get_level_values(0):
                continue
            d = df[sym].copy().reset_index()
            d.columns = [c.lower() for c in d.columns]
            d["date"] = pd.to_datetime(d["date"]).dt.date
            d["symbol"] = sym
            d = d.dropna(subset=["close"])
            keep = [c for c in ["symbol", "date", "open", "high", "low", "close", "volume"] if c in d.columns]
            if not d.empty:
                results[sym] = d[keep]
        except Exception as exc:
            print(f"[ERR] {sym}: {exc}")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Telecharge l'historique EOD par batch pour les symboles de ibkr_us.sqlite"
    )
    ap.add_argument("--db", default=None, help="Chemin ibkr_us.sqlite (auto-detecte par defaut)")
    ap.add_argument("--out", default=DATA_ROOT, help=f"Dossier de sortie Parquet (defaut: {DATA_ROOT})")
    ap.add_argument("--days", type=int, default=365, help="Nombre de jours en arriere (defaut: 365)")
    ap.add_argument("--batch-size", type=int, default=100, help="Symboles par requete yfinance (defaut: 100)")
    ap.add_argument("--pause", type=float, default=1.0, help="Pause en secondes entre batches (defaut: 1.0)")
    ap.add_argument("--all", dest="all_symbols", action="store_true",
                    help="Inclure les symboles non verifies IBKR (us_symbols_raw)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Ignorer les symboles deja presents dans le dossier de sortie")
    args = ap.parse_args()

    db_path = args.db or _get_db_path()
    end_date   = date.today()
    start_date = end_date - timedelta(days=args.days)

    print(f"[DB]      {db_path}")
    print(f"[SORTIE]  {args.out}")
    print(f"[PERIODE] {start_date} -> {end_date} ({args.days} jours)")

    symbols = get_symbols(db_path, args.all_symbols)
    print(f"[SYMBOLES] {len(symbols)} trouves ({'tous' if args.all_symbols else 'verifies IBKR'})")

    if not symbols:
        print("[DONE] Rien a telecharger.")
        return

    # Decoupage en batches
    batches = [symbols[i:i + args.batch_size] for i in range(0, len(symbols), args.batch_size)]
    total = len(symbols)
    n_batches = len(batches)
    print(f"[BATCH]   {n_batches} batches de {args.batch_size} symboles max")

    ok = err = empty = 0
    existing_files = 0
    processed = 0

    for b_idx, batch in enumerate(batches, 1):
        results = fetch_batch(batch, start_date, end_date)

        for sym in batch:
            processed += 1
            df = results.get(sym)
            if df is None or df.empty:
                empty += 1
            else:
                try:
                    wrote_any = False
                    for day, group in df.groupby("date"):
                        path = parquet_path(args.out, day, sym)
                        if args.skip_existing and os.path.exists(path):
                            existing_files += 1
                            continue
                        save_parquet(group.reset_index(drop=True), path)
                        wrote_any = True
                    if wrote_any:
                        ok += 1
                    else:
                        empty += 1
                except Exception as exc:
                    print(f"[ERR save] {sym}: {exc}")
                    err += 1

        missing = [s for s in batch if s not in results]
        if missing:
            err += len(missing)

        print(f"[{processed}/{total}] batch {b_idx}/{n_batches} | ok={ok}  vide={empty}  err={err}")
        sys.stdout.flush()

        if b_idx < n_batches:
            time.sleep(args.pause)

    print(f"\n[DONE] ok={ok}  vide={empty}  erreurs={err}  deja-existants={existing_files}")
    print(f"[SORTIE] {args.out}/")


if __name__ == "__main__":
    main()
