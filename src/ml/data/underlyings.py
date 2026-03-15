"""Read EOD underlying prices from the Hive-partitioned price_historical/ store."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from src.ml.utils import (
    PRICE_HISTORICAL_ROOT,
    duckdb_scan,
    gcs_data_uri,
    gcs_mount_path,
    fs_path_to_gcs_uri,
)


def _read_underlyings_gcs(start: str, end: str, price_root: Path) -> pd.DataFrame:
    """
    Read underlyings directly from GCS using pyarrow.fs.GcsFileSystem.

    Uses Application Default Credentials / workload identity (no explicit token
    needed on Cloud Run).  Partition pruning is handled by pyarrow.dataset so
    only the relevant day directories are fetched.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    from pyarrow.fs import GcsFileSystem

    pa.set_io_thread_count(32)  # Parallelize GCS file reads (default = num CPUs ≈ 2 on Cloud Run)

    gcs_prefix = fs_path_to_gcs_uri(price_root)  # gs://bucket/price_historical
    if not gcs_prefix:
        raise RuntimeError("fs_path_to_gcs_uri returned None — check GCS_DATA_URI/GCS_MOUNT_PATH")

    # pyarrow expects "bucket/path", not "gs://bucket/path"
    bucket_path = gcs_prefix.removeprefix("gs://")

    fs = GcsFileSystem()
    dataset = ds.dataset(bucket_path, filesystem=fs, format="parquet", partitioning="hive")

    table = dataset.to_table(
        filter=(pc.field("day") >= start) & (pc.field("day") <= end),
        columns=["symbol", "date", "open", "high", "low", "close", "volume"],
    )
    return table.to_pandas()


def _candidate_parquet_globs(price_root: Path, start: str, end: str) -> list[str]:
    """
    Build day-partition glob paths for local (GCSFuse) filesystem reads.
    Only includes directories that actually exist (skips weekends/holidays).
    """
    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end)
    if end_day < start_day:
        raise ValueError(f"end={end} is before start={start}")

    globs: list[str] = []
    day = start_day
    while day <= end_day:
        day_str = day.isoformat()
        day_dir = (
            price_root
            / f"year={day.year:04d}"
            / f"month={day.month:02d}"
            / f"day={day_str}"
        )
        if day_dir.exists():
            globs.append((day_dir / "*.parquet").as_posix())
        day += timedelta(days=1)
    return globs


def read_underlyings(
    start: str,
    end: str,
    price_root: Path = PRICE_HISTORICAL_ROOT,
) -> pd.DataFrame:
    """
    Return a (symbol, date) table filtered to [start, end].

    Store layout:
        year=YYYY/month=MM/day=YYYY-MM-DD/{SYMBOL}.parquet
        columns: symbol, date, open, high, low, close, volume

    On Cloud Run (GCS_DATA_URI + GCS_MOUNT_PATH set): reads directly from GCS
    via pyarrow.fs.GcsFileSystem using workload identity — bypasses GCSFuse.
    Locally: reads from local filesystem via DuckDB.
    """
    if gcs_data_uri() and gcs_mount_path():
        df = _read_underlyings_gcs(start, end, price_root)
    else:
        parquet_globs = _candidate_parquet_globs(price_root, start, end)
        if not parquet_globs:
            raise RuntimeError(
                f"No underlying day partitions found for [{start}, {end}] in {price_root}.\n"
                "Make sure price_historical/ is populated for the requested window."
            )
        con = duckdb.connect(":memory:")
        globs_sql = ", ".join(f"'{g}'" for g in parquet_globs)
        q = f"""
        SELECT
            symbol,
            date,
            open::DOUBLE   AS open,
            high::DOUBLE   AS high,
            low::DOUBLE    AS low,
            close::DOUBLE  AS close,
            volume::BIGINT AS volume
        FROM read_parquet([{globs_sql}], hive_partitioning = true)
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
