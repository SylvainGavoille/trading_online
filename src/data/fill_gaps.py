#!/usr/bin/env python3
"""
Détecte et comble les jours manquants dans price_historical/.

Algorithme :
  1. Utilise les dates d'AAPL comme référence des jours de trading réels
     (élimine automatiquement les jours fériés US).
  2. Pour chaque symbole présent dans le store, calcule les jours manquants.
  3. Groupe par date → batch-download yfinance (100 symboles / appel).
  4. Sauvegarde uniquement les fichiers vraiment manquants.

Usage :
  python src/data/fill_gaps.py
  python src/data/fill_gaps.py --out price_historical --batch-size 100 --pause 1.0
  python src/data/fill_gaps.py --ref SPY          # autre symbole de référence
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.data.download_history import fetch_batch, parquet_path, save_parquet

DATA_ROOT_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "..", "price_historical"
)


# ---------------------------------------------------------------------------
# Scan helpers
# ---------------------------------------------------------------------------


def scan_store(root: str) -> tuple[set[str], dict[str, set[str]]]:
    """
    Walk price_historical/ and return:
      - all_days  : set of all date strings (YYYY-MM-DD) found in dir names
      - sym_dates : {symbol: set(date_strings)} — dates for which the file exists
    """
    all_days: set[str] = set()
    sym_dates: dict[str, set[str]] = defaultdict(set)

    for dirpath, _dirs, files in os.walk(root):
        folder = os.path.basename(dirpath)
        if not folder.startswith("day="):
            continue
        day_str = folder[4:]  # strip "day="
        all_days.add(day_str)
        for fname in files:
            if fname.endswith(".parquet"):
                sym_dates[fname[:-8]].add(day_str)

    return all_days, dict(sym_dates)


def get_reference_days(sym_dates: dict[str, set[str]], ref_symbol: str) -> set[str]:
    """
    Return the set of trading days present for ref_symbol.
    Falls back to the most-represented symbol if ref_symbol is absent.
    """
    if ref_symbol in sym_dates:
        return set(sym_dates[ref_symbol])

    print(
        f"[WARN] Symbole de référence '{ref_symbol}' absent du store — "
        "utilisation du symbole avec le plus de données."
    )
    best = max(sym_dates, key=lambda s: len(sym_dates[s]))
    print(f"       Référence : {best} ({len(sym_dates[best])} jours)")
    return set(sym_dates[best])


# ---------------------------------------------------------------------------
# Gap computation
# ---------------------------------------------------------------------------


def compute_gaps(
    sym_dates: dict[str, set[str]],
    trading_days: set[str],
) -> dict[str, list[date]]:
    """
    Return {symbol: [missing_date, ...]} for all symbols that have gaps.
    Only considers dates in trading_days (real market days).
    """
    gaps: dict[str, list[date]] = {}
    for sym, present in sym_dates.items():
        missing = sorted(date.fromisoformat(d) for d in trading_days - present)
        if missing:
            gaps[sym] = missing
    return gaps


# ---------------------------------------------------------------------------
# Download + fill
# ---------------------------------------------------------------------------


def fill_gaps(
    gaps: dict[str, list[date]],
    data_root: str,
    batch_size: int,
    pause: float,
) -> None:
    """
    For each missing (symbol, date) pair:
      - groups symbols by the day they're missing
      - batch-downloads via fetch_batch (one yfinance call per batch per day)
      - writes only the files that are truly absent
    """
    # Invert: day → [symbols missing that day]
    day_to_syms: dict[date, list[str]] = defaultdict(list)
    for sym, missing_days in gaps.items():
        for d in missing_days:
            day_to_syms[d].append(sym)

    total_pairs = sum(len(v) for v in day_to_syms.values())
    print(
        f"\n[GAPS] {len(gaps):,} symboles | {total_pairs:,} fichiers à télécharger"
        f" sur {len(day_to_syms)} jour(s)"
    )

    saved = 0
    empty = 0
    days_done = 0

    for trading_day in sorted(day_to_syms):
        symbols = day_to_syms[trading_day]
        days_done += 1

        # Split into batches
        batches = [
            symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)
        ]
        for b_idx, batch in enumerate(batches, 1):
            # fetch_batch needs a range; use [day, day] → 1-day window
            results = fetch_batch(batch, trading_day, trading_day)

            for sym in batch:
                df = results.get(sym)
                if df is None or df.empty:
                    empty += 1
                    continue
                # filter to exactly this date (fetch_batch may return a range)
                df_day = df[df["date"] == trading_day]
                if df_day.empty:
                    empty += 1
                    continue
                path = parquet_path(data_root, trading_day, sym)
                if not os.path.exists(path):
                    save_parquet(df_day.reset_index(drop=True), path)
                    saved += 1

            if len(batches) > 1:
                time.sleep(pause)

        print(
            f"  {trading_day}  [{days_done}/{len(day_to_syms)}]"
            f"  sauvegardés: {saved:,}  vides/introuvables: {empty:,}",
            flush=True,
        )

        if days_done < len(day_to_syms):
            time.sleep(pause)

    print(f"\n[DONE] Fichiers Parquet créés : {saved:,}  |  Sans données : {empty:,}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Comble les jours manquants dans price_historical/"
    )
    ap.add_argument(
        "--out",
        default=DATA_ROOT_DEFAULT,
        help="Dossier Parquet (défaut: price_historical/)",
    )
    ap.add_argument(
        "--ref",
        default="AAPL",
        help="Symbole de référence pour les jours de trading (défaut: AAPL)",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Symboles par appel yfinance (défaut: 100)",
    )
    ap.add_argument(
        "--pause",
        type=float,
        default=1.0,
        help="Pause entre batches en secondes (défaut: 1.0)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Affiche les gaps sans télécharger"
    )
    args = ap.parse_args()

    root = os.path.normpath(args.out)
    print(f"[STORE] {root}")

    # 1. Scan
    print("[1/3] Scan du store Parquet…")
    t0 = time.time()
    all_days, sym_dates = scan_store(root)
    print(
        f"      {len(all_days)} jours  |  {len(sym_dates):,} symboles  "
        f"({time.time()-t0:.1f}s)"
    )

    if not sym_dates:
        print("[ERR] Store vide — lancez d'abord download_history.py")
        sys.exit(1)

    # 2. Reference trading days
    print(f"[2/3] Calcul des gaps (référence: {args.ref})…")
    trading_days = get_reference_days(sym_dates, args.ref)
    print(f"      {len(trading_days)} jours de trading réels")

    gaps = compute_gaps(sym_dates, trading_days)

    total_missing = sum(len(v) for v in gaps.values())
    print(
        f"      {len(gaps):,} symboles avec gaps  |  {total_missing:,} fichiers manquants"
    )

    if not gaps:
        print("[DONE] Aucun gap — le store est complet.")
        return

    # Top missing days
    from collections import Counter

    day_counts: Counter = Counter()
    for days in gaps.values():
        for d in days:
            day_counts[d] += 1
    print("      Top 5 jours les plus manquants :")
    for d, n in day_counts.most_common(5):
        print(f"        {d} : {n:,} symboles")

    if args.dry_run:
        print("[DRY-RUN] Fin (pas de téléchargement).")
        return

    # 3. Download & fill
    print(
        f"[3/3] Téléchargement des gaps (batch={args.batch_size}, pause={args.pause}s)…"
    )
    fill_gaps(gaps, root, args.batch_size, args.pause)


if __name__ == "__main__":
    main()
