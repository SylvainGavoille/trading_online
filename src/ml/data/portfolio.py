"""
Portfolio daily state: read from Hive-partitioned files and/or live IBKR.

Workflow
--------
1. Collect daily snapshots (automated or manual):
       from src.ml.data.portfolio import snapshot_from_ibkr, save_portfolio_snapshot
       snap = snapshot_from_ibkr(ib_client)   # requires connected IBClient
       save_portfolio_snapshot(snap, PORTFOLIO_DAILY_ROOT)

2. Feed the pipeline:
       df = read_portfolio(start="2025-02-20", end="2026-02-23")

Schema stored (one row per day):
    date          YYYY-MM-DD
    cash          float   TotalCashValue
    buying_power  float   BuyingPower
    net_liq       float   NetLiquidation
    margin_used   float   GrossPositionValue (proxy for margin)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import duckdb
import numpy as np
import pandas as pd

from src.ml.utils import PORTFOLIO_DAILY_ROOT


# ---------------------------------------------------------------------------
# IBKR live snapshot
# ---------------------------------------------------------------------------

def snapshot_from_ibkr(ib_client) -> dict:
    """
    Pull the current portfolio state from a connected IBClient instance
    (src.api.ib_connector.IBClient).

    Returns a dict matching the portfolio schema.
    """
    try:
        summary = ib_client.get_account_summary(timeout=10.0) or {}
    except Exception as exc:
        raise RuntimeError(f"IBKR account summary request failed: {exc}") from exc

    def _f(key: str) -> float:
        v = summary.get(key)
        try:
            return float(v) if v is not None else float("nan")
        except (TypeError, ValueError):
            return float("nan")

    return {
        "date":         date.today().isoformat(),
        "cash":         _f("TotalCashValue"),
        "buying_power": _f("BuyingPower"),
        "net_liq":      _f("NetLiquidation"),
        # GrossPositionValue is the market value of all open positions —
        # a reasonable v1 proxy for margin used.
        "margin_used":  _f("GrossPositionValue"),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_portfolio_snapshot(
    snapshot: dict,
    portfolio_root: Path = PORTFOLIO_DAILY_ROOT,
) -> Path:
    """
    Save one portfolio snapshot to the Hive-partitioned portfolio_daily/ store.

    Path written:
        portfolio_root/year=YYYY/month=MM/day=YYYY-MM-DD/portfolio.parquet
    """
    d = pd.to_datetime(snapshot["date"])
    partition = (
        portfolio_root
        / f"year={d.year}"
        / f"month={d.month:02}"
        / f"day={d.date().isoformat()}"
    )
    partition.mkdir(parents=True, exist_ok=True)
    path = partition / "portfolio.parquet"
    pd.DataFrame([snapshot]).to_parquet(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Read historical data
# ---------------------------------------------------------------------------

def read_portfolio(
    start: str,
    end: str,
    portfolio_root: Path = PORTFOLIO_DAILY_ROOT,
    ib_client=None,
) -> pd.DataFrame:
    """
    Load portfolio daily state for [start, end].

    If ib_client is provided, today's snapshot is auto-saved when missing.
    Supports Parquet (Hive-partitioned) or flat CSV files as source.

    Raises RuntimeError with actionable guidance when no data is found.
    """
    # Optionally refresh today's snapshot from live IBKR
    if ib_client is not None:
        _maybe_refresh_today(ib_client, portfolio_root)

    # --- Parquet path ---
    if portfolio_root.exists() and list(portfolio_root.glob("**/*.parquet")):
        glob = (portfolio_root / "**" / "*.parquet").as_posix()
        con = duckdb.connect(":memory:")
        q = f"""
        SELECT
            date,
            cash::DOUBLE         AS cash,
            buying_power::DOUBLE AS buying_power,
            net_liq::DOUBLE      AS net_liq,
            margin_used::DOUBLE  AS margin_used
        FROM read_parquet('{glob}', hive_partitioning = true)
        WHERE date >= '{start}'
          AND date <= '{end}'
        """
        df = con.execute(q).df()

    # --- CSV fallback ---
    elif portfolio_root.exists() and list(portfolio_root.glob("**/*.csv")):
        frames = [pd.read_csv(f) for f in portfolio_root.glob("**/*.csv")]
        df = pd.concat(frames, ignore_index=True)
        df = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    else:
        raise RuntimeError(
            f"No portfolio data found in {portfolio_root}.\n\n"
            "Build history by running daily:\n"
            "  from src.ml.data.portfolio import snapshot_from_ibkr, save_portfolio_snapshot\n"
            "  save_portfolio_snapshot(snapshot_from_ibkr(ib_client))\n\n"
            "Or provide a CSV with columns: date, cash, buying_power, net_liq, margin_used."
        )

    if df.empty:
        raise RuntimeError(
            f"Portfolio data is empty for [{start}, {end}].\n"
            "Make sure daily snapshots exist for this date range."
        )

    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _maybe_refresh_today(ib_client, portfolio_root: Path) -> None:
    today = date.today().isoformat()
    d = pd.to_datetime(today)
    today_path = (
        portfolio_root
        / f"year={d.year}"
        / f"month={d.month:02}"
        / f"day={today}"
        / "portfolio.parquet"
    )
    if not today_path.exists():
        try:
            snap = snapshot_from_ibkr(ib_client)
            save_portfolio_snapshot(snap, portfolio_root)
            print(f"[portfolio] Saved today's snapshot → {today_path}")
        except Exception as exc:
            print(f"[portfolio] Could not refresh IBKR snapshot: {exc}")
