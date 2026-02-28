"""Daily GCP job entrypoint for data refresh + ML pipeline run."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> None:
    print("[run]", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=_PROJECT_ROOT)


def _csv_to_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _csv_to_strings(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _has_any_parquet(root: Path) -> bool:
    return any(root.rglob("*.parquet"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Daily ML pipeline runner for Cloud Run Job")
    ap.add_argument("--price_root", required=True)
    ap.add_argument("--options_root", required=True)
    ap.add_argument("--portfolio_root", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--price_days", type=int, default=7)
    ap.add_argument("--lookback_days", type=int, default=365)
    ap.add_argument("--horizons", default="2,5,10,21")
    ap.add_argument("--categories", default="long_premium,short_premium")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--min_train_days", type=int, default=80)
    ap.add_argument("--test_days", type=int, default=20)
    ap.add_argument("--step_days", type=int, default=20)
    ap.add_argument("--allow_missing_symbol_db", action="store_true")
    args = ap.parse_args()

    price_root = Path(args.price_root)
    options_root = Path(args.options_root)
    portfolio_root = Path(args.portfolio_root)
    out_dir = Path(args.out_dir)

    price_root.mkdir(parents=True, exist_ok=True)
    options_root.mkdir(parents=True, exist_ok=True)
    portfolio_root.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    start = today - timedelta(days=args.lookback_days)
    horizons = _csv_to_ints(args.horizons)
    categories = _csv_to_strings(args.categories)

    # Refresh recent historical prices used by the feature pipeline.
    # download_history.py requires ibkr_us.sqlite to determine the symbol universe.
    db_env_raw = os.environ.get("IBKR_SQLITE_PATH", "").strip()
    db_env = Path(db_env_raw) if db_env_raw else None
    db_default = _PROJECT_ROOT / "ibkr_us.sqlite"
    has_symbol_db = (db_env.exists() if db_env is not None else False) or db_default.exists()
    if has_symbol_db:
        _run(
            [
                sys.executable,
                "src/data/download_history.py",
                "--out",
                str(price_root),
                "--days",
                str(args.price_days),
                "--skip-existing",
            ]
        )
    elif args.allow_missing_symbol_db:
        print(
            "[warn] ibkr_us.sqlite not found; skipping price refresh and using existing price_historical data.",
            flush=True,
        )
    else:
        raise FileNotFoundError(
            "ibkr_us.sqlite not found. Provide IBKR_SQLITE_PATH or include the DB in the image."
        )

    # Skip pipeline when required datasets are still empty. This keeps scheduled
    # Cloud Run executions healthy while upstream collectors bootstrap data.
    if not _has_any_parquet(price_root):
        print(
            f"[warn] No parquet data found in {price_root}; skipping pipeline run.",
            flush=True,
        )
        return

    # Auto-bootstrap options snapshots from IBKR when missing.
    if not _has_any_parquet(options_root):
        print(
            f"[info] No parquet data found in {options_root}; running options snapshot collector.",
            flush=True,
        )
        try:
            _run(
                [
                    sys.executable,
                    "src/data/collect_options_snapshot.py",
                    "--price_root",
                    str(price_root),
                    "--out_root",
                    str(options_root),
                ]
            )
        except Exception as exc:
            print(f"[warn] options snapshot collection failed: {exc}", flush=True)

        if not _has_any_parquet(options_root):
            print(
                f"[warn] No parquet data found in {options_root} after collection; skipping pipeline run.",
                flush=True,
            )
            return

    # Run the pipeline against persisted data roots.
    pipeline_cmd = [
        sys.executable,
        "src/ml/pipeline.py",
        "--price_root",
        str(price_root),
        "--options_root",
        str(options_root),
        "--portfolio_root",
        str(portfolio_root),
        "--out_dir",
        str(out_dir),
        "--start",
        start.isoformat(),
        "--end",
        today.isoformat(),
        "--horizons",
        *[str(h) for h in horizons],
        "--categories",
        *categories,
        "--topk",
        str(args.topk),
        "--min_train_days",
        str(args.min_train_days),
        "--test_days",
        str(args.test_days),
        "--step_days",
        str(args.step_days),
    ]
    _run(pipeline_cmd)

    print("[done] Daily ML refresh completed.", flush=True)


if __name__ == "__main__":
    main()
