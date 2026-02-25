"""Read EOD underlying prices from the Hive-partitioned price_historical/ store."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.ml.utils import PRICE_HISTORICAL_ROOT, duckdb_scan


def read_underlyings(
    start: str,
    end: str,
    price_root: Path = PRICE_HISTORICAL_ROOT,
) -> pd.DataFrame:
    """
    Scan all price_historical Parquet files with DuckDB and return a
    (symbol, date) table filtered to [start, end].

    Store layout (one row per file):
        year=YYYY/month=MM/day=YYYY-MM-DD/{SYMBOL}.parquet
        columns: symbol, date, open, high, low, close, volume
    """
    # as_posix() ensures forward slashes on Windows (required by DuckDB glob)
    glob = (price_root / "**" / "*.parquet").as_posix()

    con = duckdb.connect(":memory:")
    # Filter on the *partition* column `day` (not the data column `date`) so
    # DuckDB can skip directories outside the requested range without opening
    # any files.  ISO "YYYY-MM-DD" strings sort correctly as text.
    q = f"""
    SELECT
        symbol,
        date,
        open::DOUBLE   AS open,
        high::DOUBLE   AS high,
        low::DOUBLE    AS low,
        close::DOUBLE  AS close,
        volume::BIGINT AS volume
    FROM read_parquet('{glob}', hive_partitioning = true)
    WHERE day >= '{start}'
      AND day <= '{end}'
    """
    df = duckdb_scan(con, q)
    if df.empty:
        raise RuntimeError(
            f"No underlying data found for [{start}, {end}] in {price_root}.\n"
            "Make sure price_historical/ is populated (run fill_gaps.py first)."
        )
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["symbol", "date"], inplace=True)
    return df.reset_index(drop=True)
