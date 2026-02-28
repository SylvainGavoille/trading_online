# -*- coding: utf-8 -*-
"""
Daily EOD option chain snapshot collector.

Connects to IBKR (TWS / IB Gateway), picks the top-N most-liquid symbols from
price_historical/, fetches their option chains, and saves one Parquet file per
day in the Hive-partitioned layout expected by src/ml/data/options.py:

    options_snapshot/year=YYYY/month=MM/day=YYYY-MM-DD/part-0.parquet

Usage
-----
# Full collection (requires TWS/Gateway running at market close)
uv run python src/data/collect_options_snapshot.py

# Show symbol universe without hitting IBKR
uv run python src/data/collect_options_snapshot.py --dry_run

# Override defaults
uv run python src/data/collect_options_snapshot.py --top_n 30 --dte_min 14 --dte_max 60
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import duckdb
import numpy as np
import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.utils import duckdb_scan

from ibapi.contract import Contract
from src.api.ib_connector import IBClient

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
        "batch_size": int(sec.get("batch_size", 20)),
        "batch_delay": float(sec.get("batch_delay_s", 1.0)),
        "min_price": float(sec.get("min_price_filter", 5.0)),
    }


# ---------------------------------------------------------------------------
# Symbol universe - top-N by volume from price_historical
# ---------------------------------------------------------------------------


def _find_day_dir(price_root: Path, ref_date: Optional[date] = None) -> Optional[Path]:
    """
    Return the Path to the day=YYYY-MM-DD directory for ref_date (or the
    most-recent available day when ref_date is None).

    Uses directory-listing only - never reads parquet files - so it is fast
    even when price_historical/ contains millions of files.
    """
    if ref_date is not None:
        p = (
            price_root
            / f"year={ref_date.year}"
            / f"month={ref_date.month:02d}"
            / f"day={ref_date.isoformat()}"
        )
        return p if p.is_dir() else None

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
    """
    Return the top-N symbols by volume from the most recent available day
    in price_historical/, filtered to stocks with close >= min_price.

    The price filter removes penny stocks that don't have listed options,
    which would otherwise waste time with Error 200 from IBKR.

    Only the single target day's files are scanned (~thousands of files),
    not the entire store (millions), so the query is fast.
    """
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
# Expiration / strike calculators (no IBKR API call needed)
# ---------------------------------------------------------------------------


def calc_expirations(
    today: date,
    dte_min: int,
    dte_max: int,
    max_n: int,
) -> List[date]:
    """
    Return upcoming standard US equity option expirations (Fridays) within
    [dte_min, dte_max] days, keeping at most max_n nearest.

    US equity options expire on Fridays (weekly) and, for less liquid names,
    only on the 3rd Friday of each month.  We include all Fridays so that
    contracts that don't exist are simply skipped at snapshot time.
    """
    result = []
    start = today + timedelta(days=max(dte_min, 1))
    end = today + timedelta(days=dte_max)
    # walk forward to first Friday
    d = start
    while d.weekday() != 4:  # 4 = Friday
        d += timedelta(days=1)
    while d <= end:
        result.append(d)
        d += timedelta(days=7)
    return result[:max_n]


def calc_strikes(spot: float, pct_range: float) -> List[float]:
    """
    Build a strike ladder around spot using standard US equity option increments:
        price < 5    -> $0.50 increments
        5  <= p < 25 -> $1 increments
        25 <= p < 50 -> $2.50 increments
        50 <= p < 200-> $5 increments
        200<= p < 500-> $10 increments
        p >= 500     -> $25 increments

    Returns only strikes within spot * (1 +/- pct_range).
    """
    if spot < 5:
        step = 0.50
    elif spot < 25:
        step = 1.0
    elif spot < 50:
        step = 2.5
    elif spot < 200:
        step = 5.0
    elif spot < 500:
        step = 10.0
    else:
        step = 25.0

    lo = spot * (1.0 - pct_range)
    hi = spot * (1.0 + pct_range)

    # Nearest strike at or below spot
    base = round(round(spot / step) * step, 4)
    strikes = []
    k = base
    while k <= hi:
        if k >= lo:
            strikes.append(round(k, 4))
        k = round(k + step, 4)
    k = round(base - step, 4)
    while k >= lo:
        strikes.append(round(k, 4))
        k = round(k - step, 4)
    return sorted(strikes)


# ---------------------------------------------------------------------------
# Spot price helpers
# ---------------------------------------------------------------------------


def _spot_from_yahoo(symbol: str) -> Optional[float]:
    """Fetch the most recent close price from Yahoo Finance."""
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as exc:
        print(f"  [{symbol}] Yahoo Finance error: {exc}")
    return None


def _spot_from_ibkr(ib: IBClient, symbol: str) -> Optional[float]:
    """Fetch the most recent close price from IBKR market data."""
    mkt = ib.get_market_data(symbol)
    if not mkt or not mkt.get("close"):
        return None
    spot_list = mkt["close"]
    val = float(spot_list[-1]) if spot_list else None
    return val if val and val > 0 else None


def get_spot_price(ib: IBClient, symbol: str) -> Optional[float]:
    """
    Return the spot price for symbol, trying Yahoo Finance first.
    Falls back to IBKR market data if Yahoo returns nothing.
    """
    spot = _spot_from_yahoo(symbol)
    if spot and spot > 0:
        print(f"  [{symbol}] spot={spot:.4f} (Yahoo Finance)")
        return spot
    print(f"  [{symbol}] Yahoo unavailable -- trying IBKR market data...")
    spot = _spot_from_ibkr(ib, symbol)
    if spot and spot > 0:
        print(f"  [{symbol}] spot={spot:.4f} (IBKR delayed)")
        return spot
    return None


# ---------------------------------------------------------------------------
# IBKR Option contract builder
# ---------------------------------------------------------------------------


def build_option_contract(
    symbol: str,
    expiry: date,
    strike: float,
    right: str,  # "C" or "P"
    multiplier: str = "100",
) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "OPT"
    c.exchange = "SMART"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = expiry.strftime("%Y%m%d")
    c.strike = strike
    c.right = right
    c.multiplier = multiplier
    return c


# ---------------------------------------------------------------------------
# Per-symbol collection
# ---------------------------------------------------------------------------


def collect_symbol(
    ib: IBClient,
    symbol: str,
    cfg: dict,
    today: date,
) -> List[dict]:
    """
    Fetch all option snapshot rows for one underlying symbol.

    Returns a list of row dicts (one per option contract with valid data).
    """
    # 1. Get current spot price (Yahoo Finance first, IBKR as fallback)
    spot = get_spot_price(ib, symbol)
    if not spot:
        print(f"  [{symbol}] No spot price available -- skipping")
        return []

    # 2. Calculate expirations and strikes locally (no reqSecDefOptParams needed)
    expirations = calc_expirations(
        today, cfg["dte_min"], cfg["dte_max"], cfg["max_expirations"]
    )
    strikes = calc_strikes(spot, cfg["moneyness_range"])
    multiplier = "100"  # standard for US equity options

    if not expirations or not strikes:
        print(f"  [{symbol}] No expirations/strikes (spot={spot:.2f}) -- skipping")
        return []

    # 4. Build contracts list
    contracts = [
        build_option_contract(symbol, exp, strike, right, multiplier)
        for exp in expirations
        for strike in strikes
        for right in ("C", "P")
    ]
    print(
        f"  [{symbol}] spot={spot:.2f}  expirations={len(expirations)}  "
        f"strikes={len(strikes)}  contracts={len(contracts)}"
    )

    # 5. Fetch snapshots in parallel batches.
    #
    # Strategy: fire all N requests in a batch SEQUENTIALLY from the main thread
    # (ibapi's socket writes are not safe to call from multiple threads
    # concurrently), then wait for all N events CONCURRENTLY using lightweight
    # wait threads (those threads do no IBKR API calls).
    #
    # This makes the batch wall-clock time equal to the SLOWEST response time
    # rather than N × slowest, giving a significant speedup.
    # Typical response times: < 1 s during market hours, ~14 s after hours with
    # reqMarketDataType(4) (delayed-frozen).
    rows = []
    batch_size = cfg["batch_size"]
    batch_delay = cfg["batch_delay"]
    snapshot_timeout = 15.0  # comfortable margin for the ~14 s after-hours case

    for batch_start in range(0, len(contracts), batch_size):
        batch = contracts[batch_start : batch_start + batch_size]

        # --- Phase 1: register events and fire all reqMktData calls (sequential) ---
        batch_state = []  # (req_id, event, contract)
        for contract in batch:
            req_id = ib._get_next_req_id()
            event = threading.Event()
            with ib._lock:
                ib._mktdata_results[req_id] = {
                    "bid": None,
                    "ask": None,
                    "last": None,
                    "volume": 0,
                    "open_interest": 0,
                    "iv": None,
                    "delta": None,
                    "gamma": None,
                    "vega": None,
                    "theta": None,
                    "und_price": None,
                }
                ib._mktdata_events[req_id] = event
            ib.reqMktData(req_id, contract, "", True, False, [])
            batch_state.append((req_id, event, contract))

        # --- Phase 2: wait for all events concurrently (threads only call event.wait) ---
        timed_out = {}  # req_id -> bool

        def _wait(req_id: int, ev: threading.Event) -> None:
            timed_out[req_id] = not ev.wait(timeout=snapshot_timeout)

        wait_threads = [
            threading.Thread(target=_wait, args=(rid, ev), daemon=True)
            for rid, ev, _ in batch_state
        ]
        for t in wait_threads:
            t.start()
        for t in wait_threads:
            t.join(timeout=snapshot_timeout + 2)

        # --- Phase 3: cancel timed-out subs and collect results (main thread) ---
        for req_id, _ev, _contract in batch_state:
            if timed_out.get(req_id):
                ib.cancelMktData(req_id)

        for req_id, _ev, contract in batch_state:
            with ib._lock:
                data = ib._mktdata_results.pop(req_id, {})
                ib._mktdata_events.pop(req_id, None)

            bid = data.get("bid")
            ask = data.get("ask")
            iv = data.get("iv")
            delta = data.get("delta")
            # Skip contracts with absolutely no useful data
            if bid is None and ask is None and iv is None and delta is None:
                continue

            rows.append(
                {
                    "underlying": symbol,
                    "right": contract.right,
                    "expiry": datetime.strptime(
                        contract.lastTradeDateOrContractMonth, "%Y%m%d"
                    ).date(),
                    "strike": float(contract.strike),
                    "bid": bid,
                    "ask": ask,
                    "last": data.get("last"),
                    "volume": data.get("volume", 0),
                    "openInterest": data.get("open_interest", 0),
                    "iv": data.get("iv"),
                    "delta": data.get("delta"),
                    "gamma": data.get("gamma"),
                    "vega": data.get("vega"),
                    "theta": data.get("theta"),
                    "multiplier": int(multiplier) if multiplier else 100,
                    "contractId": None,  # not returned by snapshot mode
                }
            )

        # Pause between batches to respect IBKR pacing limits
        if batch_start + batch_size < len(contracts):
            time.sleep(batch_delay)

    return rows


# ---------------------------------------------------------------------------
# Parquet writer
# ---------------------------------------------------------------------------


def save_snapshot(
    rows: List[dict],
    snap_date: date,
    options_root: Path,
) -> Path:
    """Save rows to Hive-partitioned Parquet compatible with read_options()."""
    df = pd.DataFrame(rows)
    df["date"] = pd.Timestamp(snap_date)

    # Cast types to match read_options() schema
    for col in ["bid", "ask", "last", "iv", "delta", "gamma", "vega", "theta"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["strike"] = df["strike"].astype("float64")
    df["volume"] = df["volume"].fillna(0).astype("int64")
    df["openInterest"] = df["openInterest"].fillna(0).astype("int64")
    df["multiplier"] = df["multiplier"].fillna(100).astype("int64")
    df["expiry"] = pd.to_datetime(df["expiry"])

    # Hive path
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
        description="Collect EOD option chain snapshots from IBKR"
    )
    ap.add_argument(
        "--date", default=None, help="Snapshot date YYYY-MM-DD (default: today)"
    )
    ap.add_argument(
        "--top_n", type=int, default=None, help="Override top_n_symbols from config"
    )
    ap.add_argument("--dte_min", type=int, default=None)
    ap.add_argument("--dte_max", type=int, default=None)
    ap.add_argument(
        "--max_exp", type=int, default=None, help="Override max_expirations from config"
    )
    ap.add_argument(
        "--moneyness",
        type=float,
        default=None,
        help="Override moneyness_range_pct (0–100; stored as fraction internally)",
    )
    ap.add_argument(
        "--dry_run",
        action="store_true",
        help="Print symbol universe only -- do not connect to IBKR",
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
    )

    # --- Symbol universe ---
    print(
        f"[universe] Scanning price_historical for top symbols by volume "
        f"(close >= ${cfg['min_price']:.2f})..."
    )
    symbols = get_top_n_symbols(price_root, cfg["top_n"], min_price=cfg["min_price"])
    if not symbols:
        print("[ERROR] No symbols found -- is price_historical populated?")
        sys.exit(1)
    print(
        f"[universe] {len(symbols)} symbols: {symbols[:10]}{'...' if len(symbols)>10 else ''}"
    )

    if args.dry_run:
        print("[dry_run] Done (--dry_run; IBKR not contacted).")
        return

    # --- IBKR connection ---
    print("[ibkr] Connecting...")
    raw_cfg = yaml.safe_load(open(CONFIG_PATH))
    # Use a dedicated client ID so this subprocess doesn't conflict with the
    # dashboard connection (which holds client_id 10).
    # Try a wider ID window because Cloud Run retries / parallel runs can leave
    # short-lived sessions around.
    base_id = raw_cfg.get("api", {}).get("collector_client_id", 11)
    ib = None
    for cid in range(base_id, base_id + 20):
        raw_cfg["api"]["client_id"] = cid
        candidate = IBClient(raw_cfg)
        print(
            f"[ibkr] trying host={candidate.host} port={candidate.port} client_id={cid}..."
        )
        if candidate.connect_and_run():
            ib = candidate
            print(f"[ibkr] Connected with client_id={cid}.")
            break
        # Ensure failed attempt is fully closed before next client_id.
        try:
            candidate.disconnect()
        except Exception:
            pass
        print(f"[ibkr] connection failed for client_id={cid}, trying next...")
        time.sleep(1)
    if ib is None:
        print(
            "[ERROR] Could not connect to IBKR on any client ID. "
            "Is TWS/IB Gateway running?"
        )
        sys.exit(1)
    time.sleep(1)  # let managed accounts callback arrive

    # Use delayed-frozen market data (type 4) for option snapshots.
    # Type 3 (15-min delayed) is unreliable for options after market close on a
    # paper account — IBKR often returns no data at all with type 3 after hours.
    # Type 4 explicitly requests frozen data and works consistently for EOD
    # option chain collection regardless of the time of day.
    ib.reqMarketDataType(4)

    # --- Collect ---
    today = snap_date
    all_rows: List[dict] = []
    n_ok = 0  # symbols with at least 1 option row
    n_skip = 0  # symbols skipped cleanly (no chain, no price, etc.)
    n_error = 0  # symbols that raised an exception

    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {symbol}")

        # Abort if IBKR disconnected mid-run
        if not ib.isConnected():
            print("\n[FATAL] IBKR connection lost -- aborting collection.")
            print(
                f"        Collected {len(all_rows):,} rows from {n_ok} symbols before disconnect."
            )
            ib.disconnect()
            sys.exit(1)

        try:
            rows = collect_symbol(ib, symbol, cfg, today)
            all_rows.extend(rows)
            if rows:
                n_ok += 1
                print(f"  OK: {len(rows)} option rows")
            else:
                n_skip += 1
        except Exception as exc:
            n_error += 1
            print(f"  ERROR: {exc}")

    ib.disconnect()

    # --- Summary ---
    total = len(symbols)
    print(f"\n{'='*55}")
    print(f"  Collection summary for {snap_date}")
    print(f"{'='*55}")
    print(f"  Symbols processed : {total}")
    print(f"  With option data  : {n_ok}")
    print(f"  Skipped (no chain): {n_skip}")
    print(f"  Errors            : {n_error}")
    print(f"  Total option rows : {len(all_rows):,}")
    print(f"{'='*55}")

    # --- Save ---
    if not all_rows:
        print(
            "\n[ERROR] No option data collected -- options_snapshot/ was NOT written."
        )
        if n_error == total:
            print(
                "        All symbols failed with errors. Check IBKR connection and permissions."
            )
        elif n_skip == total:
            print(
                "        All symbols were skipped (no listed options or no price data)."
            )
            print("        Try increasing --top_n or lowering --dte_min / --dte_max.")
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
