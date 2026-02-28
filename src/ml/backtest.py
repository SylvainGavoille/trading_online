"""Apply portfolio constraints and run walk-forward backtest with ILP optimizer."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
import lightgbm as lgb

from src.ml.config import BacktestConfig, OptimizerConfig
from src.ml.optimizer import build_constraints, optimize_trades


# ---------------------------------------------------------------------------
# Constraint filter (pre-optimizer per-trade liquidity + budget check)
# ---------------------------------------------------------------------------

def apply_constraints(
    day_df: pd.DataFrame,
    portfolio_row: pd.Series,
    cfg: BacktestConfig,
    category: str,
) -> pd.DataFrame:
    """
    Filter a single day's candidates to those satisfying liquidity,
    per-trade budget, and naked-call constraints.
    """
    df = day_df.copy()

    # Liquidity
    df = df[df["spread_pct"].fillna(1.0) <= cfg.max_spread_pct].copy()
    df = df[
        (df["openInterest"].fillna(0) >= cfg.min_oi)
        | (df["volume"].fillna(0) >= cfg.min_volume)
    ].copy()

    # Budget check
    bp = float(portfolio_row.get("buying_power", np.nan))
    if not np.isfinite(bp) or bp <= 0:
        return df.iloc[0:0].copy()

    mult = df["multiplier"].fillna(100).astype(float)
    mid  = df["mid"].astype(float)
    cat  = category.lower()

    if cat == "long_premium":
        df["est_cost"] = mid * mult
        budget = cfg.max_premium_spend_pct_bp * bp
        df = df[df["est_cost"] <= budget].copy()

    elif cat == "short_premium":
        df["est_margin_proxy"] = (mid * mult) * 5.0
        budget = cfg.max_margin_add_pct_bp * bp
        df = df[df["est_margin_proxy"] <= budget].copy()
        if not cfg.allow_naked_calls:
            df = df[df["right"].astype(str).str.upper() != "C"].copy()

    return df


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

def backtest_ranker(
    df: pd.DataFrame,
    model: lgb.LGBMRanker,
    feature_cols: List[str],
    portfolio: pd.DataFrame,
    cfg: BacktestConfig,
    opt_cfg: OptimizerConfig,
    category: str,
    topk: int,
) -> pd.DataFrame:
    """
    For each trading day in df:
      1. Score all candidates with the trained model.
      2. Apply per-trade liquidity / budget constraints.
      3. Run ILP (or greedy) optimizer to select the best portfolio-feasible set.
      4. Realise PnL using the pre-computed `pnl` column.

    Returns a daily summary DataFrame with:
        date, pnl, avg_pred, n_trades, cum_pnl
    """
    df = df.copy()
    df["pred_score"] = model.predict(df[feature_cols].to_numpy(dtype=np.float32))

    portfolio_map = portfolio.set_index("date")
    trades = []

    for d, day_df in df.groupby("date", sort=True):
        if d not in portfolio_map.index:
            continue

        p_row = portfolio_map.loc[d]

        # Step 1 — hard per-trade filter
        constrained = apply_constraints(day_df, p_row, cfg, category)
        if constrained.empty:
            continue

        # Step 2 — portfolio-level optimizer (ILP or greedy)
        cons = build_constraints(p_row, category, cfg, opt_cfg, topk)
        pick = optimize_trades(
            constrained,
            category=category,
            cons=cons,
            prefer_ilp=opt_cfg.prefer_ilp,
        )
        if pick.empty:
            continue

        trades.append(pick)

    if not trades:
        return pd.DataFrame()

    trades_df = pd.concat(trades, ignore_index=True)
    daily = (
        trades_df.groupby("date")
        .agg(
            pnl=(   "pnl",        "sum"),
            avg_pred=("pred_score", "mean"),
            n_trades=("selected",  "sum"),
        )
        .reset_index()
        .sort_values("date")
    )
    daily["cum_pnl"] = daily["pnl"].cumsum()
    return daily
