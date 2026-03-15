"""Actions-only ML pipeline (no options dependency).

Builds features from underlyings, trains horizon-specific regressors, and
runs a simple daily top-k backtest per walk-forward fold.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

# Ensure project root is importable regardless of working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.data.underlyings import read_underlyings
from src.ml.features.underlying import build_underlying_features
from src.ml.training import walk_forward_splits
from src.ml.utils import ensure_dir


def _build_table(px: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, list[str]]:
    feat = build_underlying_features(px)
    fut = (
        px.sort_values(["symbol", "date"])
        .assign(fwd_ret=lambda d: d.groupby("symbol")["close"].shift(-horizon) / d["close"] - 1.0)
        [["symbol", "date", "fwd_ret"]]
    )
    df = feat.merge(fut, on=["symbol", "date"], how="inner")
    feature_cols = [c for c in feat.columns if c not in {"symbol", "date"}]
    df = df.dropna(subset=feature_cols + ["fwd_ret"]).copy()
    return df, feature_cols


def _train_regressor(
    df: pd.DataFrame, feature_cols: list[str], lgbm_jobs: int
) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(
        objective="regression",
        metric="l2",
        num_leaves=63,
        learning_rate=0.05,
        n_estimators=300,
        min_data_in_leaf=100,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=1,
        lambda_l2=1.0,
        force_col_wise=True,
        random_state=42,
        n_jobs=max(1, int(lgbm_jobs)),
        verbose=-1,
    )
    model.fit(
        df[feature_cols].to_numpy(dtype=np.float32),
        df["fwd_ret"].to_numpy(dtype=np.float32),
    )
    return model


def _backtest_topk(
    dtest: pd.DataFrame, model: lgb.LGBMRegressor, feature_cols: list[str], topk: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (equity_curve, daily_picks).

    daily_picks columns: date, symbol, rank, score, fwd_ret
    """
    work = dtest.copy()
    work["score"] = model.predict(work[feature_cols].to_numpy(dtype=np.float32))
    eq_rows: list[dict] = []
    pick_rows: list[dict] = []
    for day, grp in work.groupby("date"):
        ranked = grp.sort_values("score", ascending=False).reset_index(drop=True)
        picks = ranked.head(topk)
        if picks.empty:
            continue
        eq_rows.append({"date": day, "n_picks": int(len(picks)), "pnl": float(picks["fwd_ret"].mean())})
        for rank, (_, row) in enumerate(picks.iterrows(), 1):
            pick_rows.append({
                "date": day,
                "symbol": row["symbol"],
                "rank": rank,
                "score": float(row["score"]),
                "fwd_ret": float(row["fwd_ret"]),
            })
    if not eq_rows:
        empty_eq = pd.DataFrame(columns=["date", "n_picks", "pnl", "equity"])
        return empty_eq, pd.DataFrame()
    eq = pd.DataFrame(eq_rows).sort_values("date")
    eq["equity"] = (1.0 + eq["pnl"]).cumprod()
    return eq, pd.DataFrame(pick_rows)


