"""ILP / greedy optimizer for option trade selection (post-model)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import pulp  # type: ignore
    _HAS_PULP = True
except Exception:
    _HAS_PULP = False


# ---------------------------------------------------------------------------
# Runtime constraint bundle (built per trading day)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OptimizerConstraints:
    max_trades: int = 3
    max_trades_per_symbol: int = 1

    # Budget caps (fraction of buying_power already converted to $)
    max_premium: float = 0.0        # long_premium: total debit cap
    max_margin_proxy: float = 0.0   # short_premium: total margin proxy cap

    # Greek caps — optional, None = uncapped
    max_abs_portfolio_delta: Optional[float] = None
    max_abs_portfolio_vega: Optional[float] = None

    # Sector caps: {sector_name: dollar_budget}  — optional
    sector_budget_caps: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_trade_costs(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["multiplier"] = pd.to_numeric(
        out.get("multiplier", 100), errors="coerce"
    ).fillna(100).astype(float)
    out["mid"] = pd.to_numeric(out["mid"], errors="coerce").astype(float)
    out["trade_cost"]         = (out["mid"] * out["multiplier"]).clip(lower=0.0)
    out["trade_margin_proxy"] = (out["trade_cost"].abs() * 5.0).clip(lower=0.0)
    return out


def _sector_of(row: pd.Series, has_sector: bool) -> str:
    if has_sector and pd.notna(row.get("sector")):
        return str(row["sector"])
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Greedy optimizer
# ---------------------------------------------------------------------------

def optimize_trades_greedy(
    candidates: pd.DataFrame,
    category: str,
    cons: OptimizerConstraints,
) -> pd.DataFrame:
    """Greedy selection respecting all hard constraints."""
    df = _compute_trade_costs(candidates)
    df = df.sort_values("pred_score", ascending=False).reset_index(drop=True)

    has_sector = "sector" in df.columns
    cat = category.lower()

    chosen: List[pd.Series] = []
    used_symbols: Dict[str, int] = {}
    used_sector_budget: Dict[str, float] = {}
    used_cost   = 0.0
    used_margin = 0.0
    used_delta  = 0.0
    used_vega   = 0.0

    for _, row in df.iterrows():
        if len(chosen) >= cons.max_trades:
            break

        sym = str(row["symbol"])
        if used_symbols.get(sym, 0) >= cons.max_trades_per_symbol:
            continue

        # Budget
        if cat == "long_premium":
            if cons.max_premium > 0 and used_cost + float(row["trade_cost"]) > cons.max_premium:
                continue
        elif cat == "short_premium":
            if cons.max_margin_proxy > 0 and used_margin + float(row["trade_margin_proxy"]) > cons.max_margin_proxy:
                continue

        # Greek caps
        d = float(row["delta"]) if ("delta" in df.columns and pd.notna(row.get("delta"))) else 0.0
        v = float(row["vega"])  if ("vega"  in df.columns and pd.notna(row.get("vega")))  else 0.0

        if cons.max_abs_portfolio_delta is not None:
            if abs(used_delta + d) > cons.max_abs_portfolio_delta:
                continue
        if cons.max_abs_portfolio_vega is not None:
            if abs(used_vega + v) > cons.max_abs_portfolio_vega:
                continue

        # Sector caps
        if cons.sector_budget_caps is not None:
            sec = _sector_of(row, has_sector)
            cap = cons.sector_budget_caps.get(sec)
            if cap is not None:
                add = float(row["trade_cost"]) if cat == "long_premium" else float(row["trade_margin_proxy"])
                if used_sector_budget.get(sec, 0.0) + add > cap:
                    continue

        # Accept
        chosen.append(row)
        used_symbols[sym] = used_symbols.get(sym, 0) + 1

        if cat == "long_premium":
            used_cost += float(row["trade_cost"])
        else:
            used_margin += float(row["trade_margin_proxy"])

        used_delta += d
        used_vega  += v

        if cons.sector_budget_caps is not None:
            sec = _sector_of(row, has_sector)
            add = float(row["trade_cost"]) if cat == "long_premium" else float(row["trade_margin_proxy"])
            used_sector_budget[sec] = used_sector_budget.get(sec, 0.0) + add

    if not chosen:
        return candidates.iloc[0:0].copy()

    out = pd.DataFrame(chosen).copy()
    out["selected"] = 1
    return out


# ---------------------------------------------------------------------------
# ILP optimizer (PuLP)
# ---------------------------------------------------------------------------

def optimize_trades_ilp(
    candidates: pd.DataFrame,
    category: str,
    cons: OptimizerConstraints,
) -> pd.DataFrame:
    """ILP optimizer via PuLP.  Falls back to greedy if PuLP unavailable."""
    if not _HAS_PULP:
        return optimize_trades_greedy(candidates, category, cons)

    df = _compute_trade_costs(candidates).reset_index(drop=True)

    # Pre-trim for speed on large option chains
    MAX_CAND = 2000
    if len(df) > MAX_CAND:
        df = df.nlargest(MAX_CAND, "pred_score").reset_index(drop=True)

    n = len(df)
    prob = pulp.LpProblem("OptionTradeSelection", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary) for i in range(n)]

    scores = df["pred_score"].astype(float).fillna(-1e9).to_numpy()
    prob += pulp.lpSum(scores[i] * x[i] for i in range(n))

    # Max trades
    prob += pulp.lpSum(x) <= int(cons.max_trades)

    # Per-symbol cap
    sym_list = df["symbol"].astype(str).to_list()
    for sym in set(sym_list):
        idx = [i for i, s in enumerate(sym_list) if s == sym]
        prob += pulp.lpSum(x[i] for i in idx) <= int(cons.max_trades_per_symbol)

    # Budget
    cat = category.lower()
    if cat == "long_premium" and cons.max_premium > 0:
        costs = df["trade_cost"].astype(float).to_numpy()
        prob += pulp.lpSum(costs[i] * x[i] for i in range(n)) <= float(cons.max_premium)

    if cat == "short_premium" and cons.max_margin_proxy > 0:
        margins = df["trade_margin_proxy"].astype(float).to_numpy()
        prob += pulp.lpSum(margins[i] * x[i] for i in range(n)) <= float(cons.max_margin_proxy)

    # Delta cap (absolute via two inequalities)
    if cons.max_abs_portfolio_delta is not None and "delta" in df.columns:
        deltas = pd.to_numeric(df["delta"], errors="coerce").fillna(0.0).to_numpy()
        cap = float(cons.max_abs_portfolio_delta)
        prob += pulp.lpSum(deltas[i] * x[i] for i in range(n)) <=  cap
        prob += pulp.lpSum(deltas[i] * x[i] for i in range(n)) >= -cap

    # Vega cap
    if cons.max_abs_portfolio_vega is not None and "vega" in df.columns:
        vegas = pd.to_numeric(df["vega"], errors="coerce").fillna(0.0).to_numpy()
        cap = float(cons.max_abs_portfolio_vega)
        prob += pulp.lpSum(vegas[i] * x[i] for i in range(n)) <=  cap
        prob += pulp.lpSum(vegas[i] * x[i] for i in range(n)) >= -cap

    # Sector caps
    if cons.sector_budget_caps is not None and "sector" in df.columns:
        sectors = df["sector"].astype(str).fillna("UNKNOWN").to_list()
        w = df["trade_cost"].astype(float).to_numpy() if cat == "long_premium" \
            else df["trade_margin_proxy"].astype(float).to_numpy()
        for sec, cap in cons.sector_budget_caps.items():
            idx = [i for i, s in enumerate(sectors) if s == sec]
            if idx:
                prob += pulp.lpSum(w[i] * x[i] for i in idx) <= float(cap)

    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=5))

    selected = [
        i for i in range(n)
        if pulp.value(x[i]) is not None and pulp.value(x[i]) > 0.5
    ]
    if not selected:
        return candidates.iloc[0:0].copy()

    out = df.iloc[selected].copy()
    out["selected"] = 1
    return out


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def optimize_trades(
    candidates: pd.DataFrame,
    category: str,
    cons: OptimizerConstraints,
    prefer_ilp: bool = True,
) -> pd.DataFrame:
    """Select trades via ILP (if available and prefer_ilp) or greedy."""
    if candidates.empty:
        return candidates.copy()
    if prefer_ilp and _HAS_PULP:
        return optimize_trades_ilp(candidates, category, cons)
    return optimize_trades_greedy(candidates, category, cons)


# ---------------------------------------------------------------------------
# Constraint builder (called per trading day from backtest_ranker)
# ---------------------------------------------------------------------------

def build_constraints(
    portfolio_row: "pd.Series",
    category: str,
    bt_cfg,           # BacktestConfig — provides budget pct_bp values
    opt_cfg,          # OptimizerConfig — provides per_symbol cap + greek caps
    topk: int,
) -> OptimizerConstraints:
    """Convert portfolio snapshot + configs into OptimizerConstraints."""
    import numpy as np

    bp = float(portfolio_row.get("buying_power", np.nan))
    if not np.isfinite(bp) or bp <= 0:
        # No budget — return a zero-budget constraint that will select nothing
        return OptimizerConstraints(max_trades=topk, max_premium=0.0, max_margin_proxy=0.0)

    cat = category.lower()
    if cat == "long_premium":
        max_premium    = bt_cfg.max_premium_spend_pct_bp * bp
        max_margin     = 0.0
        delta_cap      = opt_cfg.max_abs_delta_long
        vega_cap       = opt_cfg.max_abs_vega_long
    else:  # short_premium
        max_premium    = 0.0
        max_margin     = bt_cfg.max_margin_add_pct_bp * bp
        delta_cap      = opt_cfg.max_abs_delta_short
        vega_cap       = opt_cfg.max_abs_vega_short

    return OptimizerConstraints(
        max_trades=int(topk),
        max_trades_per_symbol=int(opt_cfg.max_trades_per_symbol),
        max_premium=float(max_premium),
        max_margin_proxy=float(max_margin),
        max_abs_portfolio_delta=delta_cap,
        max_abs_portfolio_vega=vega_cap,
    )
