"""Read EOD options snapshots from the Hive-partitioned options_snapshot/ store."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.ml.utils import OPTIONS_SNAPSHOT_ROOT, duckdb_scan


def read_options(
    start: str,
    end: str,
    options_root: Path = OPTIONS_SNAPSHOT_ROOT,
) -> pd.DataFrame:
    """
    Scan options_snapshot/ Parquet files and return a flat options table
    filtered to [start, end].

    Expected store layout:
        options_snapshot/year=YYYY/month=MM/day=YYYY-MM-DD/part-*.parquet

    Minimum required columns:
        date, underlying, right (C/P), expiry, strike,
        bid, ask, volume (opt), openInterest (opt),
        iv, delta, gamma, vega, theta (all optional),
        multiplier (default 100), contractId (optional)

    You must supply this data from IBKR EOD option chain pulls.
    Use the IBKR TWS API (reqMktData / reqContractDetails) or
    ib_insync's reqSecDefOptParams + snapshot loop to build it.
    """
    if not options_root.exists():
        raise RuntimeError(
            f"options_snapshot/ directory not found at {options_root}.\n"
            "You need to populate it from IBKR EOD option chain data."
        )

    glob = (options_root / "**" / "*.parquet").as_posix()
    con = duckdb.connect(":memory:")
    q = f"""
    SELECT
        date,
        underlying,
        "right",
        expiry,
        strike::DOUBLE                          AS strike,
        bid::DOUBLE                             AS bid,
        ask::DOUBLE                             AS ask,
        COALESCE(last,    NULL)::DOUBLE         AS last,
        COALESCE(volume,       0)::BIGINT       AS volume,
        COALESCE(openInterest, 0)::BIGINT       AS openInterest,
        COALESCE(iv,      NULL)::DOUBLE         AS iv,
        COALESCE(delta,   NULL)::DOUBLE         AS delta,
        COALESCE(gamma,   NULL)::DOUBLE         AS gamma,
        COALESCE(vega,    NULL)::DOUBLE         AS vega,
        COALESCE(theta,   NULL)::DOUBLE         AS theta,
        COALESCE(multiplier, 100)::BIGINT       AS multiplier,
        COALESCE(contractId, NULL)              AS contractId
    FROM read_parquet('{glob}', hive_partitioning = true)
    WHERE date >= '{start}'
      AND date <= '{end}'
    """
    df = duckdb_scan(con, q)
    if df.empty:
        raise RuntimeError(
            f"No options snapshots found for [{start}, {end}] in {options_root}."
        )
    df["date"]   = pd.to_datetime(df["date"])
    df["expiry"] = pd.to_datetime(df["expiry"])
    df["right"]  = df["right"].astype(str).str.upper()
    df.sort_values(["underlying", "date", "expiry", "strike", "right"], inplace=True)
    return df.reset_index(drop=True)
