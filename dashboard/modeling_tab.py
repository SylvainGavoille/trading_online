"""
Modeling tab for the Quantum Trader dashboard.

Provides four sub-tabs:
  1. Portfolio Snapshot  — save today's IBKR account state
  2. Options Snapshot    — collect EOD option chains from IBKR
  3. ML Pipeline         — run walk-forward backtest + PuLP optimizer
  4. Results             — browse saved metrics, equity curves and coverage
"""

from __future__ import annotations

import sys
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Project root (dashboard/ is one level below root)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.utils import PORTFOLIO_DAILY_ROOT
from src.ml.data.portfolio import snapshot_from_ibkr, save_portfolio_snapshot
from gcs_data import (
    read_portfolio_history_from_gcs,
    read_options_coverage_from_gcs,
    read_ml_run_status,
    read_ml_summary_metrics,
    read_ml_equity_curves,
    read_ml_actions_summary,
    read_ml_actions_equity,
    read_ml_actions_picks,
    read_latest_recommendations,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uv_python() -> list[str]:
    """
    Return the command prefix to run Python in the uv virtual environment.
    -u forces unbuffered stdout/stderr so lines appear immediately when piped.
    """
    return [sys.executable, "-u"]


def _stream_subprocess(cmd: list[str], placeholder, max_lines: int = 60) -> int:
    """
    Run cmd via subprocess.Popen, stream stdout+stderr line-by-line into
    `placeholder` (a st.empty()), and return the exit code.
    """
    import os

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"  # prevent charmap errors on Windows
    env["PYTHONUTF8"] = "1"  # Python 3.7+ UTF-8 mode

    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=str(_PROJECT_ROOT),
            env=env,
        )
        for raw in proc.stdout:
            lines.append(raw.rstrip())
            placeholder.code("\n".join(lines[-max_lines:]), language="")
        proc.wait()
        return proc.returncode
    except Exception as exc:
        lines.append(f"[ERROR] {exc}")
        placeholder.code("\n".join(lines), language="")
        return 1


def _read_portfolio_history() -> Optional[pd.DataFrame]:
    """Read all portfolio_daily/ parquet files from GCS, return sorted DataFrame or None."""
    return read_portfolio_history_from_gcs()


def _read_options_coverage() -> Optional[pd.DataFrame]:
    """Return a DataFrame with (day, n_rows) from options_snapshot/ in GCS."""
    return read_options_coverage_from_gcs()



# ---------------------------------------------------------------------------
# Sub-tab: Portfolio Snapshot
# ---------------------------------------------------------------------------


