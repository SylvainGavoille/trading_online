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
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Project root (dashboard/ is one level below root)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.ml.utils import PORTFOLIO_DAILY_ROOT, OPTIONS_SNAPSHOT_ROOT
from src.ml.data.portfolio import snapshot_from_ibkr, save_portfolio_snapshot


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
    """Read all portfolio_daily/ parquet files, return sorted DataFrame or None."""
    if not PORTFOLIO_DAILY_ROOT.exists():
        return None
    files = list(PORTFOLIO_DAILY_ROOT.glob("**/*.parquet"))
    if not files:
        return None
    try:
        import duckdb

        glob = PORTFOLIO_DAILY_ROOT.as_posix() + "/**/*.parquet"
        df = duckdb.sql(
            f"""
            SELECT date, cash, buying_power, net_liq, margin_used
            FROM read_parquet('{glob}', hive_partitioning=true)
            ORDER BY date
            """
        ).df()
        return df
    except Exception:
        return None


def _read_options_coverage() -> Optional[pd.DataFrame]:
    """Return a DataFrame with (day, n_rows) from options_snapshot/."""
    if not OPTIONS_SNAPSHOT_ROOT.exists():
        return None
    files = list(OPTIONS_SNAPSHOT_ROOT.glob("**/*.parquet"))
    if not files:
        return None
    try:
        import duckdb

        glob = OPTIONS_SNAPSHOT_ROOT.as_posix() + "/**/*.parquet"
        df = duckdb.sql(
            f"""
            SELECT day, COUNT(*) AS n_rows
            FROM read_parquet('{glob}', hive_partitioning=true)
            GROUP BY day ORDER BY day
        """
        ).df()
        return df
    except Exception as exc:
        st.warning(f"⚠️ Could not read options coverage: {exc}")
        return None


def _read_summary_metrics() -> Optional[pd.DataFrame]:
    path = _PROJECT_ROOT / "ml_output" / "summary_metrics.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _read_equity_curves(category: str, horizon: int) -> Optional[pd.DataFrame]:
    path = (
        _PROJECT_ROOT
        / "ml_output"
        / "backtests"
        / f"category={category}"
        / f"h={horizon}"
        / "fold_equity.parquet"
    )
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


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
        "**What this does:** Queries IBKR for option chains (bid, ask, IV, delta, "
        "gamma, vega, theta) of the **top-N most liquid symbols** from today's "
        "`price_historical/` data. Results are saved to `options_snapshot/` "
        "partitioned by date.  \n\n"
        "Typical run time: **5–15 minutes** for 50 symbols. Run daily after market close."
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


def _render_results() -> None:
    st.subheader("📈 Results")

    import plotly.express as px
    import plotly.graph_objects as go

    # ── Portfolio history ──────────────────────────────────────────────────
    with st.expander("📋 Portfolio History", expanded=True):
        df_port = _read_portfolio_history()
        if df_port is None or df_port.empty:
            st.caption("No portfolio snapshots yet — run Portfolio Snapshot first.")
        else:
            df_port["date"] = pd.to_datetime(df_port["date"])
            cols_avail = [
                c for c in ["net_liq", "buying_power", "cash"] if c in df_port.columns
            ]
            if cols_avail:
                fig = px.line(
                    df_port,
                    x="date",
                    y=cols_avail,
                    title="Account History",
                    labels={"value": "USD", "date": "Date", "variable": ""},
                )
                fig.update_layout(margin=dict(t=35, b=0), legend=dict(orientation="h"))
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
            st.caption("No options snapshots yet — run Options Snapshot first.")
        else:
            fig = px.bar(
                cov.tail(30),
                x="day",
                y="n_rows",
                title="Option rows per day (last 30)",
                labels={"day": "Date", "n_rows": "Rows"},
            )
            fig.update_layout(margin=dict(t=35, b=0))
            st.plotly_chart(fig, use_container_width=True, key="res_options_coverage_chart")

    # ── ML output ─────────────────────────────────────────────────────────
    st.markdown("#### ML Pipeline Results")

    summary = st.session_state.get("ml_summary_cache") or _read_summary_metrics()
    if summary is None:
        st.info("No ML results yet — run the ML Pipeline first.")
        return

    st.session_state["ml_summary_cache"] = summary

    # Summary metrics table
    with st.expander("📊 Fold Metrics", expanded=True):
        display_cols = [
            c
            for c in [
                "category",
                "horizon",
                "fold",
                "test_start",
                "test_end",
                "total_pnl",
                "sharpe_proxy",
                "n_trades",
                "n_days",
            ]
            if c in summary.columns
        ]
        st.dataframe(
            summary[display_cols]
            .sort_values(["category", "horizon", "test_end"])
            .style.format(
                {
                    "total_pnl": "{:+,.0f}",
                    "sharpe_proxy": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Aggregate metrics
    if {"total_pnl", "sharpe_proxy", "n_trades"}.issubset(summary.columns):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total PnL (all folds)", f"${summary['total_pnl'].sum():+,.0f}")
        c2.metric("Avg Sharpe", f"{summary['sharpe_proxy'].mean():.2f}")
        c3.metric("Total Trades", f"{int(summary['n_trades'].sum()):,}")
        c4.metric("Folds evaluated", len(summary))

    st.divider()

    # Equity curves
    st.markdown("#### Equity Curves")
    combos = summary[["category", "horizon"]].drop_duplicates()
    sel_cols = st.columns(2)
    sel_cat = sel_cols[0].selectbox(
        "Category", combos["category"].unique().tolist(), key="res_cat"
    )
    sel_h = sel_cols[1].selectbox(
        "Horizon", sorted(combos["horizon"].unique().tolist()), key="res_h"
    )

    eq = _read_equity_curves(sel_cat, sel_h)
    if eq is None:
        st.caption(f"No equity data for {sel_cat} H={sel_h}.")
    else:
        eq["date"] = pd.to_datetime(eq["date"])
        eq["cum_pnl"] = eq["pnl"].cumsum()
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=eq["date"],
                y=eq["cum_pnl"],
                mode="lines",
                name="Cumulative PnL",
                line=dict(color="#00b4d8"),
            )
        )
        fig.update_layout(
            title=f"Cumulative PnL — {sel_cat}  H={sel_h}",
            xaxis_title="Date",
            yaxis_title="PnL ($)",
            margin=dict(t=40, b=0),
        )
        st.plotly_chart(fig, use_container_width=True, key="res_equity_curve_chart")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total PnL", f"${eq['pnl'].sum():+,.0f}")
        c2.metric(
            "Avg Sharpe",
            f"{(eq['pnl'].mean() / (eq['pnl'].std(ddof=1) + 1e-9)) * (252**0.5):.2f}",
        )
        c3.metric("Total Trades", f"{int(eq['n_trades'].sum()):,}")


# ---------------------------------------------------------------------------
# Public entrypoint called from dashboard_app.py
# ---------------------------------------------------------------------------


def render_modeling_tab(ib_client) -> None:
    st.header("🤖 Modeling")

    tab_port, tab_opt, tab_pipe, tab_res = st.tabs(
        [
            "📋 Portfolio Snapshot",
            "📊 Options Snapshot",
            "🚀 ML Pipeline",
            "📈 Results",
        ]
    )

    with tab_port:
        _render_portfolio_snapshot(ib_client)

    with tab_opt:
        _render_options_snapshot()

    with tab_pipe:
        _render_ml_pipeline()

    with tab_res:
        _render_results()
