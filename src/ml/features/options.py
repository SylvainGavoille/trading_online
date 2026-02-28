"""Feature engineering for options rows (merges underlying + portfolio context)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.utils import mid_price, safe_log1p


def categorize_option_rows(opt: pd.DataFrame, category: str) -> pd.Series:
    """
    Return a boolean mask selecting rows that belong to `category`.

    Supported categories
    --------------------
    long_premium  : buy calls or puts
    short_premium : sell puts (and optionally covered calls — see BacktestConfig)
    """
    cat = category.lower()
    if cat == "long_premium":
        return pd.Series(True, index=opt.index)
    if cat == "short_premium":
        return pd.Series(True, index=opt.index)
    raise ValueError(
        f"Unknown category '{category}'. "
        "Supported: 'long_premium', 'short_premium'."
    )


def build_option_features(
    opt: pd.DataFrame,
    und_feat: pd.DataFrame,
    portfolio: pd.DataFrame,
) -> pd.DataFrame:
    """
    Enrich the options table with:
      - option-level features (mid, spread, DTE, greeks/IV when present)
      - underlying features (ret, rv, trend …)
      - portfolio context (buying_power ratio, margin ratio)

    Parameters
    ----------
    opt       : raw options snapshot (from read_options)
    und_feat  : output of build_underlying_features
    portfolio : output of read_portfolio
    """
    opt = opt.copy()
    opt.rename(columns={"underlying": "symbol"}, inplace=True)

    # Option pricing
    opt["mid"]        = mid_price(opt)
    opt["spread"]     = (opt["ask"] - opt["bid"]).astype(float)
    opt["spread_pct"] = opt["spread"] / opt["mid"].replace(0, np.nan)

    # Days to expiry
    opt["dte"] = (opt["expiry"] - opt["date"]).dt.days.astype(int)

    # Merge underlying features.
    # Build a tiny date-mapping table (O(D) rows, not O(N)) so that each
    # options snapshot date resolves to the nearest prior price date — this
    # handles weekends/holidays where the options file (e.g. Monday) arrives
    # after the last price file (Friday).
    opt_dates = pd.DataFrame({"date": sorted(opt["date"].unique())})
    und_dates = pd.DataFrame({"price_date": sorted(und_feat["date"].unique())})
    und_dates["date"] = und_dates["price_date"]
    date_map  = pd.merge_asof(
        opt_dates, und_dates,
        on="date", direction="backward", tolerance=pd.Timedelta("7 days"),
    )  # columns: date, price_date (NaT when no price within 7 days)

    opt2   = opt.merge(date_map, on="date", how="left")
    merged = opt2.merge(
        und_feat.rename(columns={"date": "price_date"}),
        on=["symbol", "price_date"],
        how="left",
    ).drop(columns=["price_date"])

    # Merge portfolio (by date)
    p = portfolio.copy()
    merged = merged.merge(p, on="date", how="left")

    # Portfolio ratios
    merged["bp_to_netliq"]     = merged["buying_power"] / merged["net_liq"].replace(0, np.nan)
    merged["margin_to_netliq"] = merged["margin_used"]  / merged["net_liq"].replace(0, np.nan)

    # Greeks / IV (cast to float if present)
    for c in ["iv", "delta", "gamma", "vega", "theta"]:
        if c in merged.columns:
            merged[c] = merged[c].astype(float)

    # Right encoding
    merged["is_call"] = (merged["right"].astype(str).str.upper() == "C").astype(int)

    # Liquidity
    merged["log_oi"]      = safe_log1p(merged["openInterest"].astype(float))
    merged["log_opt_vol"] = safe_log1p(merged["volume"].astype(float))

    merged.replace([np.inf, -np.inf], np.nan, inplace=True)
    return merged
