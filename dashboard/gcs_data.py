"""
Shared helpers for reading ML data from the GCS bucket (quantum-ml-bucket).

Set GCS_DATA_URI=gs://quantum-ml-bucket in .env to enable GCS fallback.
Uses Application Default Credentials (ADC) — works inside Cloud Run and
locally when `gcloud auth application-default login` has been run.
"""

from __future__ import annotations

import os
import re
from io import BytesIO
from typing import Optional

import pandas as pd


def get_gcs_data_uri() -> str:
    """Return the GCS_DATA_URI env var (e.g. 'gs://quantum-ml-bucket'), or ''."""
    return os.getenv("GCS_DATA_URI", "").strip().rstrip("/")


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    """Return (bucket_name, blob_prefix) from a gs://... URI."""
    without_scheme = uri[len("gs://"):]
    if "/" in without_scheme:
        bucket, prefix = without_scheme.split("/", 1)
        return bucket, prefix
    return without_scheme, ""


def _gcs_client():
    from google.cloud import storage  # type: ignore
    return storage.Client()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def gcs_download_blob(bucket_name: str, blob_name: str) -> Optional[bytes]:
    """Download a single GCS blob and return its bytes, or None on error."""
    try:
        client = _gcs_client()
        blob = client.bucket(bucket_name).blob(blob_name)
        if not blob.exists(client):
            return None
        return blob.download_as_bytes()
    except Exception:
        return None


def gcs_list_blobs(bucket_name: str, prefix: str) -> list[str]:
    """List all blob names under *prefix* in *bucket_name*."""
    try:
        client = _gcs_client()
        return [b.name for b in client.list_blobs(bucket_name, prefix=prefix)]
    except Exception:
        return []


def gcs_read_parquet(bucket_name: str, blob_name: str) -> Optional[pd.DataFrame]:
    """Download a parquet blob and return a DataFrame, or None."""
    data = gcs_download_blob(bucket_name, blob_name)
    if data is None:
        return None
    try:
        return pd.read_parquet(BytesIO(data))
    except Exception:
        return None


def gcs_read_all_parquets(bucket_name: str, prefix: str) -> Optional[pd.DataFrame]:
    """
    Download every *.parquet blob under *prefix* and concatenate into a
    single DataFrame.  Returns None if nothing was found.
    """
    blobs = [b for b in gcs_list_blobs(bucket_name, prefix) if b.endswith(".parquet")]
    if not blobs:
        return None

    client = _gcs_client()
    frames: list[pd.DataFrame] = []
    for blob_name in blobs:
        try:
            data = client.bucket(bucket_name).blob(blob_name).download_as_bytes()
            frames.append(pd.read_parquet(BytesIO(data)))
        except Exception:
            continue

    return pd.concat(frames, ignore_index=True) if frames else None


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------


def read_portfolio_history_from_gcs() -> Optional[pd.DataFrame]:
    """
    Read all portfolio_daily/ parquet files from the GCS bucket and return
    a DataFrame sorted by date, or None.
    """
    root_uri = get_gcs_data_uri()
    if not root_uri:
        return None
    bucket, root_prefix = _parse_gs_uri(root_uri)
    prefix = f"{root_prefix}/portfolio_daily/".lstrip("/") if root_prefix else "portfolio_daily/"

    df = gcs_read_all_parquets(bucket, prefix)
    if df is None or df.empty:
        return None
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df


def read_options_coverage_from_gcs() -> Optional[pd.DataFrame]:
    """
    Return a DataFrame with (day, n_rows) by listing options_snapshot/ blobs
    in GCS and extracting the Hive day= partition from each path.
    Avoids downloading file contents — counts blobs per partition instead.
    """
    root_uri = get_gcs_data_uri()
    if not root_uri:
        return None
    bucket, root_prefix = _parse_gs_uri(root_uri)
    prefix = f"{root_prefix}/options_snapshot/".lstrip("/") if root_prefix else "options_snapshot/"

    blobs = [b for b in gcs_list_blobs(bucket, prefix) if b.endswith(".parquet")]
    if not blobs:
        return None

    day_pattern = re.compile(r"day=(\d{4}-\d{2}-\d{2})")
    counts: dict[str, int] = {}
    for blob_name in blobs:
        m = day_pattern.search(blob_name)
        if m:
            day = m.group(1)
            counts[day] = counts.get(day, 0) + 1

    if not counts:
        return None

    df = pd.DataFrame(
        sorted(counts.items(), key=lambda x: x[0]),
        columns=["day", "n_rows"],
    )
    return df


