"""
End-to-end ML pipeline orchestrator.

Usage examples
--------------
# Full walk-forward backtest
uv run python src/ml/pipeline.py \
    --start 2025-02-20 --end 2026-02-23 \
    --horizons 2 5 10 21 \
    --categories long_premium short_premium \
    --topk 3

# Save today's portfolio snapshot from live IBKR (run daily)
uv run python src/ml/pipeline.py --snapshot

# Override default data roots
uv run python src/ml/pipeline.py \
    --price_root /data/price_historical \
    --options_root /data/options_snapshot \
    --portfolio_root /data/portfolio_daily \
    --out_dir /data/out \
    --start 2025-02-20 --end 2026-02-23 \
    --horizons 5 21 --categories long_premium --topk 3
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
from pathlib import Path

import pandas as pd

# Ensure project root is importable regardless of working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.config import BacktestConfig, TrainConfig, load_optimizer_config
from src.ml.utils import (
    ensure_dir,
    date_str,
    PRICE_HISTORICAL_ROOT,
    OPTIONS_SNAPSHOT_ROOT,
    PORTFOLIO_DAILY_ROOT,
)
from src.ml.data.underlyings import read_underlyings
from src.ml.data.options import read_options
from src.ml.data.portfolio import read_portfolio, snapshot_from_ibkr, save_portfolio_snapshot
from src.ml.training import build_training_table, train_ranker, walk_forward_splits
from src.ml.backtest import backtest_ranker


def _get_ib_client():
    """Try to get a connected IBKR client. Returns None if unavailable."""
    try:
        import yaml
        from src.api.ib_connector import IBClient

        cfg_path = _PROJECT_ROOT / "src" / "config" / "config.yaml"
        with open(cfg_path) as f:
            config = yaml.safe_load(f)
        client = IBClient(config)
        if client.connect_and_run():
            return client
    except Exception as exc:
        print(f"[IBKR] Connection not available: {exc}")
    return None


def cmd_snapshot(portfolio_root: Path) -> None:
    """Save today's portfolio snapshot from live IBKR."""
    print("[snapshot] Connecting to IBKR...")
    ib = _get_ib_client()
    if ib is None:
        print("[snapshot] IBKR not available. Is TWS/Gateway running?")
        sys.exit(1)
    snap = snapshot_from_ibkr(ib)
    path = save_portfolio_snapshot(snap, portfolio_root)
    print(f"[snapshot] Saved -> {path}")
    print(f"  {snap}")


