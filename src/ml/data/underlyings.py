"""Read EOD underlying prices from the Hive-partitioned price_historical/ store."""
from __future__ import annotations

import concurrent.futures
import io
import time
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
    Read underlyings from GCS using google.cloud.storage with parallel downloads.

    Replaces pyarrow.dataset discovery (which lists ALL 2.37M+ files before
    pruning) with:
      1. Parallel LIST calls on only the target day directories (32 threads, ~5 s)
      2. Parallel file downloads + in-memory parquet parse (200 threads, ~3-8 min)

    Uses Application Default Credentials / workload identity on Cloud Run.
    """
    from google.cloud import storage as gcs_storage

    gcs_prefix = fs_path_to_gcs_uri(price_root)
    if not gcs_prefix:
        raise RuntimeError("fs_path_to_gcs_uri returned None — check GCS_DATA_URI/GCS_MOUNT_PATH")

    without_scheme = gcs_prefix.removeprefix("gs://")
    bucket_name, _, blob_prefix = without_scheme.partition("/")
    blob_prefix = blob_prefix.rstrip("/")

    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end)

    # Build one GCS prefix per calendar day in [start, end]
    day_prefixes: list[str] = []
    day = start_day
    while day <= end_day:
        day_str = day.isoformat()
        parts = [blob_prefix, f"year={day.year:04d}", f"month={day.month:02d}", f"day={day_str}", ""]
        day_prefixes.append("/".join(p for p in parts if p))
        day += timedelta(days=1)

    gcs_client = gcs_storage.Client()

    # ── Step 1: List only target day directories in parallel ─────────────────
    t_list = time.time()

    def _list_day(prefix: str) -> list[str]:
        return [
            b.name
            for b in gcs_client.list_blobs(bucket_name, prefix=prefix)
            if b.name.endswith(".parquet")
        ]

    all_blob_names: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        for blobs in ex.map(_list_day, day_prefixes):
            all_blob_names.extend(blobs)

    if not all_blob_names:
        return pd.DataFrame()

    print(
        f"[underlyings] {len(all_blob_names):,} files listed in {time.time() - t_list:.1f}s, downloading ...",
        flush=True,
    )

    # ── Step 2: Download all blobs + parse parquet in parallel ───────────────
    t_dl = time.time()
    bkt = gcs_client.bucket(bucket_name)
    _COLS = ["symbol", "date", "open", "high", "low", "close", "volume"]

    def _download(name: str) -> pd.DataFrame | None:
        try:
            data = bkt.blob(name).download_as_bytes(raw_download=True)
            return pd.read_parquet(io.BytesIO(data), columns=_COLS)
        except Exception:
            return None

    # Process in batches to cap peak memory (each batch ~50K files ≈ 50–100 MB)
    BATCH = 50_000
    batch_dfs: list[pd.DataFrame] = []
    for batch_start in range(0, len(all_blob_names), BATCH):
        chunk = all_blob_names[batch_start: batch_start + BATCH]
        chunk_frames: list[pd.DataFrame] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=200) as ex:
            for df in ex.map(_download, chunk):
                if df is not None:
                    chunk_frames.append(df)
        if chunk_frames:
            batch_dfs.append(pd.concat(chunk_frames, ignore_index=True))
        n_done = min(batch_start + BATCH, len(all_blob_names))
        print(
            f"[underlyings] {n_done:,}/{len(all_blob_names):,} files "
            f"({time.time() - t_dl:.0f}s)",
            flush=True,
        )

    print(f"[underlyings] download complete in {time.time() - t_dl:.1f}s", flush=True)
    if not batch_dfs:
        return pd.DataFrame()
    return pd.concat(batch_dfs, ignore_index=True)


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
