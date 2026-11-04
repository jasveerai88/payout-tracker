# Changelog

All notable changes to Payout Arrival Tracker are documented here.

## v0.2.0 — 2026-11-03

- Agent-ready release (no behaviour change to the text report):
  - `--json` flag: prints one JSON object with the same totals and per-platform rows as the text report (tool, version, date, rates, totals, rows with bucket / balances / distance / arrival, warnings, rule). Exit codes unchanged; errors in `--json` mode are `{"error": "..."}` with the same message and exit code — never a traceback, never plain text.
  - `SKILL.md` added at the repo root for AI coding agents: purpose, when to use / not use, exact commands, the output JSON schema, exit codes, and the honesty rules (a balance is never realized money).
  - README gained a short "Use with AI agents" section.
- Tests added for the JSON output (parses, totals and rows agree with the text report, JSON error objects on missing file and invalid data); suite is now 31 tests. Report totals on the bundled sample are unchanged (realized CAD $336.00).

## v0.1.2 — 2026-11-03

- Mini-fix from the delta re-audit:
  - `fee_pct` above 100 is now rejected with a clean error naming the field (it was silently accepted and clamped to "would land $0.00"). Valid range is 0–100 inclusive.
  - `fee_fixed` greater than the entry's balance is now rejected the same way (a fixed fee cannot exceed the balance it is charged against).
- Regression tests added; suite is now 27 tests. Report totals on the bundled sample are unchanged (realized CAD $336.00).

## v0.1.1 — 2026-11-03

- Bug-fix release from the adversarial QA audit (core math was verified correct; these are input-validation holes):
  - NaN / Infinity in any numeric field (balance, realized, threshold, fee_pct, fee_fixed, fx_to_cad, cad_to_inr) is now rejected with a clean error instead of printing `$nan` / `$inf` totals.
  - `cad_to_inr` of zero or negative is now rejected instead of silently zeroing/negating every ₹ figure (mirrors the existing `fx_to_cad` check).
  - `delay_days` must be a non-negative integer — negative values no longer print arrival dates in the past, and fractions like 7.9 are no longer silently truncated.
  - Structural errors are human-readable: a missing top-level `"entries"`, `"entries"` not a list, or an entry that isn't an object now say what to fix instead of a raw `KeyError` / `AttributeError`.
  - Fixed the source docstring pointing at a non-bundled `data/engine-money.json`; the bundled example is `data/sample.json`.
- Regression test per bug; suite is now 22 tests. Report totals on the bundled sample are unchanged (realized CAD $336.00).

## v0.1.0 — 2026-11-03

- First public release (MIT, Python 3 stdlib only, local-first).
- Renamed from payout-tracker-lite before first publish (owner decision 2026-11-03).
- Sorts every platform balance into REALIZED / PAYABLE / STUCK / UNKNOWN, net of fees and FX, in CAD + INR, with the built-in honesty trap (balances never leak into realized). Includes `data/sample.json`.
- Sponsors is LIVE: https://github.com/sponsors/jasveerai88
