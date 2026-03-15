import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys
import types


class _DuckDbConn:
    def close(self):
        return None


sys.modules.setdefault("duckdb", types.SimpleNamespace(connect=lambda: _DuckDbConn()))

from src.data import collect_options_snapshot as mod


class TestCollectOptionsSnapshot(unittest.TestCase):
    def test_get_top_n_symbols_uses_requested_ref_date(self):
        target_day = date(2026, 3, 9)
        day_dir = Path("C:/mock/price_historical/year=2026/month=03/day=2026-03-09")

        with patch.object(mod, "_find_day_dir", return_value=day_dir), patch.object(
            mod, "duckdb_scan"
        ) as mock_scan:
            mock_scan.return_value = mod.pd.DataFrame(
                {"symbol": ["NVDA", "TSLA"], "volume": [10, 9]}
            )
            symbols = mod.get_top_n_symbols(
                Path("C:/mock/price_historical"),
                n=2,
                ref_date=target_day,
                min_price=5.0,
            )

        self.assertEqual(symbols, ["NVDA", "TSLA"])
        sql = mock_scan.call_args.args[1]
        self.assertIn("day=2026-03-09", sql)

    def test_main_falls_back_to_yahoo_when_option_farm_not_ready(self):
        saved_rows = []

        def _fake_save_snapshot(rows, snap_date, out_root):
            saved_rows.extend(rows)
            return out_root / "year=2026" / "month=03" / "day=2026-03-09" / "part-0.parquet"

        argv = [
            "collect_options_snapshot.py",
            "--date",
            "2026-03-09",
            "--price_root",
            "C:/mock/price_historical",
            "--out_root",
            "C:/mock/options_snapshot",
        ]

        with patch("sys.argv", argv), patch.object(
            mod,
            "load_config",
            return_value={
                "top_n": 1,
                "dte_min": 7,
                "dte_max": 90,
                "moneyness_range": 0.2,
                "max_expirations": 3,
                "option_chain_timeout_s": 25.0,
                "min_price": 5.0,
            },
        ), patch.object(
            mod,
            "get_top_n_symbols",
            return_value=["NVDA"],
        ) as mock_get_symbols, patch.object(
            mod,
            "_connect_ib_with_ready_option_farm",
            side_effect=RuntimeError("options data farm (usopt) not ready"),
        ), patch.object(
            mod,
            "collect_symbol",
            return_value=[{"underlying": "NVDA", "right": "C"}],
        ) as mock_collect_symbol, patch.object(
            mod,
            "save_snapshot",
            side_effect=_fake_save_snapshot,
        ), patch.object(
            mod.yaml,
            "safe_load",
            return_value={"api": {}},
        ):
            mod.main()

        self.assertEqual(saved_rows, [{"underlying": "NVDA", "right": "C"}])
        self.assertEqual(mock_collect_symbol.call_args.kwargs["force_yahoo"], True)
        self.assertEqual(mock_get_symbols.call_args.kwargs["ref_date"], date(2026, 3, 9))


if __name__ == "__main__":
    unittest.main()
