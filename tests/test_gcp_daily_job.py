import json
import tempfile
import unittest
from pathlib import Path

from src.ml.gcp_daily_job import (
    _day_partition_has_parquet,
    _refresh_marker_path,
    _write_refresh_marker,
    _wait_for_refresh_marker,
    _count_price_days,
)


class TestDayPartitionHasParquet(unittest.TestCase):
    """Real helper exercised here: the test's original target
    (_select_option_refresh_days) never existed in the source. The actual
    day-coverage logic the daily job uses to decide whether a partition needs
    (re)collection is _day_partition_has_parquet, so we test that instead."""

    def test_returns_true_when_partition_has_parquet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            day_dir = root / "year=2026" / "month=03" / "day=2026-03-09"
            day_dir.mkdir(parents=True)
            (day_dir / "part-0.parquet").write_bytes(b"x")

            self.assertTrue(_day_partition_has_parquet(root, "2026-03-09"))

    def test_returns_false_when_partition_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_day_partition_has_parquet(Path(tmp), "2026-03-09"))

    def test_returns_false_when_partition_dir_exists_but_no_parquet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            day_dir = root / "year=2026" / "month=03" / "day=2026-03-09"
            day_dir.mkdir(parents=True)
            (day_dir / "_SUCCESS").write_text("")

            self.assertFalse(_day_partition_has_parquet(root, "2026-03-09"))

    def test_returns_false_for_malformed_day_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_day_partition_has_parquet(Path(tmp), "not-a-date"))


class TestCountPriceDays(unittest.TestCase):
    def test_counts_distinct_day_partitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for day in ("2026-03-07", "2026-03-08", "2026-03-09"):
                y, m, _ = day.split("-")
                d = root / f"year={y}" / f"month={m}" / f"day={day}"
                d.mkdir(parents=True)
                (d / "part-0.parquet").write_bytes(b"x")

            self.assertEqual(_count_price_days(root), 3)

    def test_zero_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_count_price_days(Path(tmp)), 0)


class TestRefreshMarkerRoundTrip(unittest.TestCase):
    def test_write_then_wait_detects_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            day_str = "2026-03-09"

            written = _write_refresh_marker(out_dir, day_str)
            self.assertEqual(written, _refresh_marker_path(out_dir, day_str))
            self.assertTrue(written.exists())

            payload = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["day"], day_str)

            # A waiter should immediately see the valid marker.
            found = _wait_for_refresh_marker(
                out_dir, day_str, timeout_minutes=0.05, poll_seconds=0.01
            )
            self.assertTrue(found)

    def test_wait_times_out_when_marker_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = _wait_for_refresh_marker(
                Path(tmp), "2026-03-09", timeout_minutes=0.001, poll_seconds=0.01
            )
            self.assertFalse(found)


if __name__ == "__main__":
    unittest.main()
