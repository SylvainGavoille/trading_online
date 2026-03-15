"""Daily GCP job: price refresh → actions pipeline → options snapshot → ML pipeline.

Execution modes
---------------
full (default)
    1. Refresh today's price history   (download_history.py)
    2. Run actions pipeline            (actions_pipeline.py)
    3. Collect today's options snapshot (collect_options_snapshot.py via Yahoo Finance)
    4. Bootstrap portfolio if missing  (pipeline.py --snapshot)
    5. Run options ML pipeline         (pipeline.py)

refresh_only
    Steps 1-3 only. Writes a completion marker for the pipeline_only job
    to detect (used in split-job Cloud Run mode).

pipeline_only
    Steps 4-5 only. Optionally waits for the refresh_only marker before
    starting model training (--wait_for_refresh flag).

Split-job mode  (split_jobs_enabled=true in Terraform)
------------------------------------------------------
    quantum-daily-ml-refresh   --mode refresh_only
    quantum-daily-ml-pipeline  --mode pipeline_only --wait_for_refresh

Single-job mode (default)
-------------------------
    quantum-daily-ml  --mode full

Idempotency
-----------
Each data step checks for an existing today partition before running.
Re-runs within the same day are always safe.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout_s: int | None = None) -> None:
    print("[run]", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=_PROJECT_ROOT, timeout=timeout_s)


# ---------------------------------------------------------------------------
# Parquet / partition helpers
# ---------------------------------------------------------------------------


def _has_any_parquet(root: Path) -> bool:
    return any(root.rglob("*.parquet"))


def _day_partition_has_parquet(root: Path, day_str: str) -> bool:
    """True when at least one Parquet file exists under day=YYYY-MM-DD partition."""
    try:
        y, m, _d = day_str.split("-")
    except ValueError:
        return False
    day_dir = root / f"year={y}" / f"month={m}" / f"day={day_str}"
    return day_dir.exists() and any(day_dir.rglob("*.parquet"))


def _count_price_days(price_root: Path) -> int:
    """Return the number of distinct day=YYYY-MM-DD partitions in price_historical/."""
    days: set[str] = set()
    for p in price_root.rglob("*.parquet"):
        for part in p.parts:
            if part.startswith("day="):
                days.add(part[4:])
                break
    return len(days)


# ---------------------------------------------------------------------------
# Split-job refresh marker helpers
# ---------------------------------------------------------------------------


def _refresh_marker_path(out_dir: Path, day_str: str) -> Path:
    return out_dir / "_status" / f"refresh_done_{day_str}.json"


def _write_refresh_marker(out_dir: Path, day_str: str) -> Path:
    p = _refresh_marker_path(out_dir, day_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"day": day_str, "status": "ok", "written_at_epoch_s": time.time()}, indent=2),
        encoding="utf-8",
    )
    return p


def _wait_for_refresh_marker(
    out_dir: Path,
    day_str: str,
    timeout_minutes: float,
    poll_seconds: float,
) -> bool:
    deadline = time.time() + timeout_minutes * 60.0
    marker = _refresh_marker_path(out_dir, day_str)
    while time.time() < deadline:
        if marker.exists():
            try:
                raw = json.loads(marker.read_text(encoding="utf-8"))
                if raw.get("status") == "ok" and raw.get("day") == day_str:
                    return True
            except Exception:
                pass
        time.sleep(max(1.0, poll_seconds))
    return False


# ---------------------------------------------------------------------------
# CSV parse helpers
# ---------------------------------------------------------------------------


def _csv_to_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _csv_to_strings(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _fetch_symbol_db_from_gcs(dest: Path) -> bool:
    """Download ibkr_us.sqlite from GCS bucket root if not present locally.

    Looks for gs://<GCS_DATA_URI bucket>/ibkr_us.sqlite.
    Returns True if the file is available after the call.
    """
    if dest.exists():
        return True
    gcs_uri = os.environ.get("GCS_DATA_URI", "").strip().rstrip("/")
    if not gcs_uri:
        return False
    bucket_name = gcs_uri[len("gs://"):].split("/")[0]
    try:
        from google.cloud import storage  # type: ignore
        client = storage.Client()
        blob = client.bucket(bucket_name).blob("ibkr_us.sqlite")
        if not blob.exists(client):
            print("[warn] ibkr_us.sqlite not found in GCS bucket.", flush=True)
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        print(f"[info] Downloaded ibkr_us.sqlite from gs://{bucket_name}/ibkr_us.sqlite", flush=True)
        return True
    except Exception as exc:
        print(f"[warn] Failed to fetch ibkr_us.sqlite from GCS: {exc}", flush=True)
        return False


def _step_price_refresh(args: argparse.Namespace, price_root: Path, run_day: str, horizons: list[int]) -> None:
    """Ensure today's OHLCV bars are present in price_historical/.

    Resolves the symbol universe from ibkr_us.sqlite (price data only — no
    live IBKR connection needed, the file ships in the Docker image or on GCS).

    Two-phase download:
    1. Daily refresh (--days N): fast, fills recent gaps.
    2. Bootstrap backfill (--days 365): runs once when day coverage is below
       the minimum needed for model training.

    Set SKIP_PRICE_REFRESH=true to skip both phases (e.g. when Yahoo Finance
    rate-limits the Cloud Run IP and all downloads return empty).
    """
    if os.environ.get("SKIP_PRICE_REFRESH", "").lower() in ("1", "true", "yes"):
        print("[info] SKIP_PRICE_REFRESH=true — skipping price download.", flush=True)
        return

    db_env_raw = os.environ.get("IBKR_SQLITE_PATH", "").strip()
    db_env = Path(db_env_raw) if db_env_raw else None
    db_default = _PROJECT_ROOT / "ibkr_us.sqlite"

    # Try to fetch from GCS if not present locally
    db_path = db_env if db_env is not None else db_default
    if not db_path.exists():
        _fetch_symbol_db_from_gcs(db_path)

    has_symbol_db = db_path.exists()

    if not has_symbol_db:
        if args.allow_missing_symbol_db:
            print("[warn] ibkr_us.sqlite not found; using existing price_historical data.", flush=True)
            return
        raise FileNotFoundError(
            "ibkr_us.sqlite not found. Provide IBKR_SQLITE_PATH or bake it into the image."
        )

    if _day_partition_has_parquet(price_root, run_day):
        print(f"[info] price_historical already up to date for day={run_day}.", flush=True)
    else:
        _run([
            sys.executable, "src/data/download_history.py",
            "--out", str(price_root),
            "--days", str(args.price_days),
            "--skip-existing",
        ])

    # Bootstrap backfill: triggered once when history is too short for training.
    day_count = _count_price_days(price_root)
    min_needed = max(args.min_train_days + max(horizons), 120)
    if day_count < min_needed:
        print(
            f"[info] price_historical has {day_count} day partitions (need {min_needed}); "
            f"running {args.price_backfill_days}-day backfill.",
            flush=True,
        )
        _run([
            sys.executable, "src/data/download_history.py",
            "--out", str(price_root),
            "--days", str(args.price_backfill_days),
            "--skip-existing",
        ])


def _step_actions_pipeline(
    args: argparse.Namespace,
    price_root: Path,
    out_dir: Path,
    start: date,
    today: date,
    horizons: list[int],
    categories: list[str],
) -> None:
    """Train and rank with the price-only LightGBM model (no options dependency).

    Failure is non-fatal: a warning is logged and execution continues to the
    options collection step.
    """
    try:
        _run(
            [
                sys.executable, "src/ml/actions_pipeline.py",
                "--price_root", str(price_root),
                "--out_dir", str(out_dir / "actions"),
                "--start", start.isoformat(),
                "--end", today.isoformat(),
                "--horizons", *[str(h) for h in horizons],
                "--topk", str(max(args.topk, 5)),
                "--min_train_days", str(args.min_train_days),
                "--test_days", str(args.test_days),
                "--step_days", str(args.step_days),
                "--lgbm_jobs", str(args.actions_lgbm_jobs),
                "--max_symbols", str(args.actions_max_symbols),
                "--max_minutes", str(args.actions_max_minutes),
            ],
            timeout_s=int(args.actions_subprocess_timeout_minutes * 60),
        )
    except Exception as exc:
        print(f"[warn] actions pipeline failed: {exc}", flush=True)


def _step_options_collect(
    args: argparse.Namespace,
    options_root: Path,
    price_root: Path,
    run_day: str,
) -> bool:
    """Collect today's option chain snapshot from Yahoo Finance.

    Returns True when today's partition exists (or was just created).
    Returns False when collection failed, signalling the caller to abort
    the options ML pipeline to avoid training on stale data.
    """
    if _day_partition_has_parquet(options_root, run_day):
        print(f"[info] options_snapshot already present for day={run_day}.", flush=True)
        return True

    try:
        cmd = [
            sys.executable, "src/data/collect_options_snapshot.py",
            "--date", run_day,
            "--price_root", str(price_root),
            "--out_root", str(options_root),
            "--top_n", str(args.options_top_n),
        ]
        if args.options_max_minutes is not None:
            cmd += ["--max_minutes", str(args.options_max_minutes)]
        _run(cmd, timeout_s=int(args.options_subprocess_timeout_minutes * 60))
    except Exception as exc:
        print(f"[warn] options collection failed for {run_day}: {exc}", flush=True)

    ok = _day_partition_has_parquet(options_root, run_day)
    if not ok:
        print(
            f"[warn] options_snapshot has no parquet for day={run_day}; "
            "skipping options ML pipeline to avoid stale training.",
            flush=True,
        )
    return ok


def _step_portfolio_bootstrap(portfolio_root: Path) -> bool:
    """Bootstrap portfolio_daily/ if empty by running pipeline.py --snapshot.

    Returns True when portfolio data is available (existing or just created).
    Returns False when bootstrap failed, signalling the caller to abort.
    """
    if _has_any_parquet(portfolio_root):
        return True

    print(f"[info] portfolio_daily/ is empty; running portfolio snapshot.", flush=True)
    try:
        _run([
            sys.executable, "src/ml/pipeline.py",
            "--snapshot",
            "--portfolio_root", str(portfolio_root),
        ])
    except Exception as exc:
        print(f"[warn] portfolio snapshot failed: {exc}", flush=True)

    if not _has_any_parquet(portfolio_root):
        print("[warn] portfolio_daily/ still empty after snapshot; skipping pipeline.", flush=True)
        return False
    return True


def _step_ml_pipeline(
    args: argparse.Namespace,
    price_root: Path,
    options_root: Path,
    portfolio_root: Path,
    out_dir: Path,
    start: date,
    today: date,
    pipeline_horizons: list[int],
    pipeline_categories: list[str],
) -> None:
    """Run the full options ML pipeline (walk-forward backtest + ranker)."""
    _run(
        [
            sys.executable, "src/ml/pipeline.py",
            "--price_root", str(price_root),
            "--options_root", str(options_root),
            "--portfolio_root", str(portfolio_root),
            "--out_dir", str(out_dir),
            "--start", start.isoformat(),
            "--end", today.isoformat(),
            "--horizons", *[str(h) for h in pipeline_horizons],
            "--categories", *pipeline_categories,
            "--topk", str(args.topk),
            "--min_train_days", str(args.min_train_days),
            "--test_days", str(args.test_days),
            "--step_days", str(args.step_days),
            "--lgbm_jobs", str(args.pipeline_lgbm_jobs),
            "--max_minutes", str(args.pipeline_max_minutes),
        ],
        timeout_s=int(args.pipeline_subprocess_timeout_minutes * 60),
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Daily ML pipeline runner for Cloud Run Job")

    # Data roots (required — injected by Terraform)
    ap.add_argument("--price_root", required=True)
    ap.add_argument("--options_root", required=True)
    ap.add_argument("--portfolio_root", required=True)
    ap.add_argument("--out_dir", required=True)

    # Execution mode
    ap.add_argument(
        "--mode",
        choices=["full", "refresh_only", "pipeline_only"],
        default="full",
        help="full=all steps; refresh_only=steps 1-3; pipeline_only=steps 4-5.",
    )
    ap.add_argument("--allow_missing_symbol_db", action="store_true")

    # Price refresh
    ap.add_argument("--price_days", type=int, default=7,
                    help="Days of price history to refresh daily.")
    ap.add_argument("--price_backfill_days", type=int, default=365,
                    help="Backfill range (days) on first run when history is too short.")
    ap.add_argument("--lookback_days", type=int, default=365,
                    help="Training window (calendar days from today) passed to both pipelines.")

    # Walk-forward parameters (shared by actions + options pipelines)
    ap.add_argument("--min_train_days", type=int, default=80)
    ap.add_argument("--test_days", type=int, default=20)
    ap.add_argument("--step_days", type=int, default=20)
    ap.add_argument("--topk", type=int, default=3)

    # Actions pipeline (price-only model)
    ap.add_argument("--horizons", default="2,5,10,21",
                    help="Forward-return horizons for actions_pipeline (CSV of days).")
    ap.add_argument("--categories", default="long_premium,short_premium",
                    help="Strategy categories for actions_pipeline (CSV).")
    ap.add_argument("--actions_lgbm_jobs", type=int, default=1)
    ap.add_argument("--actions_max_symbols", type=int, default=1500)
    ap.add_argument("--actions_max_minutes", type=float, default=55.0)
    ap.add_argument("--actions_subprocess_timeout_minutes", type=float, default=65.0)

    # Options snapshot collection (Yahoo Finance)
    ap.add_argument("--options_top_n", type=int, default=30,
                    help="Top-N symbols by volume to collect options for.")
    ap.add_argument("--options_max_minutes", type=float, default=30.0,
                    help="Soft time cap for options collection.")
    ap.add_argument("--options_subprocess_timeout_minutes", type=float, default=45.0,
                    help="Hard subprocess timeout for options collection.")

    # Options ML pipeline (options ranker model)
    ap.add_argument("--pipeline_horizons", default="5,10",
                    help="Forward-return horizons for options pipeline (CSV of days).")
    ap.add_argument("--pipeline_categories", default="long_premium",
                    help="Strategy categories for options pipeline (CSV).")
    ap.add_argument("--pipeline_lgbm_jobs", type=int, default=1)
    ap.add_argument("--pipeline_max_minutes", type=float, default=45.0)
    ap.add_argument("--pipeline_subprocess_timeout_minutes", type=float, default=60.0)

    # Split-job sync (pipeline_only mode)
    ap.add_argument("--wait_for_refresh", action="store_true",
                    help="Wait for refresh marker before starting (pipeline_only mode).")
    ap.add_argument("--refresh_wait_timeout_minutes", type=float, default=120.0)
    ap.add_argument("--refresh_wait_poll_seconds", type=float, default=30.0)

    return ap


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = _build_parser().parse_args()

    price_root = Path(args.price_root)
    options_root = Path(args.options_root)
    portfolio_root = Path(args.portfolio_root)
    out_dir = Path(args.out_dir)

    for d in (price_root, options_root, portfolio_root, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    today = date.today()
    run_day = today.isoformat()
    start = today - timedelta(days=args.lookback_days)
    horizons = _csv_to_ints(args.horizons)
    categories = _csv_to_strings(args.categories)
    pipeline_horizons = _csv_to_ints(args.pipeline_horizons)
    pipeline_categories = _csv_to_strings(args.pipeline_categories)

    # ------------------------------------------------------------------
    # Refresh path (modes: full, refresh_only)
    # ------------------------------------------------------------------
    if args.mode != "pipeline_only":
        _step_price_refresh(args, price_root, run_day, horizons)

        if not _has_any_parquet(price_root):
            print("[warn] No price data after refresh; skipping pipeline.", flush=True)
            return

        _step_actions_pipeline(args, price_root, out_dir, start, today, horizons, categories)

        if not _step_options_collect(args, options_root, price_root, run_day):
            return

        if args.mode == "refresh_only":
            marker = _write_refresh_marker(out_dir, run_day)
            print(f"[done] Refresh-only mode completed. marker={marker}", flush=True)
            return

    # ------------------------------------------------------------------
    # Pipeline-only wait (split-job mode)
    # ------------------------------------------------------------------
    if args.mode == "pipeline_only" and args.wait_for_refresh:
        print(
            f"[wait] Waiting for refresh marker day={run_day} "
            f"(timeout={args.refresh_wait_timeout_minutes:.0f}m)...",
            flush=True,
        )
        if not _wait_for_refresh_marker(out_dir, run_day, args.refresh_wait_timeout_minutes, args.refresh_wait_poll_seconds):
            raise TimeoutError(
                f"Refresh marker for day={run_day} not found within "
                f"{args.refresh_wait_timeout_minutes:.0f} minutes."
            )
        print(f"[wait] Refresh marker detected for day={run_day}.", flush=True)

    # ------------------------------------------------------------------
    # Guards before ML training
    # ------------------------------------------------------------------
    if not _has_any_parquet(price_root):
        print("[warn] No price data; skipping pipeline.", flush=True)
        return

    if not _has_any_parquet(options_root):
        print("[warn] No options data; skipping pipeline.", flush=True)
        return

    if not _step_portfolio_bootstrap(portfolio_root):
        return

    # ------------------------------------------------------------------
    # Options ML pipeline
    # ------------------------------------------------------------------
    _step_ml_pipeline(
        args, price_root, options_root, portfolio_root, out_dir,
        start, today, pipeline_horizons, pipeline_categories,
    )

    print("[done] Daily ML refresh completed.", flush=True)


if __name__ == "__main__":
    main()