def _render_portfolio_snapshot(ib_client) -> None:
    st.subheader("📋 Portfolio Snapshot")

    st.info(
        "**What this does:** Connects to IBKR and reads your current account state "
        "(net liquidation value, buying power, cash, margin used), then saves it as "
        "a dated record in `portfolio_daily/`.  \n\n"
        "Run this once per trading day **after market close**. "
        "The ML pipeline needs at least **100 days** of history before it can produce results."
    )

    connected = ib_client is not None and ib_client.isConnected()
    if not connected:
        st.warning("⚠️ IBKR is not connected. Connect from the Portfolio tab first.")

    if st.button(
        "▶ Collect Portfolio Snapshot",
        type="primary",
        disabled=not connected,
        use_container_width=True,
        key="btn_portfolio_snap",
    ):
        with st.spinner("Reading account data from IBKR…"):
            try:
                snap = snapshot_from_ibkr(ib_client)
                path = save_portfolio_snapshot(snap, PORTFOLIO_DAILY_ROOT)
                st.session_state["last_portfolio_snap"] = snap
                st.session_state["last_portfolio_path"] = str(path)
                st.success(f"✅ Saved → `{path}`")
            except Exception as exc:
                st.error(f"❌ Failed: {exc}")

    # Show last result
    snap = st.session_state.get("last_portfolio_snap")
    if snap:
        c1, c2, c3, c4 = st.columns(4)

        def _fmt(v):
            return f"${v:,.0f}" if v is not None else "—"

        c1.metric("Net Liquidation", _fmt(snap.get("net_liq")))
        c2.metric("Buying Power", _fmt(snap.get("buying_power")))
        c3.metric("Cash", _fmt(snap.get("cash")))
        c4.metric("Margin Used", _fmt(snap.get("margin_used")))

    st.divider()

    # History table
    st.markdown("#### History")
    df = _read_portfolio_history()
    if df is None or df.empty:
        st.caption("No portfolio snapshots saved yet.")
    else:
        display = df.copy()
        for col in ["net_liq", "buying_power", "cash", "margin_used"]:
            if col in display.columns:
                display[col] = display[col].map(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
                )
        st.dataframe(display.tail(14), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Sub-tab: Options Snapshot
# ---------------------------------------------------------------------------


def _render_options_snapshot() -> None:
    st.subheader("📊 Options Snapshot")

    st.info(
        "**What this does:** Fetches option chains (bid, ask, IV, volume, OI) "
        "from **Yahoo Finance** for the **top-N most liquid symbols** based on "
        "`price_historical/` volume. Greeks (delta/gamma/vega/theta) are not "
        "available from Yahoo and are always `None`.  \n\n"
        "Results are saved to `options_snapshot/` partitioned by date.  \n\n"
        "Typical run time: **5–15 minutes** for 30 symbols. "
        "In production this runs automatically via the GCP Cloud Run job at 22:20 NY time."
    )

    # Config widgets
    with st.expander("⚙️ Configuration", expanded=True):
        c1, c2 = st.columns(2)
        top_n = c1.number_input(
            "Top N symbols by volume", 5, 200, 50, step=5, key="opt_top_n"
        )
        max_exp = c2.selectbox(
            "Max expirations per symbol", [1, 2, 3, 4, 5], index=2, key="opt_max_exp"
        )
        dte_min = c1.slider("DTE min (days)", 0, 90, 7, key="opt_dte_min")
        dte_max = c2.slider("DTE max (days)", 7, 365, 90, key="opt_dte_max")
        moneyness = st.slider("Moneyness range ±%", 5, 50, 20, key="opt_moneyness")

    # One-time cleanup of empty parquet files (must run before first DuckDB query)
    with st.expander("🧹 Maintenance — Clean corrupt files", expanded=False):
        st.caption(
            "If `price_historical/` contains empty files left by failed downloads, "
            "DuckDB will refuse to scan it. Run this once to remove them."
        )
        c_clean1, c_clean2 = st.columns([3, 1])
        dry_run_clean = c_clean2.checkbox(
            "Dry run (preview only)", value=True, key="clean_dryrun"
        )
        if c_clean1.button(
            "🧹 Clean price_historical/", use_container_width=True, key="btn_clean"
        ):
            clean_placeholder = st.empty()
            cmd = _uv_python() + [
                str(_PROJECT_ROOT / "src" / "data" / "cleanup_price_historical.py"),
                "--verbose",
            ]
            if dry_run_clean:
                cmd.append("--dry_run")
            with st.spinner("Scanning for corrupt files…"):
                rc = _stream_subprocess(cmd, clean_placeholder, max_lines=40)
            if rc == 0:
                st.success("✅ Cleanup complete.")
            else:
                st.error("❌ Cleanup encountered errors.")

    # Preview symbol universe (dry-run — no IBKR needed)
    if st.button(
        "🔍 Preview Symbol Universe (no IBKR)",
        use_container_width=True,
        key="btn_preview",
    ):
        preview_placeholder = st.empty()
        cmd = _uv_python() + [
            str(_PROJECT_ROOT / "src" / "data" / "collect_options_snapshot.py"),
            "--dry_run",
            "--top_n",
            str(top_n),
        ]
        with st.spinner("Scanning price_historical…"):
            rc = _stream_subprocess(cmd, preview_placeholder, max_lines=20)
        if rc != 0:
            st.error("Preview failed — is price_historical populated?")

    st.divider()

    # Main collection button
    if st.button(
        "▶ Collect Options Snapshot",
        type="primary",
        use_container_width=True,
        key="btn_opt_collect",
    ):
        output_placeholder = st.empty()
        cmd = _uv_python() + [
            str(_PROJECT_ROOT / "src" / "data" / "collect_options_snapshot.py"),
            "--top_n",
            str(top_n),
            "--dte_min",
            str(dte_min),
            "--dte_max",
            str(dte_max),
            "--max_exp",
            str(max_exp),
            "--moneyness",
            str(moneyness),
        ]
        with st.spinner("Collecting options snapshot — this may take 5–15 minutes…"):
            rc = _stream_subprocess(cmd, output_placeholder, max_lines=60)
        if rc == 0:
            st.success("✅ Options snapshot collection complete.")
            st.session_state.pop("opt_coverage_cache", None)  # invalidate cache
        else:
            st.error("❌ Collection finished with errors (see output above).")

    st.divider()

    # Recent coverage
    st.markdown("#### Coverage (options_snapshot/)")
    if "opt_coverage_cache" not in st.session_state:
        st.session_state["opt_coverage_cache"] = _read_options_coverage()
    cov = st.session_state["opt_coverage_cache"]
    if cov is None or cov.empty:
        st.caption("No options snapshots saved yet.")
    else:
        last = cov.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("Latest snapshot date", str(last["day"]))
        c2.metric("Rows saved", f"{int(last['n_rows']):,}")
        c3.metric("Days collected", len(cov))
        import plotly.express as px

        fig = px.bar(
            cov.tail(30),
            x="day",
            y="n_rows",
            title="Option rows per day (last 30)",
            labels={"day": "Date", "n_rows": "Rows"},
        )
        fig.update_layout(margin=dict(t=35, b=0))
        st.plotly_chart(fig, use_container_width=True, key="opt_snap_coverage_chart")


# ---------------------------------------------------------------------------
# Sub-tab: ML Pipeline
# ---------------------------------------------------------------------------


def _render_ml_pipeline() -> None:
    st.subheader("🚀 ML Pipeline")

    st.info(
        "**What this does:** Trains a **LightGBM LambdaRank** model that scores "
        "option contracts by expected risk-adjusted return. Walk-forward folds are used: "
        "each fold trains on all past data, then evaluates on the next period.  \n\n"
        "The **PuLP optimizer** then selects the best feasible portfolio from the "
        "model's top candidates each day, respecting buying-power and greek constraints "
        "from `config.yaml`.  \n\n"
        "Results (fold PnL, Sharpe) are saved to `ml_output/`."
    )

    # Config
    with st.expander("⚙️ Configuration", expanded=True):
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start date", date(2025, 2, 20), key="pipe_start")
        end_date = c2.date_input("End date", date.today(), key="pipe_end")
        horizons = c1.multiselect(
            "Horizons (days)", [2, 5, 10, 21], default=[2, 5, 10, 21], key="pipe_h"
        )
        categories = c2.multiselect(
            "Categories",
            ["long_premium", "short_premium"],
            default=["long_premium", "short_premium"],
            key="pipe_cat",
        )
        topk = c1.number_input("Top-K trades / day", 1, 10, 3, key="pipe_topk")

        with st.expander("Advanced", expanded=False):
            a1, a2, a3 = st.columns(3)
            min_train = a1.number_input(
                "Min train days", 20, 500, 80, key="pipe_mintrain"
            )
            test_days = a2.number_input("Test days", 5, 120, 20, key="pipe_testdays")
            step_days = a3.number_input("Step days", 5, 120, 20, key="pipe_stepdays")

    if not horizons:
        st.warning("Select at least one horizon.")
        return
    if not categories:
        st.warning("Select at least one category.")
        return

    if st.button(
        "▶ Run ML Pipeline",
        type="primary",
        use_container_width=True,
        key="btn_pipeline",
    ):
        output_placeholder = st.empty()
        cmd = _uv_python() + [
            str(_PROJECT_ROOT / "src" / "ml" / "pipeline.py"),
            "--start",
            start_date.isoformat(),
            "--end",
            end_date.isoformat(),
            "--horizons",
            *[str(h) for h in horizons],
            "--categories",
            *categories,
            "--topk",
            str(topk),
            "--min_train_days",
            str(min_train),
            "--test_days",
            str(test_days),
            "--step_days",
            str(step_days),
        ]
        with st.spinner("Running ML pipeline — this may take several minutes…"):
            rc = _stream_subprocess(cmd, output_placeholder, max_lines=80)
        if rc == 0:
            st.success("✅ Pipeline complete — check the **Results** tab.")
            st.session_state.pop("ml_summary_cache", None)  # force refresh
        else:
            st.error("❌ Pipeline finished with errors (see output above).")


# ---------------------------------------------------------------------------
# Sub-tab: Results
# ---------------------------------------------------------------------------


def _render_equity_chart(eq: pd.DataFrame, title: str, chart_key: str) -> None:
    """Render a cumulative PnL chart + 3 summary metrics for an equity DataFrame."""
    import plotly.graph_objects as go

    eq = eq.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq["cum_pnl"] = eq["pnl"].cumsum()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=eq["date"],
            y=eq["cum_pnl"],
            mode="lines",
            name="Cumulative PnL",
            line={"color": "#00b4d8"},
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="PnL ($)",
        margin={"t": 40, "b": 0},
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)
    c1, c2, c3 = st.columns(3)
    trades_col = "n_trades" if "n_trades" in eq.columns else "n_picks"
    c1.metric("Total PnL", f"${eq['pnl'].sum():+,.0f}")
    c2.metric(
        "Annualised Sharpe",
        f"{(eq['pnl'].mean() / (eq['pnl'].std(ddof=1) + 1e-9)) * (252 ** 0.5):.2f}",
    )
    c3.metric("Total Trades", f"{int(eq[trades_col].sum()):,}" if trades_col in eq.columns else "—")