def _generate_recommendations(
    px: pd.DataFrame,
    feature_cols: list[str],
    model: lgb.LGBMRegressor,
    horizon: int,
    rec_dir: Path,
    run_date: str,
    top_n: int = 50,
) -> None:
    """Score all symbols on the most recent available date and save as today's recommendations."""
    feat = build_underlying_features(px)
    latest_date = feat["date"].max()
    today_feat = feat[feat["date"] == latest_date].copy()
    if today_feat.empty:
        return

    valid = today_feat[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    today_feat["score"] = model.predict(valid.to_numpy(dtype=np.float32))
    today_feat = today_feat.sort_values("score", ascending=False).reset_index(drop=True)
    today_feat["rank"] = today_feat.index + 1

    close_map = px[px["date"] == latest_date].set_index("symbol")["close"]
    today_feat["close"] = today_feat["symbol"].map(close_map)
    today_feat["horizon"] = horizon
    today_feat["run_date"] = run_date
    today_feat["price_date"] = str(latest_date)[:10]

    recs = today_feat[["symbol", "rank", "score", "close", "horizon", "run_date", "price_date"]].head(top_n)
    ensure_dir(rec_dir)
    recs.to_parquet(rec_dir / f"{run_date}_h{horizon}.parquet", index=False)
    print(f"[actions] H={horizon}: {len(recs)} recommendations saved -> {rec_dir}", flush=True)


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    t_pipeline_start = time.perf_counter()

    print(f"[actions] Loading underlyings {args.start} -> {args.end} ...", flush=True)
    px = read_underlyings(args.start, args.end, Path(args.price_root))
    px["open"] = px["open"].astype(np.float32)
    px["high"] = px["high"].astype(np.float32)
    px["low"] = px["low"].astype(np.float32)
    px["close"] = px["close"].astype(np.float32)
    px["volume"] = px["volume"].astype(np.int32)
    if args.max_symbols is not None and args.max_symbols > 0:
        top_syms = (
            px.groupby("symbol", as_index=False)["volume"]
            .mean()
            .sort_values("volume", ascending=False)
            .head(args.max_symbols)["symbol"]
            .tolist()
        )
        px = px[px["symbol"].isin(top_syms)].copy()
        print(
            f"[actions] limited to top {len(top_syms)} symbols by avg volume",
            flush=True,
        )
    print(f"[actions] {len(px):,} rows, {px['symbol'].nunique():,} symbols", flush=True)

    all_metrics: list[pd.DataFrame] = []
    for horizon in args.horizons:
        if args.max_minutes is not None:
            elapsed_min = (time.perf_counter() - t_pipeline_start) / 60.0
            if elapsed_min >= args.max_minutes:
                print(
                    f"[actions] Reached max_minutes={args.max_minutes:.1f} after {elapsed_min:.1f}m; "
                    "stopping further horizons.",
                    flush=True,
                )
                break
        t0 = time.time()
        table, feature_cols = _build_table(px, horizon)
        if table.empty:
            print(f"[actions][skip] H={horizon}: empty table", flush=True)
            continue
        for c in feature_cols + ["fwd_ret"]:
            table[c] = table[c].astype(np.float32)

        dates = sorted(pd.to_datetime(table["date"].unique()))
        try:
            splits = list(
                walk_forward_splits(
                    dates,
                    min_train_days=args.min_train_days,
                    test_days=args.test_days,
                    step_days=args.step_days,
                )
            )
        except RuntimeError as exc:
            print(f"[actions][skip] H={horizon}: {exc}", flush=True)
            continue

        h_models_dir = out_dir / "models" / f"h={horizon}"
        h_bt_dir = out_dir / "backtests" / f"h={horizon}"
        ensure_dir(h_models_dir)
        ensure_dir(h_bt_dir)

        fold_metrics = []
        fold_curves = []
        fold_picks: list[pd.DataFrame] = []
        last_model: lgb.LGBMRegressor | None = None
        for fold_i, (_tr_s, tr_e, te_s, te_e) in enumerate(splits, 1):
            if args.max_minutes is not None:
                elapsed_min = (time.perf_counter() - t_pipeline_start) / 60.0
                if elapsed_min >= args.max_minutes:
                    print(
                        f"[actions] Reached max_minutes={args.max_minutes:.1f}; "
                        f"stopping H={horizon} at fold {fold_i}.",
                        flush=True,
                    )
                    break
            tr_mask = (table["date"] <= tr_e)
            te_mask = (table["date"] >= te_s) & (table["date"] <= te_e)
            dtrain = table[tr_mask]
            dtest = table[te_mask]
            if dtrain.empty or dtest.empty:
                continue

            model = _train_regressor(dtrain, feature_cols, args.lgbm_jobs)
            curve, picks_df = _backtest_topk(dtest, model, feature_cols, args.topk)
            if curve.empty:
                continue

            total = float(curve["pnl"].sum())
            avg = float(curve["pnl"].mean())
            vol = float(curve["pnl"].std(ddof=1)) if len(curve) > 1 else 0.0
            sharpe = (avg / (vol + 1e-9)) * math.sqrt(252.0)
            fold_metrics.append(
                {
                    "horizon": horizon,
                    "fold": fold_i,
                    "train_end": pd.to_datetime(tr_e).strftime("%Y-%m-%d"),
                    "test_start": pd.to_datetime(te_s).strftime("%Y-%m-%d"),
                    "test_end": pd.to_datetime(te_e).strftime("%Y-%m-%d"),
                    "total_pnl": total,
                    "avg_daily_pnl": avg,
                    "daily_vol": vol,
                    "sharpe_proxy": sharpe,
                    "n_days": int(len(curve)),
                    "n_picks": int(curve["n_picks"].sum()),
                }
            )
            curve = curve.copy()
            curve["fold"] = fold_i
            curve["horizon"] = horizon
            fold_curves.append(curve)

            if not picks_df.empty:
                picks_df = picks_df.copy()
                picks_df["fold"] = fold_i
                picks_df["horizon"] = horizon
                fold_picks.append(picks_df)

            last_model = model

            if hasattr(model, "booster_") and model.booster_ is not None:
                model.booster_.save_model(str(h_models_dir / f"model_fold{fold_i}.txt"))

        if not fold_metrics:
            print(f"[actions][skip] H={horizon}: no valid folds", flush=True)
            continue

        metrics_df = pd.DataFrame(fold_metrics)
        curves_df = pd.concat(fold_curves, ignore_index=True)
        metrics_df.to_parquet(h_bt_dir / "fold_metrics.parquet", index=False)
        curves_df.to_parquet(h_bt_dir / "fold_equity.parquet", index=False)
        if fold_picks:
            picks_all = pd.concat(fold_picks, ignore_index=True)
            picks_all.to_parquet(h_bt_dir / "daily_picks.parquet", index=False)
        with open(h_models_dir / "feature_cols.json", "w", encoding="utf-8") as f:
            json.dump(feature_cols, f, indent=2)
        all_metrics.append(metrics_df)

        # Generate today's recommendations using the most recent fold's model
        if last_model is not None:
            rec_dir = out_dir / "recommendations"
            _generate_recommendations(px, feature_cols, last_model, horizon, rec_dir, args.end)

        print(
            f"[actions] H={horizon}: folds={len(metrics_df)} done in {time.time() - t0:.1f}s",
            flush=True,
        )
        del table, metrics_df, curves_df, fold_metrics, fold_curves, fold_picks, last_model
        gc.collect()

    if not all_metrics:
        print("[actions] No horizon produced a model.", flush=True)
        return

    summary = pd.concat(all_metrics, ignore_index=True)
    summary.to_parquet(out_dir / "summary.parquet", index=False)
    print(f"[actions] Done. Summary rows={len(summary)} -> {out_dir / 'summary.parquet'}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Actions-only daily ML pipeline")
    ap.add_argument("--price_root", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--horizons", nargs="+", type=int, default=[2, 5, 10, 21])
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--min_train_days", type=int, default=80)
    ap.add_argument("--test_days", type=int, default=20)
    ap.add_argument("--step_days", type=int, default=20)
    ap.add_argument(
        "--lgbm_jobs",
        type=int,
        default=2,
        help="LightGBM worker threads per fold (lower to reduce memory pressure)",
    )
    ap.add_argument(
        "--max_symbols",
        type=int,
        default=None,
        help="Optional cap on number of symbols (top by average volume)",
    )
    ap.add_argument(
        "--max_minutes",
        type=float,
        default=None,
        help="Hard wall-clock cap (minutes) for the actions pipeline.",
    )
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
