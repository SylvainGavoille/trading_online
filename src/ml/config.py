"""BacktestConfig, TrainConfig and OptimizerConfig dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Multiplier applied to short-premium credit / trade cost to approximate the
# margin (capital) at risk. Shared by labels.py and optimizer.py.
MARGIN_PROXY_MULT: float = 5.0


@dataclass(frozen=True)
class BacktestConfig:
    slippage_bps: float = 10.0
    commission_per_contract: float = 0.65   # IBKR typical (per leg)
    min_oi: int = 50
    min_volume: int = 10
    max_spread_pct: float = 0.15            # (ask-bid)/mid
    max_trades_per_day: int = 3
    max_premium_spend_pct_bp: float = 0.05  # long: fraction of buying_power
    max_margin_add_pct_bp: float = 0.10     # short: fraction of buying_power (proxy)
    allow_naked_calls: bool = False


@dataclass(frozen=True)
class TrainConfig:
    num_leaves: int = 127
    learning_rate: float = 0.05
    n_estimators: int = 400          # early stopping caps actual trees; more headroom
    min_data_in_leaf: int = 100
    feature_fraction: float = 0.8
    bagging_fraction: float = 0.8
    bagging_freq: int = 1
    lambda_l2: float = 1.0
    force_col_wise: bool = True      # faster histogram build for small feature counts
    n_jobs: int = 1


@dataclass(frozen=True)
class OptimizerConfig:
    """Optimizer parameters loaded from config.yaml → ml_optimizer section."""
    prefer_ilp: bool = False
    max_trades_per_symbol: int = 1
    # Greek caps per category (None = uncapped)
    max_abs_delta_long: Optional[float] = None
    max_abs_vega_long: Optional[float] = None
    max_abs_delta_short: Optional[float] = None
    max_abs_vega_short: Optional[float] = None


def load_optimizer_config(yaml_path: Path) -> OptimizerConfig:
    """Parse the ml_optimizer section of config.yaml into an OptimizerConfig."""
    import yaml  # local import — keeps dataclass module import-free

    with open(yaml_path) as f:
        cfg = yaml.safe_load(f)

    sec = cfg.get("ml_optimizer", {})
    lp  = sec.get("long_premium",  {}) or {}
    sp  = sec.get("short_premium", {}) or {}

    return OptimizerConfig(
        prefer_ilp=bool(sec.get("prefer_ilp", False)),
        max_trades_per_symbol=int(sec.get("max_trades_per_symbol", 1)),
        max_abs_delta_long=_opt_float(lp.get("max_abs_portfolio_delta")),
        max_abs_vega_long=_opt_float(lp.get("max_abs_portfolio_vega")),
        max_abs_delta_short=_opt_float(sp.get("max_abs_portfolio_delta")),
        max_abs_vega_short=_opt_float(sp.get("max_abs_portfolio_vega")),
    )


def _opt_float(value) -> Optional[float]:
    """Return float or None (treats None/null/0 as uncapped)."""
    if value is None:
        return None
    try:
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None
