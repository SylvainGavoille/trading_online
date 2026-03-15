import unittest
from pathlib import Path
from unittest.mock import patch

from src.ml.gcp_daily_job import _select_option_refresh_days


class TestGcpDailyJob(unittest.TestCase):
    def test_select_option_refresh_days_backfills_recent_missing_days_only(self):
        def _has_parquet(_root: Path, day_str: str) -> bool:
            return day_str == "2026-03-08"

        with patch("src.ml.gcp_daily_job._day_partition_has_parquet", side_effect=_has_parquet):
            refresh_days = _select_option_refresh_days(
                {"2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10"},
                Path("C:/mock/options_snapshot"),
                recent_backfill_days=3,
            )

        self.assertEqual(refresh_days, ["2026-03-09", "2026-03-10"])


if __name__ == "__main__":
    unittest.main()
