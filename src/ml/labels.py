"""Build realized PnL labels for a given horizon H (EOD-to-EOD)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.config import BacktestConfig, MARGIN_PROXY_MULT


def _forward_trading_date(dates: pd.Series, horizon: int) -> pd.Series:
    """
    Map each date to the trading date `horizon` positions ahead.

    The trading-date calendar is the sorted unique set of dates present in
    `dates`. Dates with no date `horizon` positions ahead (i.e. within the
    last `horizon` trading days) map to NaT.
    """
    trading_dates = np.sort(dates.dropna().unique())
    pos = {d: i for i, d in enumerate(trading_dates)}
    n = len(trading_dates)

    def _fwd(d):
        i = pos.get(d)
        if i is None or i + horizon >= n:
            return pd.NaT
        return trading_dates[i + horizon]

    return dates.map(_fwd)


def build_labels_for_horizon(
    opt_feat: pd.DataFrame,
    horizon: int,
    cfg: BacktestConfig,
    category: str,
) -> pd.DataFrame:
    """
    For each option row at date t, look up mid price `horizon` trading days
    ahead. The forward date is resolved positionally against the sorted unique
    set of trading dates actually present in the data (not by adding calendar
    days, which would land on weekends/holidays and silently drop labels in a
    biased pattern).

    Adds columns
    ------------
    date_fwd      : trading date `horizon` positions after t (NaT near the end)
    mid_fwd       : mid price at that future date (NaN if unavailable)
    valid_label   : 1 if mid_fwd exists and option has not expired
    pnl           : realized PnL per contract (in $)
    ret_on_risk   : pnl / risk proxy
    score         : risk-adjusted ranking target
    """
    df = opt_feat.copy()
    key_cols = ["symbol", "right", "expiry", "strike"]
    df["date_fwd"] = _forward_trading_date(df["date"], horizon)

    # Future mid look-up via MultiIndex hash (O(N) vs O(N log N) merge)
    mid_series = df.set_index(key_cols + ["date"])["mid"]
    if mid_series.index.duplicated().any():
        mid_series = mid_series[~mid_series.index.duplicated(keep="last")]
    lookup_idx = pd.MultiIndex.from_arrays([df[c] for c in key_cols] + [df["date_fwd"]])
    df["mid_fwd"] = mid_series.reindex(lookup_idx).values
    out = df

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
        risk   = np.maximum(entry.abs() * MARGIN_PROXY_MULT, 1.0)   # credit-based margin proxy

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
