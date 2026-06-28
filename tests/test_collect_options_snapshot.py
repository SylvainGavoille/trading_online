import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
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

        # Mock the DuckDB connection: con.execute(sql, params).df() returns rows.
        mock_result = MagicMock()
        mock_result.df.return_value = mod.pd.DataFrame(
            {"symbol": ["NVDA", "TSLA"], "volume": [10, 9]}
        )
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_result

        with patch.object(mod, "_find_day_dir", return_value=day_dir), patch.object(
            mod.duckdb, "connect", return_value=mock_con
        ):
            symbols = mod.get_top_n_symbols(
                Path("C:/mock/price_historical"),
                n=2,
                ref_date=target_day,
                min_price=5.0,
            )

        self.assertEqual(symbols, ["NVDA", "TSLA"])

        # SQL must read the requested day's parquet glob and bind min_price + n.
        sql, params = mock_con.execute.call_args.args
        self.assertIn("day=2026-03-09", sql)
        self.assertIn("read_parquet", sql)
        self.assertIn("WHERE close >= ?", sql)
        self.assertIn("LIMIT ?", sql)
        self.assertEqual(params, [5.0, 2])
        mock_con.close.assert_called_once()

    def test_main_collects_via_yahoo_and_saves_snapshot(self):
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
                "batch_delay": 0.0,
                "min_price": 5.0,
            },
        ), patch.object(
            mod,
            "get_top_n_symbols",
            return_value=["NVDA"],
        ) as mock_get_symbols, patch.object(
            mod,
            "collect_symbol",
            return_value=[{"underlying": "NVDA", "right": "C"}],
        ) as mock_collect_symbol, patch.object(
            mod,
            "save_snapshot",
            side_effect=_fake_save_snapshot,
        ), patch.object(
            mod.time,
            "sleep",
            return_value=None,
        ):
            mod.main()

        # The collected Yahoo rows are persisted via save_snapshot.
        self.assertEqual(saved_rows, [{"underlying": "NVDA", "right": "C"}])
        # The universe is resolved for the requested snapshot date.
        self.assertEqual(mock_get_symbols.call_args.kwargs["ref_date"], date(2026, 3, 9))
        # collect_symbol is invoked per symbol with the snapshot date.
        collect_args = mock_collect_symbol.call_args.args
        self.assertEqual(collect_args[0], "NVDA")
        self.assertEqual(collect_args[2], date(2026, 3, 9))


if __name__ == "__main__":
    unittest.main()
