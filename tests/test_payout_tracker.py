"""Tests for Payout Arrival Tracker — stdlib unittest (also runs under pytest)."""
import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import payout_tracker as pt  # noqa: E402

TODAY = date(2026, 11, 3)


def entry(**kw):
    base = {"platform": "Test", "currency": "USD", "balance": 0, "realized": 0,
            "threshold": 100, "fee_pct": 0, "fee_fixed": 0, "fx_to_cad": 1.40,
            "delay_days": 7}
    base.update(kw)
    return base


class HonestyTrap(unittest.TestCase):
    def test_balance_never_leaks_into_realized(self):
        """THE product rule: big balances + zero realized => realized stays exactly 0."""
        entries = [entry(platform="A", balance=9999.0, realized=0),
                   entry(platform="B", balance=500.0, realized=0, threshold=None)]
        s = pt.summarize(entries, TODAY)
        self.assertEqual(s["realized_cad"], 0.0)

    def test_payable_is_not_realized(self):
        s = pt.summarize([entry(balance=200.0, realized=0)], TODAY)
        self.assertGreater(s["payable_cad"], 0)
        self.assertEqual(s["realized_cad"], 0.0)

    def test_realized_counts_only_landed_money(self):
        s = pt.summarize([entry(balance=50.0, realized=10.0)], TODAY)
        self.assertAlmostEqual(s["realized_cad"], 14.0)  # 10 * 1.40, balance ignored


class BucketLogic(unittest.TestCase):
    def test_payable_at_and_above_threshold(self):
        self.assertEqual(pt.bucket(entry(balance=100.0)), "PAYABLE")
        self.assertEqual(pt.bucket(entry(balance=250.0)), "PAYABLE")

    def test_stuck_below_threshold_with_distance(self):
        e = entry(balance=37.50)
        self.assertEqual(pt.bucket(e), "STUCK")
        self.assertAlmostEqual(pt.distance_native(e), 62.50)

    def test_unknown_when_threshold_unverified(self):
        self.assertEqual(pt.bucket(entry(balance=10.0, threshold=None)), "UNKNOWN")

    def test_zero_balance(self):
        self.assertEqual(pt.bucket(entry(balance=0, realized=5.0)), "ZERO")

    def test_net_payable_is_fee_adjusted_and_payable_only(self):
        e = entry(balance=200.0, fee_pct=10, fee_fixed=0.50)
        self.assertAlmostEqual(pt.net_payable_native(e), 179.50)
        self.assertEqual(pt.net_payable_native(entry(balance=50.0)), 0.0)  # STUCK pays nothing

    def test_arrival_date_only_for_payable(self):
        self.assertEqual(pt.arrival_date(entry(balance=200.0), TODAY), date(2026, 11, 10))
        self.assertIsNone(pt.arrival_date(entry(balance=50.0), TODAY))


class Validation(unittest.TestCase):
    def test_negative_and_bad_fx_rejected(self):
        with self.assertRaises(ValueError):
            pt.validate(entry(balance=-1))
        with self.assertRaises(ValueError):
            pt.validate(entry(fx_to_cad=0))
        with self.assertRaises(ValueError):
            pt.validate({"balance": 1, "fx_to_cad": 1.0})  # no platform


class SampleRun(unittest.TestCase):
    def test_bundled_sample_json(self):
        raw = json.loads((ROOT / "data" / "sample.json").read_text())
        s = pt.summarize(raw["entries"], TODAY)
        # Adobe Stock realized 240 USD * 1.40 = 336 CAD — and nothing else counts
        self.assertAlmostEqual(s["realized_cad"], 336.00)
        self.assertAlmostEqual(s["stuck_cad"], 52.50)  # Gumroad 37.50 USD * 1.40
        buckets = {r["platform"]: r["bucket"] for r in s["rows"]}
        self.assertEqual(buckets["Gumroad"], "STUCK")
        self.assertEqual(buckets["YouTube (AdSense)"], "PAYABLE")
        self.assertEqual(buckets["Adobe Stock"], "PAYABLE")

    def test_cli_end_to_end(self):
        r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"),
                            str(ROOT / "data" / "sample.json"), "--today", "2026-11-03"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REALIZED (money that has landed): CAD $336.00", r.stdout)
        self.assertIn("a balance is not money until it lands", r.stdout)

    def test_cli_missing_file_errors_cleanly(self):
        r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), "nope.json"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR: file not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