# ---------------------------------------------------------------------------
# ML output helpers  (reads from ML_RESULTS_GCS_URI = gs://bucket/ml_output)
# ---------------------------------------------------------------------------


def _ml_bucket_prefix() -> tuple[str, str] | None:
    """Return (bucket, ml_output_prefix) from ML_RESULTS_GCS_URI.

    Falls back to GCS_DATA_URI + /ml_output when ML_RESULTS_GCS_URI is not set,
    so only one env var (GCS_DATA_URI) is strictly required.
    """
    uri = os.getenv("ML_RESULTS_GCS_URI", "").strip().rstrip("/")
    if not uri:
        root = get_gcs_data_uri()
        if not root:
            return None
        uri = f"{root}/ml_output"
    return _parse_gs_uri(uri)


def gcs_read_json(bucket_name: str, blob_name: str) -> Optional[dict]:
    """Download a JSON blob and return as dict, or None."""
    import json
    data = gcs_download_blob(bucket_name, blob_name)
    if data is None:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def read_ml_parquet(relative_path: str) -> Optional[pd.DataFrame]:
    """Read a parquet file at *relative_path* under ML_RESULTS_GCS_URI."""
    bp = _ml_bucket_prefix()
    if bp is None:
        return None
    bucket, prefix = bp
    blob = f"{prefix}/{relative_path}".lstrip("/")
    return gcs_read_parquet(bucket, blob)


def read_ml_json(relative_path: str) -> Optional[dict]:
    """Read a JSON file at *relative_path* under ML_RESULTS_GCS_URI."""
    bp = _ml_bucket_prefix()
    if bp is None:
        return None
    bucket, prefix = bp
    blob = f"{prefix}/{relative_path}".lstrip("/")
    return gcs_read_json(bucket, blob)


def read_ml_run_status() -> Optional[dict]:
    """Read ml_output/run_status.json from GCS."""
    return read_ml_json("run_status.json")


def read_ml_summary_metrics() -> Optional[pd.DataFrame]:
    """Read ml_output/summary_metrics.parquet (options pipeline)."""
    return read_ml_parquet("summary_metrics.parquet")


def read_ml_equity_curves(category: str, horizon: int) -> Optional[pd.DataFrame]:
    """Read ml_output/backtests/category={cat}/h={h}/fold_equity.parquet."""
    return read_ml_parquet(f"backtests/category={category}/h={horizon}/fold_equity.parquet")


def read_ml_actions_summary() -> Optional[pd.DataFrame]:
    """Read ml_output/actions/summary.parquet (price-only actions pipeline)."""
    return read_ml_parquet("actions/summary.parquet")


def read_ml_actions_equity(horizon: int) -> Optional[pd.DataFrame]:
    """Read ml_output/actions/backtests/h={h}/fold_equity.parquet."""
    return read_ml_parquet(f"actions/backtests/h={horizon}/fold_equity.parquet")


def read_latest_recommendations() -> Optional[pd.DataFrame]:
    """
    Return the most recent recommendations across all horizons.

    Looks in ml_output/actions/recommendations/ for files named
    {run_date}_h{horizon}.parquet, picks the latest run_date, and
    concatenates all horizon files for that date.
    """
    bp = _ml_bucket_prefix()
    if bp is None:
        return None
    bucket, prefix = bp
    rec_prefix = f"{prefix}/actions/recommendations/".lstrip("/")

    blobs = [b for b in gcs_list_blobs(bucket, rec_prefix) if b.endswith(".parquet")]
    if not blobs:
        return None

    # Extract run dates from filenames like "2025-03-15_h5.parquet"
    import re
    date_pat = re.compile(r"(\d{4}-\d{2}-\d{2})_h\d+\.parquet$")
    dates = {m.group(1) for b in blobs if (m := date_pat.search(b))}
    if not dates:
        return None

    latest_date = max(dates)
    frames: list[pd.DataFrame] = []
    for blob_name in blobs:
        if latest_date in blob_name:
            df = gcs_read_parquet(bucket, blob_name)
            if df is not None and not df.empty:
                frames.append(df)

    if not frames:
        return None

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["horizon", "rank"]).reset_index(drop=True)
    return result