def _fetch_sector_info(symbols: list[str]) -> dict[str, dict]:
    """Fetch sector and industry from Yahoo Finance for each symbol."""
    import yfinance as yf
    result: dict[str, dict] = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            result[sym] = {
                "sector": info.get("sector") or "—",
                "industry": info.get("industry") or "—",
            }
        except Exception:
            result[sym] = {"sector": "—", "industry": "—"}
    return result


def _compute_hit_rates(picks: pd.DataFrame) -> pd.DataFrame:
    """From daily_picks backtest data, compute per-symbol win rate and avg return."""
    if picks is None or picks.empty or "fwd_ret" not in picks.columns:
        return pd.DataFrame(columns=["symbol", "win_rate", "avg_return", "n_appearances"])
    g = picks.groupby("symbol")["fwd_ret"]
    hr = pd.DataFrame({
        "win_rate": g.apply(lambda x: (x > 0).mean()),
        "avg_return": g.mean(),
        "n_appearances": g.count(),
    }).reset_index()
    return hr


def _render_backtest_picks(actions: Optional[pd.DataFrame]) -> None:
    """Show top stocks from backtest history when live recommendations aren't available yet."""
    st.markdown("#### 📋 Most Picked Stocks (backtest history)")
    st.caption(
        "Live recommendations aren't available yet — showing which stocks the model "
        "selected most often during the walk-forward backtest. "
        "This is a proxy for what the model tends to favour."
    )

    # Determine available horizons from actions summary
    horizons = []
    if actions is not None and "horizon" in actions.columns:
        horizons = sorted(actions["horizon"].unique().tolist())
    if not horizons:
        st.caption("No backtest data available yet.")
        return

    sel_h = st.selectbox(
        "Select horizon",
        horizons,
        format_func=lambda h: f"H={h}  (~{h} trading days forward)",
        key="bt_picks_horizon",
    )

    picks_key = f"ml_picks_cache_h{sel_h}"
    if picks_key not in st.session_state:
        st.session_state[picks_key] = read_ml_actions_picks(sel_h)
    picks_df = st.session_state[picks_key]

    if picks_df is None or picks_df.empty:
        st.info(
            f"No per-stock backtest data for H={sel_h} yet.  \n"
            "This file (`daily_picks.parquet`) is generated by the updated pipeline.  \n"
            "**Next step:** run `deploy.ps1` then trigger the Cloud Run job manually."
        )
        return

    hr = _compute_hit_rates(picks_df)
    hr = hr.sort_values("n_appearances", ascending=False).reset_index(drop=True)
    hr["rank"] = hr.index + 1
    hr["win_rate_pct"] = (hr["win_rate"] * 100).round(1)
    hr["avg_return_pct"] = (hr["avg_return"] * 100).round(2)

    display = hr[["rank", "symbol", "n_appearances", "win_rate_pct", "avg_return_pct"]].head(50)
    display.columns = ["rank", "symbol", "appearances", "win_rate %", "avg_return %"]

    styled = (
        display.style
        .format({"win_rate %": "{:.1f}", "avg_return %": "{:+.2f}"})
        .background_gradient(subset=["win_rate %", "avg_return %"], cmap="RdYlGn")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(
        f"{len(hr)} unique stocks appeared across all backtest folds for H={sel_h}. "
        "High `win_rate %` + positive `avg_return %` = stock the model consistently ranked well."
    )


def _render_recommendations() -> None:
    """Show today's stock recommendations from the actions pipeline."""
    st.markdown("#### 🎯 Today's Stock Recommendations")

    if "ml_recs_cache" not in st.session_state:
        st.session_state["ml_recs_cache"] = read_latest_recommendations()
    recs = st.session_state["ml_recs_cache"]

    if recs is None or recs.empty:
        # No recommendations yet — show status and backtest picks as fallback
        st.warning(
            "**No live recommendations yet** — the updated pipeline hasn't run.  \n"
            "To generate them: run `deploy.ps1`, then trigger the Cloud Run job."
        )
        actions = st.session_state.get("ml_actions_cache")
        if actions is None:
            actions = read_ml_actions_summary()
            st.session_state["ml_actions_cache"] = actions
        _render_backtest_picks(actions)
        return

    run_date = recs["run_date"].iloc[0] if "run_date" in recs.columns else "unknown"
    price_date = recs["price_date"].iloc[0] if "price_date" in recs.columns else "unknown"
    horizons_avail = sorted(recs["horizon"].unique().tolist())

    st.caption(
        f"Model run date: **{run_date}** · Price date used: **{price_date}** · "
        f"Horizons available: {', '.join(f'H={h}' for h in horizons_avail)}"
    )

    with st.expander("ℹ️ How to read recommendations", expanded=False):
        st.markdown("""
**Each row is a stock the model expects to outperform over the next N trading days.**

| Column | Meaning |
|---|---|
| `rank` | 1 = highest expected return for this horizon |
| `symbol` | Stock ticker |
| `expected_gain` | Score expressed as a percentage — the model's predicted forward return |
| `close` | Closing price on `price_date` — the last price the model saw |
| `win_rate` | % of backtest appearances where this stock had a positive return (historical, not a guarantee) |
| `avg_return` | Average actual return across all backtest appearances for this symbol |
| `n_appearances` | How many times this stock appeared in the top-K picks during the backtest |
| `sector` / `industry` | From Yahoo Finance (loaded on demand) |

**Important caveats:**
- These are **model predictions**, not financial advice.
- The model is trained on historical price patterns only — it has no macro/news awareness.
- Use alongside your own analysis. A `sharpe_proxy > 1` in the backtest is a necessary but not sufficient signal.
        """)

    sel_h = st.selectbox(
        "Select horizon",
        horizons_avail,
        format_func=lambda h: f"H={h}  (~{h} trading days forward)",
        key="recs_horizon_sel",
    )

    subset = recs[recs["horizon"] == sel_h].copy()
    if subset.empty:
        st.caption(f"No recommendations for H={sel_h}.")
        return

    # Add % expected gain column
    if "score" in subset.columns:
        subset["expected_gain"] = subset["score"] * 100

    # Merge historical hit rates from backtest picks
    picks_key = f"ml_picks_cache_h{sel_h}"
    if picks_key not in st.session_state:
        st.session_state[picks_key] = read_ml_actions_picks(sel_h)
    picks_df = st.session_state[picks_key]

    if picks_df is not None and not picks_df.empty:
        hr = _compute_hit_rates(picks_df)
        subset = subset.merge(hr, on="symbol", how="left")

    # Sector / industry (on-demand)
    sector_key = f"ml_sector_cache_h{sel_h}"
    sector_data = st.session_state.get(sector_key)

    if sector_data is None:
        if st.button("🏢 Load sector & industry info (Yahoo Finance)", key=f"btn_load_sector_h{sel_h}"):
            with st.spinner(f"Fetching sector info for {len(subset)} stocks…"):
                sector_data = _fetch_sector_info(subset["symbol"].tolist())
                st.session_state[sector_key] = sector_data

    if sector_data:
        subset["sector"] = subset["symbol"].map(lambda s: sector_data.get(s, {}).get("sector", "—"))
        subset["industry"] = subset["symbol"].map(lambda s: sector_data.get(s, {}).get("industry", "—"))

    # Build display table
    display_cols = [c for c in [
        "rank", "symbol", "expected_gain", "close",
        "win_rate", "avg_return", "n_appearances",
        "sector", "industry",
    ] if c in subset.columns]

    fmt: dict = {"close": "{:.2f}"}
    if "expected_gain" in subset.columns:
        fmt["expected_gain"] = "{:+.2f}%"
    if "win_rate" in subset.columns:
        fmt["win_rate"] = "{:.0%}"
    if "avg_return" in subset.columns:
        fmt["avg_return"] = "{:+.4f}"

    gradient_cols = [c for c in ["expected_gain", "win_rate"] if c in subset.columns]
    styled = subset[display_cols].style.format(fmt)
    if gradient_cols:
        styled = styled.background_gradient(subset=gradient_cols, cmap="RdYlGn")

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(f"{len(subset)} stocks ranked for H={sel_h}")

    # Per-stock explanation
    if "explanation" in subset.columns:
        st.markdown("**Why was this stock selected?**")
        exp_sym = st.selectbox(
            "Pick a stock to explain",
            subset["symbol"].tolist(),
            key="recs_explain_sym",
            label_visibility="collapsed",
        )
        row = subset[subset["symbol"] == exp_sym].iloc[0]
        gain_str = f"{row['expected_gain']:+.2f}%" if "expected_gain" in subset.columns else ""
        wr_str = f" · win rate {row['win_rate']:.0%}" if "win_rate" in subset.columns and pd.notna(row.get("win_rate")) else ""
        st.info(
            f"**{exp_sym}** — rank #{int(row['rank'])}  {gain_str}{wr_str}\n\n"
            f"Top drivers: **{row['explanation']}**\n\n"
            f"↑ = feature pushed the score up (bullish signal)  ·  ↓ = feature pulled it down"
        )

    # Explore a stock in the Exploration tab
    st.markdown("**Explore a stock from this list**")
    explore_col1, explore_col2 = st.columns([3, 1])
    explore_sym = explore_col1.selectbox(
        "Symbol",
        subset["symbol"].tolist(),
        key="recs_explore_sym",
        label_visibility="collapsed",
    )
    if explore_col2.button("📈 Open in Exploration", key="btn_recs_explore", use_container_width=True):
        st.session_state["quick_selected_symbol"] = explore_sym
        st.session_state["auto_load_data"] = True
        st.info(f"Switch to the **🔍 Exploration** tab to view **{explore_sym}**.")

    st.divider()


def _render_results() -> None:
    st.subheader("📈 Results")

    with st.expander("ℹ️ How to read this page", expanded=False):
        st.markdown("""
**This page shows outputs produced by the daily Cloud Run job** (`quantum-daily-ml`, runs every weekday at 22:20 NY time).

---

#### 🗂️ Data pipeline overview
```
price_historical/  (6 471 symbols, daily OHLCV)
        ↓
Actions Pipeline  →  LightGBM regressor per horizon
        ↓                 predicts forward return, ranks top-K stocks
ml_output/actions/
  summary.parquet          ← fold metrics for all horizons
  backtests/h=5/
    fold_metrics.parquet   ← per-fold PnL, Sharpe, trade count
    fold_equity.parquet    ← daily equity curve
  models/h=5/
    model_fold*.txt        ← saved LightGBM models
    feature_cols.json      ← list of features used
```

---

#### 📊 Actions Fold Metrics table — column guide

| Column | Meaning |
|---|---|
| `horizon` | Prediction horizon in trading days (e.g. 5 = 1 week forward return) |
| `fold` | Walk-forward fold index. Each fold trains on all past data, tests on next period. |
| `test_start / test_end` | Date range the fold was evaluated on (out-of-sample) |
| `total_pnl` | Sum of daily average returns across the test period (not dollar P&L — it's a % return proxy) |
| `sharpe_proxy` | Annualised Sharpe ratio: `mean(daily_pnl) / std(daily_pnl) × √252`. **>1 is good, >2 is very good.** |
| `n_picks` | Total number of stock selections made across the test period |
| `n_days` | Number of trading days in the test period |

---

#### 📈 Equity curve — how to read it

- The curve shows **cumulative sum of daily PnL** across all walk-forward test folds
- Each fold is evaluated **out-of-sample** (model never saw the test data during training)
- A rising curve = the model ranked high-return stocks above low-return ones on average
- **Total PnL** and **Annualised Sharpe** are shown below the chart

> ⚠️ PnL values are **fractional returns** (e.g. +0.05 = +5% average across top-K picks that day), not dollar amounts. To estimate dollar P&L, multiply by your position size.

---

#### 🔄 Refreshing data
Results are cached for the session. To reload fresh data from GCS, **reload the page**.
        """)

    import plotly.express as px

    # ── Last run status ────────────────────────────────────────────────────
    status = read_ml_run_status()
    if status:
        elapsed = status.get("elapsed_minutes", "?")
        stopped = status.get("stopped_early", False)
        combos = status.get("completed_combos", [])
        badge = "⚠️ stopped early" if stopped else "✅ completed"
        st.caption(
            f"Last GCP run: {badge} · {elapsed:.1f} min · combos: {', '.join(combos) or '—'}"
        )

    # ── Portfolio history ──────────────────────────────────────────────────
    with st.expander("📋 Portfolio History", expanded=True):
        df_port = _read_portfolio_history()
        if df_port is None or df_port.empty:
            st.caption("No portfolio snapshots in GCS yet.")
        else:
            df_port["date"] = pd.to_datetime(df_port["date"])
            cols_avail = [c for c in ["net_liq", "buying_power", "cash"] if c in df_port.columns]
            if cols_avail:
                fig = px.line(
                    df_port,
                    x="date",
                    y=cols_avail,
                    title="Account History",
                    labels={"value": "USD", "date": "Date", "variable": ""},
                )
                fig.update_layout(margin={"t": 35, "b": 0}, legend={"orientation": "h"})
                st.plotly_chart(fig, use_container_width=True, key="res_portfolio_history_chart")
            c1, c2, c3 = st.columns(3)
            last = df_port.iloc[-1]
            c1.metric("Latest Net Liq", f"${last.get('net_liq', 0):,.0f}")
            c2.metric("Latest Buying Power", f"${last.get('buying_power', 0):,.0f}")
            c3.metric("Snapshots saved", len(df_port))

    # ── Options coverage ──────────────────────────────────────────────────
    with st.expander("📊 Options Snapshot Coverage", expanded=False):
        cov = _read_options_coverage()
        if cov is None or cov.empty:
            st.caption("No options snapshots in GCS yet.")
        else:
            fig = px.bar(
                cov.tail(30),
                x="day",
                y="n_rows",
                title="Option rows per day (last 30)",
                labels={"day": "Date", "n_rows": "Rows"},
            )
            fig.update_layout(margin={"t": 35, "b": 0})
            st.plotly_chart(fig, use_container_width=True, key="res_options_coverage_chart")
            st.caption(f"{len(cov)} days collected · latest: {cov.iloc[-1]['day']}")

    # ── Options ML pipeline results ────────────────────────────────────────
    st.markdown("#### Options ML Pipeline")

    summary = st.session_state.get("ml_summary_cache")
    if summary is None:
        summary = read_ml_summary_metrics()
    if summary is None:
        st.info(
            "No options ML results in GCS yet. "
            "They appear after the first Cloud Run job completes."
        )
    else:
        st.session_state["ml_summary_cache"] = summary

        display_cols = [
            c for c in
            ["category", "horizon", "fold", "test_start", "test_end",
             "total_pnl", "sharpe_proxy", "n_trades", "n_days"]
            if c in summary.columns
        ]
        with st.expander("📊 Fold Metrics", expanded=True):
            st.dataframe(
                summary[display_cols]
                .sort_values(["category", "horizon", "test_end"])
                .style.format({"total_pnl": "{:+,.0f}", "sharpe_proxy": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

        if {"total_pnl", "sharpe_proxy", "n_trades"}.issubset(summary.columns):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total PnL (all folds)", f"${summary['total_pnl'].sum():+,.0f}")
            c2.metric("Avg Sharpe", f"{summary['sharpe_proxy'].mean():.2f}")
            c3.metric("Total Trades", f"{int(summary['n_trades'].sum()):,}")
            c4.metric("Folds evaluated", len(summary))

        st.markdown("**Equity Curves**")
        combos = summary[["category", "horizon"]].drop_duplicates()
        sel_c1, sel_c2 = st.columns(2)
        sel_cat = sel_c1.selectbox("Category", combos["category"].unique().tolist(), key="res_cat")
        sel_h = sel_c2.selectbox(
            "Horizon", sorted(combos["horizon"].unique().tolist()), key="res_h"
        )
        eq = read_ml_equity_curves(sel_cat, sel_h)
        if eq is None:
            st.caption(f"No equity data for {sel_cat} H={sel_h}.")
        else:
            _render_equity_chart(eq, f"Cumulative PnL — {sel_cat}  H={sel_h}", "res_equity_chart")

    st.divider()

    # ── Actions pipeline results ───────────────────────────────────────────
    st.markdown("#### Actions Pipeline (price-only)")

    actions = st.session_state.get("ml_actions_cache")
    if actions is None:
        actions = read_ml_actions_summary()
    if actions is None:
        st.info("No actions pipeline results in GCS yet.")
    else:
        st.session_state["ml_actions_cache"] = actions

        act_cols = [
            c for c in ["horizon", "fold", "test_start", "test_end",
                         "total_pnl", "sharpe_proxy", "n_picks", "n_days"]
            if c in actions.columns
        ]
        with st.expander("📊 Actions Fold Metrics", expanded=True):
            st.caption(
                "Each row is one out-of-sample test fold. "
                "`total_pnl` = sum of daily avg returns (fractional, not $). "
                "`sharpe_proxy` = annualised Sharpe (>1 good, >2 very good). "
                "`n_picks` = total stock selections made."
            )
            st.dataframe(
                actions[act_cols].sort_values(["horizon", "test_end"])
                .style.format({"total_pnl": "{:+.4f}", "sharpe_proxy": "{:.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

        if "horizon" in actions.columns:
            horizons_available = sorted(actions["horizon"].unique().tolist())
            sel_ah = st.selectbox(
                "Select horizon (trading days)",
                horizons_available,
                format_func=lambda h: f"H={h}  (~{h} trading days forward)",
                key="res_act_h",
            )
            eq_act = read_ml_actions_equity(sel_ah)
            if eq_act is None:
                st.caption(f"No equity data for H={sel_ah}.")
            else:
                st.caption(
                    "Cumulative sum of daily average returns across all out-of-sample folds. "
                    "Rising = model consistently ranked better stocks higher."
                )
                _render_equity_chart(
                    eq_act, f"Actions Cumulative PnL — H={sel_ah}", "res_actions_equity_chart"
                )

    st.divider()
    _render_recommendations()


# ---------------------------------------------------------------------------
# Public entrypoint called from dashboard_app.py
# ---------------------------------------------------------------------------


def render_modeling_tab(ib_client) -> None:
    st.header("🤖 Modeling")

    tab_res, tab_port, tab_opt = st.tabs(
        [
            "📈 Results",
            "📋 Portfolio Snapshot",
            "📊 Options Snapshot",
        ]
    )

    with tab_res:
        _render_results()

    with tab_port:
        _render_portfolio_snapshot(ib_client)

    with tab_opt:
        _render_options_snapshot()
