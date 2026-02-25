"""Build realized PnL labels for a given horizon H (EOD-to-EOD)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.config import BacktestConfig


def build_labels_for_horizon(
    opt_feat: pd.DataFrame,
    horizon: int,
    cfg: BacktestConfig,
    category: str,
) -> pd.DataFrame:
    """
    For each option row at date t, look up mid price at t + horizon trading days
    (calendar days used as proxy — options snapshots are only on trading days so
    the merge will simply not find a match if t+H is a holiday/weekend, which is
    acceptable for v1).

    Adds columns
    ------------
    date_fwd      : t + timedelta(horizon)
    mid_fwd       : mid price at that future date (NaN if unavailable)
    valid_label   : 1 if mid_fwd exists and option has not expired
    pnl           : realized PnL per contract (in $)
    ret_on_risk   : pnl / risk proxy
    score         : risk-adjusted ranking target
    """
    df = opt_feat.copy()
    key_cols = ["symbol", "right", "expiry", "strike"]
    df["date_fwd"] = df["date"] + pd.Timedelta(days=horizon)

    # Future mid look-up table
    future = (
        df[key_cols + ["date", "mid"]]
        .rename(columns={"date": "date_lookup", "mid": "mid_fwd"})
    )
    out = df.merge(
        future,
        left_on=key_cols + ["date_fwd"],
        right_on=key_cols + ["date_lookup"],
        how="left",
    ).drop(columns=["date_lookup"])

    # Validity: future mid must exist and option must not have expired
    out["valid_label"] = (~out["mid_fwd"].isna()).astype(int)
    out.loc[out["date_fwd"] >= out["expiry"], "valid_label"] = 0

    # Costs
    slip = cfg.slippage_bps / 10_000.0
    mult = out["multiplier"].fillna(100).astype(float)
    comm = 2.0 * cfg.commission_per_contract   # both legs

    entry_mid = out["mid"].astype(float)
    exit_mid  = out["mid_fwd"].astype(float)

    cat = category.lower()
    if cat == "long_premium":
        entry  = entry_mid * (1.0 + slip) * mult + comm
        exitv  = exit_mid  * (1.0 - slip) * mult
        pnl    = exitv - entry
        risk   = entry                              # premium at risk

    elif cat == "short_premium":
        entry  = entry_mid * (1.0 - slip) * mult - comm   # net credit
        exitv  = exit_mid  * (1.0 + slip) * mult
        pnl    = entry - exitv
        risk   = np.maximum(entry.abs() * 5.0, 1.0)       # 5× credit proxy

    else:
        raise ValueError(f"Unknown category for labeling: {category}")

    out["pnl"]         = pnl
    out["ret_on_risk"] = out["pnl"] / risk.replace(0, np.nan)

    # Score: reward risk-adjusted PnL, penalize wide spreads and high margin use
    out["score"] = (
        out["ret_on_risk"]
        - 0.25 * out["spread_pct"].astype(float).fillna(0.0)
        - 0.05 * out["margin_to_netliq"].astype(float).fillna(0.0)
    )

    return out
