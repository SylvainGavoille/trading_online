"""Shared helpers and default path constants."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    import duckdb as _duckdb  # used by duckdb_scan signature

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# src/ml/utils.py → parents[0]=src/ml  parents[1]=src  parents[2]=project_root
PROJECT_ROOT          = Path(__file__).resolve().parents[2]
PRICE_HISTORICAL_ROOT = PROJECT_ROOT / "price_historical"
OPTIONS_SNAPSHOT_ROOT = PROJECT_ROOT / "options_snapshot"
PORTFOLIO_DAILY_ROOT  = PROJECT_ROOT / "portfolio_daily"


# ---------------------------------------------------------------------------
# GCS / DuckDB helpers
# ---------------------------------------------------------------------------


def gcs_data_uri() -> str:
    """Return GCS_DATA_URI env var (e.g. 'gs://quantum-ml-bucket'), or ''."""
    return os.environ.get("GCS_DATA_URI", "").strip().rstrip("/")


def gcs_mount_path() -> str:
    """Return GCS_MOUNT_PATH env var (GCSFuse mount root, e.g. '/mnt/quantum'), or ''."""
    return os.environ.get("GCS_MOUNT_PATH", "").strip().rstrip("/")


def fs_path_to_gcs_uri(path: str | Path) -> str | None:
    """
    Convert a GCSFuse filesystem path to a gs:// URI.

    Requires both GCS_DATA_URI and GCS_MOUNT_PATH to be set.
    Returns None if the conversion is not possible.

    Example:
        /mnt/quantum/price_historical/year=2025/month=01/day=2025-01-01/*.parquet
        → gs://quantum-ml-bucket/price_historical/year=2025/month=01/day=2025-01-01/*.parquet
    """
    gcs_uri = gcs_data_uri()
    mount = gcs_mount_path()
    if not gcs_uri or not mount:
        return None
    path_str = str(path)
    if not path_str.startswith(mount):
        return None
    rel = path_str[len(mount):].lstrip("/")
    return f"{gcs_uri}/{rel}"


# ---------------------------------------------------------------------------
# DuckDB resilient scan
# ---------------------------------------------------------------------------

_TOO_SMALL_RE = re.compile(r"File '([^']+)' too small to be a Parquet file")


def duckdb_scan(con: "_duckdb.DuckDBPyConnection", sql: str, max_retries: int = 50) -> pd.DataFrame:
    """
    Execute a DuckDB SQL statement that contains a read_parquet(glob) call.

    If any file is reported as 'too small to be a Parquet file' (a corrupt /
    empty file left by a failed download), it is deleted and the query is
    retried automatically.  Repeats up to max_retries times so the entire
    store is self-healing on first scan.
    """
    for _ in range(max_retries):
        try:
            return con.execute(sql).df()
        except Exception as exc:
            m = _TOO_SMALL_RE.search(str(exc))
            if m:
                bad = Path(m.group(1))
                bad.unlink(missing_ok=True)
                print(f"[data] Removed corrupt parquet: {bad.parent.name}/{bad.name}")
                continue
            raise
    raise RuntimeError(f"Exceeded {max_retries} corrupt-file retries on query.")


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date(s: str) -> pd.Timestamp:
    return pd.to_datetime(s, format="%Y-%m-%d", errors="raise")


def date_str(d) -> str:
    return pd.to_datetime(d).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# File system
# ---------------------------------------------------------------------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Financial math
# ---------------------------------------------------------------------------

def mid_price(df: pd.DataFrame) -> pd.Series:
    """(bid+ask)/2 ; falls back to last ; then NaN."""
    bid = df.get("bid")
    ask = df.get("ask")
    if bid is not None and ask is not None:
        return (bid.astype(float) + ask.astype(float)) / 2.0
    last = df.get("last")
    if last is not None:
        return last.astype(float)
    return pd.Series(np.nan, index=df.index)


def safe_log1p(x: pd.Series) -> pd.Series:
    return np.log1p(np.maximum(x.astype(float), 0.0))


def winsorize(s: pd.Series, p_low: float = 0.01, p_high: float = 0.99) -> pd.Series:
    lo = s.quantile(p_low)
    hi = s.quantile(p_high)
    return s.clip(lo, hi)