def gcs_bucket_stats() -> dict:
    """
    Return a quick overview of the GCS bucket contents.

    Makes three list_blobs calls (price_historical, options_snapshot,
    portfolio_daily) and one for ml_output, then counts days/files.

    Returns a dict with keys:
      price_days, price_files,
      options_days, options_files,
      portfolio_files,
      ml_summary_exists, ml_run_status (dict or None),
      gcs_data_uri, ml_results_uri
    """
    root_uri = get_gcs_data_uri()
    bp = _ml_bucket_prefix()
    ml_uri = f"gs://{bp[0]}/{bp[1]}" if bp else ""

    result: dict = {
        "gcs_data_uri": root_uri,
        "ml_results_uri": ml_uri,
        "price_days": 0,
        "price_files": 0,
        "options_days": 0,
        "options_files": 0,
        "portfolio_files": 0,
        "ml_summary_exists": False,
        "ml_run_status": None,
    }

    if not root_uri:
        return result

    bucket, root_prefix = _parse_gs_uri(root_uri)
    day_re = re.compile(r"day=(\d{4}-\d{2}-\d{2})")

    # price_historical
    price_prefix = f"{root_prefix}/price_historical/".lstrip("/") if root_prefix else "price_historical/"
    price_blobs = [b for b in gcs_list_blobs(bucket, price_prefix) if b.endswith(".parquet")]
    result["price_files"] = len(price_blobs)
    result["price_days"] = len({m.group(1) for b in price_blobs if (m := day_re.search(b))})

    # options_snapshot
    opt_prefix = f"{root_prefix}/options_snapshot/".lstrip("/") if root_prefix else "options_snapshot/"
    opt_blobs = [b for b in gcs_list_blobs(bucket, opt_prefix) if b.endswith(".parquet")]
    result["options_files"] = len(opt_blobs)
    result["options_days"] = len({m.group(1) for b in opt_blobs if (m := day_re.search(b))})

    # portfolio_daily
    port_prefix = f"{root_prefix}/portfolio_daily/".lstrip("/") if root_prefix else "portfolio_daily/"
    result["portfolio_files"] = len(
        [b for b in gcs_list_blobs(bucket, port_prefix) if b.endswith(".parquet")]
    )

    # ml_output
    if bp:
        ml_bucket, ml_prefix = bp
        summary_blob = f"{ml_prefix}/summary_metrics.parquet".lstrip("/")
        result["ml_summary_exists"] = bool(gcs_download_blob(ml_bucket, summary_blob) is not None)
        result["ml_run_status"] = read_ml_run_status()

    return result


def list_price_symbols_from_gcs(max_lookback_days: int = 7) -> set:
    """Return the set of symbols available in price_historical/ for the most recent day."""
    import datetime
    root_uri = get_gcs_data_uri()
    if not root_uri:
        return set()
    bucket, root_prefix = _parse_gs_uri(root_uri)
    base = f"{root_prefix}/price_historical".lstrip("/") if root_prefix else "price_historical"

    today = datetime.date.today()
    for offset in range(max_lookback_days):
        day = today - datetime.timedelta(days=offset + 1)
        prefix = f"{base}/year={day.year}/month={day.month:02d}/day={day.isoformat()}/"
        blobs = gcs_list_blobs(bucket, prefix)
        symbols = {b.rsplit("/", 1)[-1][:-8] for b in blobs if b.endswith(".parquet")}
        if symbols:
            return symbols
    return set()


def read_price_history_from_gcs(
    symbol: str,
    start_date,
    end_date,
) -> Optional[pd.DataFrame]:
    """
    Download price_historical parquet files for *symbol* in [start_date, end_date]
    from GCS.  Dates can be datetime.date or anything pd.to_datetime accepts.
    Returns a DataFrame with columns Open/High/Low/Close/Volume indexed by Date,
    or None if nothing was found.
    """
    root_uri = get_gcs_data_uri()
    if not root_uri:
        return None
    bucket, root_prefix = _parse_gs_uri(root_uri)
    base = f"{root_prefix}/price_historical".lstrip("/") if root_prefix else "price_historical"

    import datetime

    if not isinstance(start_date, datetime.date):
        start_date = pd.to_datetime(start_date).date()
    if not isinstance(end_date, datetime.date):
        end_date = pd.to_datetime(end_date).date()

    frames: list[pd.DataFrame] = []
    day = start_date
    while day <= end_date:
        blob_name = (
            f"{base}/year={day.year}/month={day.month:02d}"
            f"/day={day.isoformat()}/{symbol}.parquet"
        )
        df = gcs_read_parquet(bucket, blob_name)
        if df is not None and not df.empty:
            frames.append(df)
        day += datetime.timedelta(days=1)

    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    df.index.name = "Date"
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    return df[cols]
