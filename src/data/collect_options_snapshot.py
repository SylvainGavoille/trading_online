# -*- coding: utf-8 -*-
"""
Daily EOD option chain snapshot collector (Yahoo Finance).

Fetches option chains for the top-N most-liquid symbols from price_historical/
and saves one Parquet file per day in the Hive-partitioned layout expected by
src/ml/data/options.py:

    options_snapshot/year=YYYY/month=MM/day=YYYY-MM-DD/part-0.parquet

NOTE: Yahoo Finance only provides *current* option market data. It does not
expose historical snapshots for past dates. Each daily run captures today's
bid/ask/iv/volume/OI. Greeks (delta/gamma/vega/theta) are not available from
Yahoo and will be None in the output.

Usage
-----
# Full collection
uv run python src/data/collect_options_snapshot.py

# Show symbol universe without fetching options
uv run python src/data/collect_options_snapshot.py --dry_run

# Override defaults
uv run python src/data/collect_options_snapshot.py --top_n 30 --dte_min 14 --dte_max 60
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import List, Optional

import duckdb
import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.utils import duckdb_scan

PRICE_HISTORICAL_ROOT = _PROJECT_ROOT / "price_historical"
OPTIONS_SNAPSHOT_ROOT = _PROJECT_ROOT / "options_snapshot"
CONFIG_PATH = _PROJECT_ROOT / "src" / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    sec = cfg.get("options_collector", {})
    return {
        "top_n": int(sec.get("top_n_symbols", 50)),
        "dte_min": int(sec.get("dte_min", 7)),
        "dte_max": int(sec.get("dte_max", 90)),
        "moneyness_range": float(sec.get("moneyness_range_pct", 0.20)),
        "max_expirations": int(sec.get("max_expirations", 3)),
        "batch_delay": float(sec.get("batch_delay_s", 1.0)),
        "min_price": float(sec.get("min_price_filter", 5.0)),
    }


# ---------------------------------------------------------------------------
# Symbol universe - top-N by volume from price_historical
# ---------------------------------------------------------------------------


def _find_day_dir(price_root: Path, ref_date: Optional[date] = None) -> Optional[Path]:
    if ref_date is not None:
        p = (
            price_root
            / f"year={ref_date.year}"
            / f"month={ref_date.month:02d}"
            / f"day={ref_date.isoformat()}"
        )
        if p.is_dir():
            return p
        # Exact date not found — fall back to the most recent available day.
        print(
            f"[universe] day={ref_date.isoformat()} not found in price_historical/; "
            "falling back to latest available day.",
            flush=True,
        )

    latest_dir: Optional[Path] = None
    latest_str: str = ""
    for year_dir in price_root.glob("year=*"):
        for month_dir in year_dir.glob("month=*"):
            for day_dir in month_dir.glob("day=*"):
                day_str = day_dir.name
                if day_str > latest_str:
                    latest_str = day_str
                    latest_dir = day_dir
    return latest_dir


def get_top_n_symbols(
    price_root: Path,
    n: int,
    ref_date: Optional[date] = None,
    min_price: float = 5.0,
) -> List[str]:
    day_dir = _find_day_dir(price_root, ref_date)
    if day_dir is None:
        print("[universe] No day directory found in price_historical/")
        return []

    day_glob = day_dir.as_posix() + "/*.parquet"
    day_label = day_dir.name.replace("day=", "")
    print(f"[universe] Using day {day_label}  ({day_dir})")

    con = duckdb.connect()
    sql = f"""
        SELECT symbol, volume
        FROM read_parquet('{day_glob}')
        WHERE close >= {min_price}
        ORDER BY volume DESC NULLS LAST
        LIMIT {n}
    """
    try:
        df = duckdb_scan(con, sql)
        if df.empty:
            print(
                f"[universe] No symbols with close >= ${min_price:.2f} found. "
                "Try lowering min_price_filter in config."
            )
            return []
        return df["symbol"].tolist()
    except Exception as exc:
        print(f"[universe] DuckDB query failed: {exc}")
        return []
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float_or_none(v) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _to_int_or_zero(v) -> int:
    try:
        if v is None or pd.isna(v):
            return 0
        return int(v)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Per-symbol collection (Yahoo Finance)
# ---------------------------------------------------------------------------


def collect_symbol(symbol: str, cfg: dict, today: date) -> List[dict]:
    """
    Fetch option chain for one underlying from Yahoo Finance.
    Returns a list of row dicts (one per option contract with valid data).
    """
    import yfinance as yf

    # 1. Spot price
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            print(f"  [{symbol}] No spot price from Yahoo -- skipping")
            return []
        spot = float(hist["Close"].iloc[-1])
        print(f"  [{symbol}] spot={spot:.4f}")
    except Exception as exc:
        print(f"  [{symbol}] Yahoo spot error: {exc} -- skipping")
        return []

    # 2. Filter expirations by DTE
    try:
        tk = yf.Ticker(symbol)
        exp_dates = []
        for exp_str in tk.options or []:
            try:
                d = date.fromisoformat(exp_str)
            except Exception:
                continue
            dte = (d - today).days
            if cfg["dte_min"] <= dte <= cfg["dte_max"]:
                exp_dates.append(d)
        exp_dates = sorted(exp_dates)[: cfg["max_expirations"]]
        if not exp_dates:
            print(
                f"  [{symbol}] No expirations in DTE range "
                f"[{cfg['dte_min']},{cfg['dte_max']}] -- skipping"
            )
            return []
    except Exception as exc:
        print(f"  [{symbol}] Yahoo options list error: {exc} -- skipping")
        return []

    # 3. Fetch chains and filter by moneyness
    lo = spot * (1.0 - cfg["moneyness_range"])
    hi = spot * (1.0 + cfg["moneyness_range"])
    rows: List[dict] = []

    for exp in exp_dates:
        try:
            chain = tk.option_chain(exp.isoformat())
        except Exception as exc:
            print(f"  [{symbol}] chain fetch error for {exp}: {exc}")
            continue

        for right, side_df in (("C", chain.calls), ("P", chain.puts)):
            if side_df is None or side_df.empty or "strike" not in side_df.columns:
                continue
            sub = side_df[(side_df["strike"] >= lo) & (side_df["strike"] <= hi)]
            for _idx, r in sub.iterrows():
                bid = _to_float_or_none(r.get("bid"))
                ask = _to_float_or_none(r.get("ask"))
                last = _to_float_or_none(r.get("lastPrice"))
                iv = _to_float_or_none(r.get("impliedVolatility"))
                volume = _to_int_or_zero(r.get("volume"))
                oi = _to_int_or_zero(r.get("openInterest"))
                if (
                    bid is None
                    and ask is None
                    and last is None
                    and iv is None
                    and volume == 0
                    and oi == 0
                ):
                    continue
                rows.append(
                    {
                        "underlying": symbol,
                        "right": right,
                        "expiry": exp,
                        "strike": float(r["strike"]),
                        "bid": bid,
                        "ask": ask,
                        "last": last,
                        "volume": volume,
                        "openInterest": oi,
                        "iv": iv,
                        "delta": None,
                        "gamma": None,
                        "vega": None,
                        "theta": None,
                        "multiplier": 100,
                        "contractId": None,
                    }
                )

    return rows


# ---------------------------------------------------------------------------
# Parquet writer
# ---------------------------------------------------------------------------


def save_snapshot(rows: List[dict], snap_date: date, options_root: Path) -> Path:
    df = pd.DataFrame(rows)
    df["date"] = pd.Timestamp(snap_date)

    for col in ["bid", "ask", "last", "iv", "delta", "gamma", "vega", "theta"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["strike"] = df["strike"].astype("float64")
    df["volume"] = df["volume"].fillna(0).astype("int64")
    df["openInterest"] = df["openInterest"].fillna(0).astype("int64")
    df["multiplier"] = df["multiplier"].fillna(100).astype("int64")
    df["expiry"] = pd.to_datetime(df["expiry"])

    out_dir = (
        options_root
        / f"year={snap_date.year}"
        / f"month={snap_date.month:02d}"
        / f"day={snap_date.isoformat()}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "part-0.parquet"
    df.to_parquet(out_path, index=False)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Collect EOD option chain snapshots from Yahoo Finance"
    )
    ap.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD (default: today)")
    ap.add_argument("--top_n", type=int, default=None, help="Override top_n_symbols from config")
    ap.add_argument("--dte_min", type=int, default=None)
    ap.add_argument("--dte_max", type=int, default=None)
    ap.add_argument("--max_exp", type=int, default=None, help="Override max_expirations from config")
    ap.add_argument(
        "--moneyness",
        type=float,
        default=None,
        help="Override moneyness_range_pct (0-100; stored as fraction internally)",
    )
    ap.add_argument(
        "--max_minutes",
        type=float,
        default=None,
        help="Hard wall-clock cap (minutes). Stops after limit and saves what was collected.",
    )
    ap.add_argument(
        "--dry_run",
        action="store_true",
        help="Print symbol universe only -- do not fetch options",
    )
    ap.add_argument("--price_root", default=str(PRICE_HISTORICAL_ROOT))
    ap.add_argument("--out_root", default=str(OPTIONS_SNAPSHOT_ROOT))
    args = ap.parse_args()

    cfg = load_config()
    if args.top_n is not None:
        cfg["top_n"] = args.top_n
    if args.dte_min is not None:
        cfg["dte_min"] = args.dte_min
    if args.dte_max is not None:
        cfg["dte_max"] = args.dte_max
    if args.max_exp is not None:
        cfg["max_expirations"] = args.max_exp
    if args.moneyness is not None:
        cfg["moneyness_range"] = args.moneyness / 100.0

    snap_date = date.fromisoformat(args.date) if args.date else date.today()
    price_root = Path(args.price_root)
    out_root = Path(args.out_root)

    print(
        f"[collector] date={snap_date}  top_n={cfg['top_n']}"
        f"  DTE=[{cfg['dte_min']},{cfg['dte_max']}]"
        f"  moneyness=+-{cfg['moneyness_range']*100:.0f}%"
        f"  max_exp={cfg['max_expirations']}"
        f"  source=Yahoo Finance"
    )

    print(
        f"[universe] Scanning price_historical for top symbols by volume "
        f"(close >= ${cfg['min_price']:.2f})..."
    )
    symbols = get_top_n_symbols(
        price_root,
        cfg["top_n"],
        ref_date=snap_date,
        min_price=cfg["min_price"],
    )
    if not symbols:
        print("[ERROR] No symbols found -- is price_historical populated?")
        sys.exit(1)
    print(
        f"[universe] {len(symbols)} symbols: {symbols[:10]}{'...' if len(symbols) > 10 else ''}"
    )

    if args.dry_run:
        print("[dry_run] Done (--dry_run; Yahoo Finance not contacted).")
        return

    all_rows: List[dict] = []
    n_ok = 0
    n_skip = 0
    n_error = 0
    t_start = time.perf_counter()
    processed = 0

    for i, symbol in enumerate(symbols, 1):
        if args.max_minutes is not None:
            elapsed_min = (time.perf_counter() - t_start) / 60.0
            if elapsed_min >= args.max_minutes:
                print(
                    f"[collector] Reached max_minutes={args.max_minutes:.1f} after "
                    f"{elapsed_min:.1f}m. Stopping early."
                )
                break

        print(f"[{i}/{len(symbols)}] {symbol}")
        t_symbol = time.perf_counter()
        processed += 1

        try:
            rows = collect_symbol(symbol, cfg, snap_date)
            all_rows.extend(rows)
            elapsed = time.perf_counter() - t_symbol
            if rows:
                n_ok += 1
                print(f"  OK: {len(rows)} option rows  ({elapsed:.2f}s)")
            else:
                n_skip += 1
                print(f"  SKIP  ({elapsed:.2f}s)")
        except Exception as exc:
            n_error += 1
            elapsed = time.perf_counter() - t_symbol
            print(f"  ERROR: {exc}  ({elapsed:.2f}s)")

        # Respect Yahoo rate limits
        time.sleep(cfg["batch_delay"])

    total = len(symbols)
    print(f"\n{'='*55}")
    print(f"  Collection summary for {snap_date}")
    print(f"{'='*55}")
    print(f"  Symbols processed : {processed}/{total}")
    print(f"  With option data  : {n_ok}")
    print(f"  Skipped (no chain): {n_skip}")
    print(f"  Errors            : {n_error}")
    print(f"  Total option rows : {len(all_rows):,}")
    print(f"{'='*55}")

    if not all_rows:
        print("\n[ERROR] No option data collected -- options_snapshot/ was NOT written.")
        sys.exit(1)

    out_path = save_snapshot(all_rows, snap_date, out_root)
    print(f"\n[OK] Saved {len(all_rows):,} rows -> {out_path}")
    print(
        f"     symbols={len(set(r['underlying'] for r in all_rows))}"
        f"  calls={sum(1 for r in all_rows if r['right']=='C')}"
        f"  puts={sum(1 for r in all_rows if r['right']=='P')}"
    )


if __name__ == "__main__":
    main()
