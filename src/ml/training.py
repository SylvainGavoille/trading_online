"""Build training tables, train LightGBM rankers, walk-forward split generator."""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.ml.config import BacktestConfig, TrainConfig
from src.ml.features.underlying import build_underlying_features, attach_underlying_close
from src.ml.features.options import build_option_features, categorize_option_rows
from src.ml.labels import build_labels_for_horizon


# ---------------------------------------------------------------------------
# Training table builder
# ---------------------------------------------------------------------------

def build_training_table(
    px: pd.DataFrame,
    opt: pd.DataFrame,
    portfolio: pd.DataFrame,
    horizons: List[int],
    categories: List[str],
    cfg: BacktestConfig,
) -> Dict[Tuple[str, int], pd.DataFrame]:
    """
    Returns {(category, horizon): DataFrame with features + 'score' label}.
    The DataFrame carries a `.attrs['feature_cols']` list for downstream use.
    """
    und_feat = build_underlying_features(px)
    opt_feat = build_option_features(opt, und_feat, portfolio)
    opt_feat = attach_underlying_close(opt_feat, px)

    # Drop rows with no option mid or already expired
    opt_feat = opt_feat[~opt_feat["mid"].isna()].copy()
    opt_feat = opt_feat[opt_feat["dte"] > 0].copy()
    opt_feat["spread_pct"] = opt_feat["spread_pct"].astype(float)

    tables: Dict[Tuple[str, int], pd.DataFrame] = {}

    for category in categories:
        mask = categorize_option_rows(opt_feat, category)
        base = opt_feat[mask].copy()

        # Liquidity filter at training time
        base = base[
            (base["openInterest"].fillna(0) >= cfg.min_oi)
            | (base["volume"].fillna(0) >= cfg.min_volume)
        ].copy()
        base = base[base["spread_pct"].fillna(1.0) <= cfg.max_spread_pct].copy()

        for h in horizons:
            labeled = build_labels_for_horizon(base, h, cfg, category)
            labeled = labeled[labeled["valid_label"] == 1].copy()

            # Re-encode right
            labeled["is_call"] = (
                labeled["right"].astype(str).str.upper() == "C"
            ).astype(int)

            # Identify numeric feature columns (exclude identifiers and labels)
            _id    = {"date", "date_fwd", "symbol", "right", "expiry",
                      "strike", "contractId"}
            _label = {"pnl", "ret_on_risk", "score", "valid_label", "mid_fwd"}
            _drop  = _id | _label

            feature_cols = [
                c for c in labeled.columns
                if c not in _drop and pd.api.types.is_numeric_dtype(labeled[c])
            ]

            # Require at least 20 days of history (underlying features need it)
            labeled = labeled.dropna(
                subset=["ret_20d", "rv_20d", "trend_10_20", "log_moneyness"],
                how="any",
            )

            labeled.attrs["feature_cols"] = feature_cols
            tables[(category, h)] = labeled

    return tables


# ---------------------------------------------------------------------------
# LightGBM ranker
# ---------------------------------------------------------------------------

def train_ranker(
    df: pd.DataFrame,
    feature_cols: List[str],
    train_cfg: TrainConfig,
) -> lgb.LGBMRanker:
    """
    Fit a LambdaRank model that ranks option candidates within each trading day.
    """
    df = df.sort_values("date").copy()

    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        num_leaves=train_cfg.num_leaves,
        learning_rate=train_cfg.learning_rate,
        n_estimators=train_cfg.n_estimators,
        min_data_in_leaf=train_cfg.min_data_in_leaf,
        feature_fraction=train_cfg.feature_fraction,
        bagging_fraction=train_cfg.bagging_fraction,
        bagging_freq=train_cfg.bagging_freq,
        lambda_l2=train_cfg.lambda_l2,
        force_col_wise=train_cfg.force_col_wise,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    all_dates = sorted(df["date"].unique())
    n_val = max(1, int(len(all_dates) * 0.2))
    train_dates = set(all_dates[:-n_val])
    val_dates   = set(all_dates[-n_val:])

    df_train = df[df["date"].isin(train_dates)]
    df_val   = df[df["date"].isin(val_dates)]

    if df_val.empty or len(train_dates) < 10:
        # Not enough data: train without early stopping.
        # np.unique on pre-sorted date column is a single O(N) pass.
        _, grp = np.unique(df["date"].values, return_counts=True)
        model.fit(
            df[feature_cols].to_numpy(dtype=np.float32),
            df["score"].to_numpy(dtype=np.float32),
            group=grp.tolist(),
        )
    else:
        _, tr_grp = np.unique(df_train["date"].values, return_counts=True)
        _, va_grp = np.unique(df_val["date"].values,   return_counts=True)

        X_train = df_train[feature_cols].to_numpy(dtype=np.float32)
        y_train = df_train["score"].to_numpy(dtype=np.float32)
        X_val   = df_val[feature_cols].to_numpy(dtype=np.float32)
        y_val   = df_val["score"].to_numpy(dtype=np.float32)

        model.fit(
            X_train, y_train, group=tr_grp.tolist(),
            eval_set=[(X_val, y_val)], eval_group=[va_grp.tolist()],
            callbacks=[
                lgb.early_stopping(20, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )

    return model


# ---------------------------------------------------------------------------
# Walk-forward split generator
# ---------------------------------------------------------------------------

def walk_forward_splits(
    dates: List[pd.Timestamp],
    min_train_days: int = 60,
    test_days: int = 20,
    step_days: int = 20,
) -> Iterable[Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """
    Yields (train_start, train_end, test_start, test_end) tuples.
    Advances the window by `step_days` after each fold.
    """
    dates = sorted(dates)
    if len(dates) < min_train_days + test_days:
        raise RuntimeError(
            f"Not enough unique dates ({len(dates)}) for walk-forward splits. "
            f"Need at least {min_train_days + test_days}."
        )
    i = min_train_days - 1
    while i + test_days < len(dates):
        yield (
            dates[0],
            dates[i],
            dates[i + 1],
            dates[min(i + test_days, len(dates) - 1)],
        )
        i += step_days
