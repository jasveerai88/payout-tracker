#!/usr/bin/env python3
"""
Payout Arrival Tracker v0.1 — Canada-first, local/offline.

One job: never let a platform BALANCE be mistaken for MONEY.
Every figure is sorted into exactly one bucket:
  REALIZED  — money that has actually landed (post-fee, already received)
  PAYABLE   — balance at/above threshold; could land, has NOT landed
  STUCK     — balance below the payout threshold, with the distance
  UNKNOWN   — balance whose payout threshold we have not verified

Input: a JSON file of platform entries (see data/engine-money.json).
Output: a text report; every total in CAD + INR.
No network, no accounts, no scraping. Python 3 stdlib only. Spend: none.

Usage: python3 payout_tracker.py DATA.json [--today YYYY-MM-DD]
Exit codes: 0 ok, 1 error.
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path

VERSION = "0.1.0"


def _num(entry, key, default=0.0):
    v = entry.get(key, default)
    if v is None:
        return default
    v = float(v)
    if v < 0:
        raise ValueError(f"{entry.get('platform','?')}: {key} must be >= 0, got {v}")
    return v


def validate(entry):
    if not entry.get("platform"):
        raise ValueError("entry missing 'platform'")
    fx = _num(entry, "fx_to_cad", 0.0)
    if fx <= 0:
        raise ValueError(f"{entry['platform']}: fx_to_cad must be > 0")
    _num(entry, "balance"); _num(entry, "realized")
    _num(entry, "fee_pct"); _num(entry, "fee_fixed")
    if entry.get("threshold") is not None:
        _num(entry, "threshold")
    return entry


def bucket(entry):
    """Which bucket a balance belongs to. Realized is tracked separately and
    is NEVER derived from the balance — that separation is the product."""
    if _num(entry, "balance") == 0:
        return "ZERO"
    th = entry.get("threshold")
    if th is None:
        return "UNKNOWN"
    return "PAYABLE" if _num(entry, "balance") >= float(th) else "STUCK"


def net_payable_native(entry):
    """What would actually arrive if the payout were requested today:
    balance minus platform fees — and only when the threshold is met."""
    if bucket(entry) != "PAYABLE":
        return 0.0
    gross = _num(entry, "balance")
    fee = gross * _num(entry, "fee_pct") / 100.0 + _num(entry, "fee_fixed")
    return max(0.0, gross - fee)


def distance_native(entry):
    if bucket(entry) != "STUCK":
        return None
    return float(entry["threshold"]) - _num(entry, "balance")


def arrival_date(entry, today):
    if bucket(entry) != "PAYABLE":
        return None
    delay = entry.get("delay_days")
    if delay is None:
        return None
    return today + timedelta(days=int(delay))


def summarize(entries, today):
    rows = []
    for e in entries:
        validate(e)
        fx = _num(e, "fx_to_cad")
        b = bucket(e)
        rows.append({
            "platform": e["platform"], "currency": e.get("currency", "?"), "bucket": b,
            "balance_cad": _num(e, "balance") * fx,
            "realized_cad": _num(e, "realized") * fx,
            "payable_cad": net_payable_native(e) * fx,
            "distance_cad": (distance_native(e) * fx) if distance_native(e) is not None else None,
            "arrival": arrival_date(e, today),
            "note": e.get("note", ""),
        })
    return {
        "rows": rows,
        "realized_cad": sum(r["realized_cad"] for r in rows),
        "payable_cad": sum(r["payable_cad"] for r in rows),
        "stuck_cad": sum(r["balance_cad"] for r in rows if r["bucket"] == "STUCK"),
        "unknown_cad": sum(r["balance_cad"] for r in rows if r["bucket"] == "UNKNOWN"),
    }


def money(cad, cad_to_inr):
    return f"CAD ${cad:,.2f} / ₹{cad * cad_to_inr:,.0f}"


def render(summary, today, cad_to_inr, source_date):
    L = [f"PAYOUT ARRIVAL TRACKER v{VERSION} — {today.isoformat()}",
         f"Rates: CAD→INR {cad_to_inr} (checked {source_date}; rates are data, not truth)",
         "",
         f"REALIZED (money that has landed): {money(summary['realized_cad'], cad_to_inr)}",
         f"PAYABLE NOW (could land, has NOT): {money(summary['payable_cad'], cad_to_inr)}",
         f"STUCK below thresholds (balances): {money(summary['stuck_cad'], cad_to_inr)}",
         f"THRESHOLD UNKNOWN (balances):      {money(summary['unknown_cad'], cad_to_inr)}",
         ""]
    for r in sorted(summary["rows"], key=lambda r: (r["bucket"], r["platform"])):
        if r["bucket"] == "ZERO" and r["realized_cad"] == 0:
            L.append(f"- {r['platform']}: no balance, nothing realized")
            continue
        parts = [f"- {r['platform']} [{r['bucket']}]: balance {money(r['balance_cad'], cad_to_inr)}"]
        if r["realized_cad"]:
            parts.append(f"realized {money(r['realized_cad'], cad_to_inr)}")
        if r["bucket"] == "PAYABLE":
            parts.append(f"would land {money(r['payable_cad'], cad_to_inr)}")
            parts.append(f"arrival ~{r['arrival'].isoformat()}" if r["arrival"] else "arrival unknown (delay not recorded)")
        if r["bucket"] == "STUCK":
            parts.append(f"needs {money(r['distance_cad'], cad_to_inr)} more to reach the threshold")
        if r["note"]:
            parts.append(f"({r['note']})")
        L.append(" · ".join(parts))
    L += ["", "Rule printed on every report: a balance is not money until it lands."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Payout Arrival Tracker — realized vs balance, Canada-first")
    ap.add_argument("data")
    ap.add_argument("--today", help="YYYY-MM-DD override (for tests)")
    a = ap.parse_args()
    path = Path(a.data)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        return 1
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw["entries"] if isinstance(raw, dict) else raw
        cad_to_inr = float(raw.get("cad_to_inr", 67.97)) if isinstance(raw, dict) else 67.97
        source_date = raw.get("rates_date", "not recorded") if isinstance(raw, dict) else "not recorded"
        today = date.fromisoformat(a.today) if a.today else date.today()
        print(render(summarize(entries, today), today, cad_to_inr, source_date))
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