def cmd_backtest(args: argparse.Namespace) -> None:
    price_root = Path(args.price_root)
    options_root = Path(args.options_root)
    portfolio_root = Path(args.portfolio_root)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    cfg_bt = BacktestConfig()
    cfg_tr = TrainConfig(n_jobs=max(1, int(args.lgbm_jobs)))
    cfg_opt = load_optimizer_config(_PROJECT_ROOT / "src" / "config" / "config.yaml")

    solver = "ILP (PuLP)" if cfg_opt.prefer_ilp else "greedy"
    print(
        f"[optimizer] solver={solver}  max_per_symbol={cfg_opt.max_trades_per_symbol}"
        f"  delta_cap_long={cfg_opt.max_abs_delta_long}"
        f"  vega_cap_long={cfg_opt.max_abs_vega_long}"
        f"  delta_cap_short={cfg_opt.max_abs_delta_short}"
        f"  vega_cap_short={cfg_opt.max_abs_vega_short}"
    )

    run_started = time.perf_counter()
    stage_times: dict[str, float] = {}

    def _elapsed_min() -> float:
        return (time.perf_counter() - run_started) / 60.0

    def _mark(stage: str, t0: float) -> None:
        stage_times[stage] = time.perf_counter() - t0

    def _time_exceeded() -> bool:
        return args.max_minutes is not None and _elapsed_min() >= float(args.max_minutes)

    def _with_retry(fn, label: str, retries: int = 3, base_sleep: float = 2.0):
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt == retries:
                    break
                wait_s = base_sleep * attempt
                print(
                    f"[retry] {label} failed (attempt {attempt}/{retries}): {exc}. "
                    f"Retrying in {wait_s:.1f}s..."
                )
                time.sleep(wait_s)
        raise last_exc

    # Optionally connect IBKR to refresh today's portfolio snapshot
    ib = _get_ib_client() if args.use_ibkr else None

    t0 = time.perf_counter()
    print(f"[data] Loading underlyings {args.start} -> {args.end} ...")
    px = _with_retry(
        lambda: read_underlyings(args.start, args.end, price_root),
        "read_underlyings",
    )
    print(f"       {len(px):,} rows, {px['symbol'].nunique():,} symbols")
    _mark("load_underlyings_s", t0)

    t0 = time.perf_counter()
    print("[data] Loading options snapshots...")
    opt = _with_retry(
        lambda: read_options(args.start, args.end, options_root),
        "read_options",
    )
    print(f"       {len(opt):,} option rows")
    _mark("load_options_s", t0)

    t0 = time.perf_counter()
    print("[data] Loading portfolio history...")
    port = _with_retry(
        lambda: read_portfolio(args.start, args.end, portfolio_root, ib_client=ib),
        "read_portfolio",
    )
    print(f"       {len(port)} portfolio days")
    _mark("load_portfolio_s", t0)

    print("[features] Building training tables...")
    t0_features = time.perf_counter()
    tables = build_training_table(
        px=px,
        opt=opt,
        portfolio=port,
        horizons=args.horizons,
        categories=args.categories,
        cfg=cfg_bt,
    )
    feature_time = time.perf_counter() - t0_features
    stage_times["build_training_tables_s"] = feature_time
    print(
        f"[features] Done in {feature_time:.1f}s - "
        + ", ".join(
            f"{c} H={h} ({len(df):,} rows)"
            for (c, h), (df, _) in tables.items()
            if not df.empty
        )
    )

    all_metrics = []
    completed_combos: list[str] = []
    stopped_early = False
    stop_reason = ""
    n_combos = sum(1 for df, _ in tables.values() if not df.empty)
    combo_i = 0

    for (category, horizon), (df, feature_cols) in tables.items():
        if _time_exceeded():
            stopped_early = True
            stop_reason = (
                f"max_minutes={args.max_minutes:.1f} reached before combo {category}/H{horizon}"
            )
            print(f"[stop] {stop_reason}")
            break

        if df.empty:
            print(f"[skip] {category} H={horizon}: empty table")
            continue

        combo_i += 1
        all_dates = sorted([pd.to_datetime(d) for d in df["date"].unique()])

        model_dir = out_dir / "models" / f"category={category}" / f"h={horizon}"
        bt_dir = out_dir / "backtests" / f"category={category}" / f"h={horizon}"
        ensure_dir(model_dir)
        ensure_dir(bt_dir)

        fold_metrics = []
        fold_curves = []

        print(
            f"\n[combo {combo_i}/{n_combos}] {category} H={horizon}  "
            f"({len(df):,} rows, {len(all_dates)} dates, {len(feature_cols)} features)"
        )

        try:
            splits = list(
                walk_forward_splits(
                    all_dates,
                    min_train_days=args.min_train_days,
                    test_days=args.test_days,
                    step_days=args.step_days,
                    embargo=horizon,
                )
            )
        except RuntimeError as exc:
            print(f"  [skip] {exc}")
            continue

        n_folds = len(splits)
        print(f"  -> {n_folds} fold(s) planned")

        for fold_i, (tr_start, tr_end, te_start, te_end) in enumerate(splits, 1):
            if _time_exceeded():
                stopped_early = True
                stop_reason = (
                    f"max_minutes={args.max_minutes:.1f} reached during combo "
                    f"{category}/H{horizon} fold {fold_i}"
                )
                print(f"  [stop] {stop_reason}")
                break

            tr_mask = (df["date"] >= tr_start) & (df["date"] <= tr_end)
            te_mask = (df["date"] >= te_start) & (df["date"] <= te_end)

            dtrain = df[tr_mask].copy()
            dtest = df[te_mask].copy()
            if dtrain.empty or dtest.empty:
                continue

            t0_fold = time.perf_counter()
            print(
                f"  fold {fold_i:02d}/{n_folds}  train->{date_str(tr_end)}  "
                f"test {date_str(te_start)}->{date_str(te_end)}  "
                f"({len(dtrain):,} train rows, {len(dtest):,} test rows) ...",
                flush=True,
            )

            model = train_ranker(dtrain, feature_cols, cfg_tr)
            equity = backtest_ranker(
                dtest,
                model,
                feature_cols,
                port,
                cfg_bt,
                cfg_opt,
                category,
                args.topk,
            )
            elapsed = time.perf_counter() - t0_fold

            if equity.empty:
                print(f"         -> no trades  [{elapsed:.1f}s]")
                continue

            total_pnl = float(equity["pnl"].sum())
            avg_daily = float(equity["pnl"].mean())
            vol_daily = float(equity["pnl"].std(ddof=1)) if len(equity) > 1 else 0.0
            sharpe = (avg_daily / (vol_daily + 1e-9)) * math.sqrt(252.0)

            fold_metrics.append(
                {
                    "category": category,
                    "horizon": horizon,
                    "fold": fold_i,
                    "train_end": date_str(tr_end),
                    "test_start": date_str(te_start),
                    "test_end": date_str(te_end),
                    "total_pnl": total_pnl,
                    "avg_daily_pnl": avg_daily,
                    "daily_vol": vol_daily,
                    "sharpe_proxy": sharpe,
                    "n_days": len(equity),
                    "n_trades": int(equity["n_trades"].sum()),
                }
            )
            equity["category"] = category
            equity["horizon"] = horizon
            equity["test_start"] = pd.to_datetime(te_start)
            fold_curves.append(equity)

            print(
                f"         -> PnL={total_pnl:+.0f}  Sharpe={sharpe:.2f}"
                f"  trades={int(equity['n_trades'].sum())}  [{elapsed:.1f}s]"
            )

        if not fold_metrics:
            continue

        metrics_df = pd.DataFrame(fold_metrics)
        _with_retry(
            lambda: metrics_df.to_parquet(bt_dir / "fold_metrics.parquet", index=False),
            f"write_fold_metrics {category}/H{horizon}",
        )

        _with_retry(
            lambda: pd.concat(fold_curves, ignore_index=True).to_parquet(
                bt_dir / "fold_equity.parquet", index=False
            ),
            f"write_fold_equity {category}/H{horizon}",
        )

        # Save feature list for inference
        with open(model_dir / "feature_cols.json", "w", encoding="utf-8") as f:
            json.dump(feature_cols, f, indent=2)

        all_metrics.append(metrics_df)
        completed_combos.append(f"{category}/H{horizon}")
        del metrics_df, fold_curves
        gc.collect()

    if all_metrics:
        summary = pd.concat(all_metrics, ignore_index=True)
        _with_retry(
            lambda: summary.to_parquet(out_dir / "summary_metrics.parquet", index=False),
            "write_summary_metrics",
        )
        print("\n" + "=" * 60)
        print(
            summary.sort_values(["category", "horizon", "test_end"])\
                .tail(30)\
                .to_string(index=False)
        )
    else:
        print("\nNo results produced. Labels require future options snapshots "
              "for the chosen horizons.")

    status = {
        "elapsed_minutes": round(_elapsed_min(), 3),
        "max_minutes": args.max_minutes,
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "requested_horizons": list(args.horizons),
        "requested_categories": list(args.categories),
        "completed_combos": completed_combos,
        "stage_times_s": {k: round(v, 3) for k, v in stage_times.items()},
    }
    with open(out_dir / "run_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    print(f"[status] wrote {out_dir / 'run_status.json'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Quantum Trader options ML pipeline")

    ap.add_argument(
        "--snapshot",
        action="store_true",
        help="Save today's portfolio snapshot from live IBKR and exit",
    )

    ap.add_argument("--price_root", default=str(PRICE_HISTORICAL_ROOT))
    ap.add_argument("--options_root", default=str(OPTIONS_SNAPSHOT_ROOT))
    ap.add_argument("--portfolio_root", default=str(PORTFOLIO_DAILY_ROOT))
    ap.add_argument("--out_dir", default=str(_PROJECT_ROOT / "ml_output"))

    ap.add_argument("--start", default="2025-02-20")
    ap.add_argument("--end", default="2026-02-23")
    ap.add_argument("--horizons", type=int, nargs="+", default=[2, 5, 10, 21])
    ap.add_argument(
        "--categories",
        nargs="+",
        default=["long_premium", "short_premium"],
    )
    ap.add_argument("--topk", type=int, default=3)

    ap.add_argument("--min_train_days", type=int, default=80)
    ap.add_argument("--test_days", type=int, default=20)
    ap.add_argument("--step_days", type=int, default=20)
    ap.add_argument("--lgbm_jobs", type=int, default=1)
    ap.add_argument(
        "--max_minutes",
        type=float,
        default=None,
        help="Hard wall-clock cap for this pipeline run.",
    )

    ap.add_argument(
        "--use_ibkr",
        action="store_true",
        help="Connect to IBKR to refresh today's portfolio snapshot",
    )

    args = ap.parse_args()

    if args.snapshot:
        cmd_snapshot(Path(args.portfolio_root))
    else:
        cmd_backtest(args)


if __name__ == "__main__":
    main()
