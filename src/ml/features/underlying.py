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
    # Sort + clean RangeIndex so reset_index(level=0, drop=True) aligns safely.
    px = px.sort_values(["symbol", "date"]).reset_index(drop=True).copy()

    # Single groupby object; sort=False skips redundant re-sort on already-sorted data.
    g = px.groupby("symbol", sort=False)

    px["ret_1d"]  = g["close"].pct_change(1)
    px["ret_5d"]  = g["close"].pct_change(5)
    px["ret_20d"] = g["close"].pct_change(20)

    # Realized volatility — Cython-optimized rolling path (no Python lambda overhead).
    px["rv_10d"] = g["ret_1d"].rolling(10).std().reset_index(level=0, drop=True)
    px["rv_20d"] = g["ret_1d"].rolling(20).std().reset_index(level=0, drop=True)

    # Intraday range and overnight gap — cache shift to avoid a second groupby pass.
    prev_close = g["close"].shift(1)
    px["range_pct"] = (px["high"] - px["low"]) / px["close"].replace(0, np.nan)
    px["gap_pct"]   = (px["open"] - prev_close) / prev_close

    # Volume
    px["vol_log"] = safe_log1p(px["volume"])
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
    Uses the same date-mapping approach as build_option_features so options on
    days with no price file (e.g. Monday after Friday) still get a valid close.
    """
    opt_dates = pd.DataFrame({"date": sorted(opt_feat["date"].unique())})
    px_dates  = pd.DataFrame({"price_date": sorted(px["date"].unique())})
    px_dates["date"] = px_dates["price_date"]
    date_map  = pd.merge_asof(
        opt_dates, px_dates,
        on="date", direction="backward", tolerance=pd.Timedelta("7 days"),
    )

    close_df = px[["symbol", "date", "close"]].rename(columns={"date": "price_date"})
    tmp      = opt_feat.merge(date_map, on="date", how="left")
    out      = tmp.merge(close_df, on=["symbol", "price_date"], how="left").drop(columns=["price_date"])
    out["moneyness"]     = out["close"] / out["strike"].replace(0, np.nan)
    out["log_moneyness"] = np.log(out["moneyness"].replace(0, np.nan))
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    return out
