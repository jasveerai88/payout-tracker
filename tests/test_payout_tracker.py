"""Tests for Payout Arrival Tracker — stdlib unittest (also runs under pytest)."""
import json
import subprocess
import sys
import tempfile
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


class FiniteNumbers(unittest.TestCase):
    """P1 regression: NaN / Infinity must never reach a report ($nan / $inf)."""

    def test_nan_and_inf_fields_rejected(self):
        for kw in ({"balance": float("nan")}, {"realized": float("inf")},
                   {"threshold": float("inf")}, {"fee_pct": float("nan")},
                   {"fee_fixed": float("inf")}, {"fx_to_cad": float("nan")}):
            with self.assertRaises(ValueError, msg=str(kw)):
                pt.validate(entry(**kw))

    def test_cli_nan_literal_in_json_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"cad_to_inr": 67.97, "entries": [{"platform": "X",'
                         ' "balance": NaN, "fx_to_cad": 1.0}]}')
            r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), str(p)],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR:", r.stdout)
        self.assertNotIn("$nan", r.stdout)


class CadToInrRate(unittest.TestCase):
    """P2 regression: a zero/negative/non-finite CAD→INR rate must not
    silently zero (or negate) every ₹ figure in the report."""

    def test_bad_rates_rejected(self):
        for rate in (0, -5, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=str(rate)):
                pt.extract({"cad_to_inr": rate, "entries": []})

    def test_cli_zero_rate_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"cad_to_inr": 0, "entries": []}')
            r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), str(p)],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("cad_to_inr", r.stdout)


class DelayDays(unittest.TestCase):
    """P3 regression: delay_days must be a non-negative integer —
    no past arrival dates, no silent truncation of 7.9 to 7."""

    def test_negative_and_fractional_rejected(self):
        for bad in (-1, 7.9):
            with self.assertRaises(ValueError, msg=str(bad)):
                pt.validate(entry(delay_days=bad))

    def test_zero_and_positive_accepted(self):
        pt.validate(entry(delay_days=0))
        pt.validate(entry(delay_days=45))


class FeeBounds(unittest.TestCase):
    """Mini-fix regression: fee_pct above 100 and fee_fixed above the balance
    were silently accepted and clamped to "would land $0.00" — they are
    data errors and must be rejected, naming the field."""

    def test_fee_pct_above_100_rejected(self):
        for bad in (100.5, 150, 1000):
            with self.assertRaises(ValueError, msg=str(bad)):
                pt.validate(entry(balance=200.0, fee_pct=bad))

    def test_fee_pct_bounds_accepted(self):
        pt.validate(entry(balance=200.0, fee_pct=0))
        pt.validate(entry(balance=200.0, fee_pct=100))

    def test_fee_fixed_above_balance_rejected(self):
        with self.assertRaises(ValueError):
            pt.validate(entry(balance=10.0, fee_fixed=10.01))
        with self.assertRaises(ValueError):
            pt.validate(entry(balance=0.0, fee_fixed=5.0))

    def test_fee_fixed_at_balance_accepted(self):
        pt.validate(entry(balance=10.0, fee_fixed=10.0))
        pt.validate(entry(balance=0.0, fee_fixed=0.0))

    def test_cli_errors_name_the_field(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"entries": [{"platform": "X", "balance": 50,'
                         ' "threshold": 10, "fee_pct": 150, "fx_to_cad": 1.0}]}')
            r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), str(p)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("ERROR:", r.stdout)
            self.assertIn("fee_pct", r.stdout)
            p.write_text('{"entries": [{"platform": "X", "balance": 50,'
                         ' "threshold": 10, "fee_fixed": 999, "fx_to_cad": 1.0}]}')
            r = subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), str(p)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("ERROR:", r.stdout)
            self.assertIn("fee_fixed", r.stdout)


class StructuralErrors(unittest.TestCase):
    """P4 regression: malformed files say what to fix — never a raw
    KeyError ('entries') or AttributeError ('str' object has no attribute)."""

    def _run(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(text)
            return subprocess.run([sys.executable, str(ROOT / "src" / "payout_tracker.py"), str(p)],
                                  capture_output=True, text=True)

    def test_missing_entries_key(self):
        r = self._run('{"cad_to_inr": 67.97}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR:", r.stdout)
        self.assertIn('"entries"', r.stdout)

    def test_entries_not_a_list(self):
        r = self._run('{"entries": "nope"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("must be a list", r.stdout)

    def test_entry_not_an_object(self):
        r = self._run('{"entries": ["just a string"]}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("entry #1", r.stdout)
        self.assertNotIn("has no attribute", r.stdout)


if __name__ == "__main__":
    unittest.main()
