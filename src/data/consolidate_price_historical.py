"""
One-shot migration: merge per-symbol parquet files into a single part-0.parquet
per day directory inside price_historical/.

Before (slow):
    price_historical/year=2025/month=02/day=2025-02-20/AAPL.parquet
    price_historical/year=2025/month=02/day=2025-02-20/MSFT.parquet
    ...  (8 026 files per trading day)

After (fast):
    price_historical/year=2025/month=02/day=2025-02-20/part-0.parquet
    (one file containing all symbols, DuckDB partition-prunes instantly)

Usage
-----
    # Dry-run: show what would happen (fast — no data reads)
    uv run python src/data/consolidate_price_historical.py --dry_run

    # Migrate, keep original per-symbol files (safe first pass)
    uv run python src/data/consolidate_price_historical.py

    # Migrate and delete originals
    uv run python src/data/consolidate_price_historical.py --delete_originals

    # Re-consolidate days that already have part-0.parquet
    uv run python src/data/consolidate_price_historical.py --force --delete_originals
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd


# project root is 2 levels up from this file (src/data/ -> src/ -> project root)
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "price_historical"

_SCHEMA = ["symbol", "date", "open", "high", "low", "close", "volume"]


def _day_dirs(root: Path):
    """Yield all leaf day directories (year=*/month=*/day=*/)."""
    for year_dir in sorted(root.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            for day_dir in sorted(month_dir.glob("day=*")):
                if day_dir.is_dir():
                    yield day_dir


def consolidate(
    root: Path,
    dry_run: bool = False,
    delete_originals: bool = False,
    force: bool = False,
) -> None:
    root = root.resolve()
    if not root.exists():
        print(f"[consolidate] Root not found: {root}")
        sys.exit(1)

    day_dirs = list(_day_dirs(root))
    if not day_dirs:
        print("[consolidate] No day directories found -- nothing to do.")
        return

    total = len(day_dirs)
    skipped = consolidated = deleted_count = 0

    # DuckDB connection reused across days (only needed when not dry-run)
    con = duckdb.connect(":memory:") if not dry_run else None

    for i, day_dir in enumerate(day_dirs, 1):
        part0 = day_dir / "part-0.parquet"

        # Collect per-symbol files (anything *.parquet that is NOT part-0.parquet)
        symbol_files = [
            f for f in day_dir.glob("*.parquet") if f.name != "part-0.parquet"
        ]

        already_consolidated = part0.exists()

        if already_consolidated and not force:
            # Already done; optionally still delete originals if requested
            if delete_originals and symbol_files:
                if not dry_run:
                    for f in symbol_files:
                        f.unlink()
                        deleted_count += 1
                else:
                    deleted_count += len(symbol_files)
                print(
                    f"[{i}/{total}] {day_dir.name}: already consolidated, "
                    f"{'would delete' if dry_run else 'deleted'} "
                    f"{len(symbol_files)} originals"
                )
            skipped += 1
            continue

        if not symbol_files:
            print(f"[{i}/{total}] {day_dir.name}: empty (no parquet files) -- skip")
            skipped += 1
            continue

        # --- DRY RUN: just report file count, no reads ---
        if dry_run:
            action = "would delete originals" if delete_originals else "would keep originals"
            print(
                f"[{i}/{total}] {day_dir.name}: "
                f"{len(symbol_files)} files -> part-0.parquet  ({action}) [DRY RUN]"
            )
            consolidated += 1
            if delete_originals:
                deleted_count += len(symbol_files)
            continue

        # --- REAL RUN: read all symbol files with DuckDB ---
        # Pass the file list as a bound parameter rather than interpolating the
        # paths into the SQL string (avoids SQL injection via odd file names).
        file_list = [str(f).replace(chr(92), "/") for f in symbol_files]
        sql = "SELECT * FROM read_parquet(?)"

        try:
            df: pd.DataFrame = con.execute(sql, [file_list]).df()
        except Exception as exc:
            print(f"[{i}/{total}] {day_dir.name}: ERROR reading files -- {exc}")
            skipped += 1
            continue

        if df.empty:
            print(f"[{i}/{total}] {day_dir.name}: all files empty -- skip")
            skipped += 1
            continue

        # Normalise to expected schema
        cols = [c for c in _SCHEMA if c in df.columns]
        df = df[cols]

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        for num_col in ("open", "high", "low", "close", "volume"):
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

        n_symbols = df["symbol"].nunique() if "symbol" in df.columns else "?"
        print(
            f"[{i}/{total}] {day_dir.name}: "
            f"{len(symbol_files)} files -> {len(df):,} rows, {n_symbols} symbols"
        )

        df.to_parquet(part0, index=False, compression="snappy")
        consolidated += 1

        if delete_originals:
            # Verify the consolidated output is consistent with the inputs
            # before destroying the originals.  Each per-symbol file holds one
            # symbol, so the distinct symbol count must match the file count.
            distinct_symbols = (
                df["symbol"].nunique() if "symbol" in df.columns else 0
            )
            if distinct_symbols == len(symbol_files):
                for f in symbol_files:
                    f.unlink()
                    deleted_count += 1
            else:
                print(
                    f"[{i}/{total}] {day_dir.name}: WARNING — consolidated "
                    f"{distinct_symbols} distinct symbols but had "
                    f"{len(symbol_files)} input files; keeping originals."
                )

    tag = "  [DRY RUN -- no files written]" if dry_run else ""
    print(
        f"\n[consolidate] Done. "
        f"consolidated={consolidated}  skipped={skipped}  "
        f"deleted_originals={deleted_count}{tag}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolidate per-symbol parquet files into one part-0.parquet per day."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_DEFAULT_ROOT,
        help=f"Root of the price_historical store (default: {_DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Show what would happen without writing or deleting anything.",
    )
    parser.add_argument(
        "--delete_originals",
        action="store_true",
        help="Delete per-symbol files after writing part-0.parquet.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-consolidate day directories that already have part-0.parquet.",
    )
    args = parser.parse_args()

    consolidate(
        root=args.root,
        dry_run=args.dry_run,
        delete_originals=args.delete_originals,
        force=args.force,
    )


if __name__ == "__main__":
    main()
