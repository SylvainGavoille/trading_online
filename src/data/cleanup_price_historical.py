"""
Fast cleanup of empty / corrupt Parquet files in price_historical/.

os.scandir() on Windows returns file size as part of the directory entry
(FindFirstFile / FindNextFile), so no separate stat() call is needed per file.
This makes the sweep much faster than pathlib.rglob on large stores.

Usage
-----
uv run python src/data/cleanup_price_historical.py
uv run python src/data/cleanup_price_historical.py --dry_run
uv run python src/data/cleanup_price_historical.py --min_bytes 1000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _iter_parquet(root: str):
    """Yield DirEntry objects for every *.parquet file under root (recursive)."""
    try:
        with os.scandir(root) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    yield from _iter_parquet(entry.path)
                elif entry.name.endswith(".parquet"):
                    yield entry
    except PermissionError:
        pass


def cleanup_empty_parquets(
    root: Path,
    min_bytes: int = 500,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[int, int]:
    """
    Walk *root* and delete any *.parquet file smaller than *min_bytes*.

    Returns (n_deleted, n_total).
    """
    n_total = 0
    n_deleted = 0

    for entry in _iter_parquet(str(root)):
        n_total += 1
        try:
            size = entry.stat(follow_symlinks=False).st_size
        except OSError:
            continue

        if size < min_bytes:
            n_deleted += 1
            if verbose:
                print(f"  {'[dry]' if dry_run else '[del]'} {entry.path}  ({size}B)")
            if not dry_run:
                try:
                    os.unlink(entry.path)
                except OSError as exc:
                    print(f"  [warn] Could not delete {entry.path}: {exc}")
                    n_deleted -= 1

    return n_deleted, n_total


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Remove empty/corrupt Parquet files from price_historical/"
    )
    ap.add_argument(
        "--root",
        default=str(_PROJECT_ROOT / "price_historical"),
        help="Directory to clean (default: price_historical/)",
    )
    ap.add_argument(
        "--min_bytes",
        type=int,
        default=500,
        help="Files strictly below this size are deleted (default: 500)",
    )
    ap.add_argument(
        "--dry_run",
        action="store_true",
        help="Print what would be deleted without actually deleting",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Print each deleted file",
    )
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"[cleanup] Directory not found: {root}")
        sys.exit(1)

    print(f"[cleanup] Scanning {root} …")
    print(f"          min_bytes={args.min_bytes}  dry_run={args.dry_run}")

    n_del, n_tot = cleanup_empty_parquets(
        root,
        min_bytes=args.min_bytes,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    action = "Would delete" if args.dry_run else "Deleted"
    print(
        f"[cleanup] Done — scanned {n_tot:,} files, {action} {n_del:,} empty/corrupt files."
    )
    if n_del and not args.dry_run:
        print(
            "[cleanup] Re-run DuckDB queries on price_historical/ — they should now work."
        )


if __name__ == "__main__":
    main()
