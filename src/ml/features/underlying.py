"""Feature engineering for underlying price series (no look-ahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.utils import safe_log1p, winsorize


def build_underlying_features(px: pd.DataFrame) -> pd.DataFrame:
    """
    Input : symbol, date, open, high, low, close, volume  (multi-symbol, multi-date)
    Output: symbol, date + feature columns

    All features use strictly past data (pct_change / rolling on past N days).
    """
    px = px.copy()
    g = px.groupby("symbol")

    px["ret_1d"]  = g["close"].pct_change(1)
    px["ret_5d"]  = g["close"].pct_change(5)
    px["ret_20d"] = g["close"].pct_change(20)

    # Realized volatility
    px["rv_10d"] = (
        g["ret_1d"].rolling(10).std().reset_index(level=0, drop=True)
    )
    px["rv_20d"] = (
        g["ret_1d"].rolling(20).std().reset_index(level=0, drop=True)
    )

    # Intraday range and overnight gap
    px["range_pct"] = (px["high"] - px["low"]) / px["close"].replace(0, np.nan)
    px["gap_pct"]   = (
        (px["open"] - g["close"].shift(1))
        / g["close"].shift(1)
    )

    # Volume
    px["vol_log"]  = safe_log1p(px["volume"])
    vol_ma = g["vol_log"].rolling(20).mean().reset_index(level=0, drop=True)
    vol_sd = g["vol_log"].rolling(20).std().reset_index(level=0, drop=True)
    px["vol_z_20d"] = (px["vol_log"] - vol_ma) / vol_sd

    # Trend
    px["ma_10"] = g["close"].rolling(10).mean().reset_index(level=0, drop=True)
    px["ma_20"] = g["close"].rolling(20).mean().reset_index(level=0, drop=True)
    px["trend_10_20"] = px["ma_10"] / px["ma_20"] - 1.0

    FEAT_COLS = [
        "ret_1d", "ret_5d", "ret_20d",
        "rv_10d", "rv_20d",
        "range_pct", "gap_pct",
        "vol_log", "vol_z_20d",
        "trend_10_20",
    ]
    for c in FEAT_COLS:
        px[c] = winsorize(
            px[c].astype(float).replace([np.inf, -np.inf], np.nan)
        )

    return px[["symbol", "date"] + FEAT_COLS].copy()


def attach_underlying_close(opt_feat: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """
    Merge underlying close into the options feature table to compute moneyness.
    """
    close_df = px[["symbol", "date", "close"]].copy()
    out = opt_feat.merge(close_df, on=["symbol", "date"], how="left")
    out["moneyness"]     = out["close"] / out["strike"].replace(0, np.nan)
    out["log_moneyness"] = np.log(out["moneyness"].replace(0, np.nan))
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    return out
