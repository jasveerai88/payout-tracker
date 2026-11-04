---
name: payout-tracker
description: Sort platform balances into REALIZED (landed) vs PAYABLE / STUCK / UNKNOWN with fees and FX in CAD + INR. Use when reporting or reconciling creator payouts from a local JSON data file — never to treat a balance as income.
---

# Payout Arrival Tracker — agent skill

## Purpose

Reads a local JSON file of platform payout entries and produces a report
that keeps one distinction absolute: money that has actually **landed**
(REALIZED) versus balances that have **not** (PAYABLE = at threshold,
STUCK = below threshold, UNKNOWN = threshold unverified). Every figure is
net of platform fees, converted with the FX rates stored in the data file,
and shown in CAD + INR.

## When to use / not use

Use when:
- Summarising or reconciling creator/platform payouts from a JSON data file.
- Answering "how much have I actually received?" versus "what is pending?".
- Checking how far a balance is from its payout threshold, or when a
  payable amount would arrive.

Do NOT use when:
- The user asks for live account balances or current exchange rates — the
  tool is offline; rates are data in the file, possibly stale (`rates_date`).
- Scraping, logging in, or fetching anything — the tool does none of that.
- Tax filing or accounting sign-off — this is a tracking report, not advice.

## Commands

```bash
# Human-readable report
python3 src/payout_tracker.py data/sample.json

# Machine-readable report for agents (one JSON object on stdout)
python3 src/payout_tracker.py data/sample.json --json

# Pin the date (reproducible reports / tests)
python3 src/payout_tracker.py data/sample.json --today 2026-11-03 --json
```

Data file shape: a JSON object `{"cad_to_inr": 67.97, "rates_date":
"2026-10-26", "entries": [...]}` (a bare list of entries also works). Each
entry: `platform`, `currency`, `balance`, `realized`, `threshold` (or
`null` if unverified), `fee_pct`, `fee_fixed`, `fx_to_cad`, `delay_days`,
`note`.

## Output JSON schema (`--json`)

Top level:
- `tool` — `"payout-tracker"`
- `version` — tool version string
- `date` — report date (ISO)
- `cad_to_inr` — CAD→INR rate taken from the data file
- `rates_date` — when the rates were checked, from the data file
- `totals` — `{realized, payable, stuck, unknown}`, each `{"cad": n, "inr": n}`
- `rows` — one object per entry, sorted by bucket then platform:
  - `platform`, `currency`, `bucket` (`REALIZED` is never a bucket;
    buckets are `PAYABLE` / `STUCK` / `UNKNOWN` / `ZERO`)
  - `balance`, `realized`, `payable` — each `{"cad": n, "inr": n}`
  - `distance_to_threshold` — `{"cad": n, "inr": n}` for STUCK rows, else `null`
  - `arrival` — ISO date a PAYABLE amount would land, else `null`
  - `note` — free-text note from the entry, may be `""`
- `warnings` — list of strings (currently always empty on success)
- `rule` — the honesty rule string

On error, stdout is a single object: `{"error": "<message>"}` and the exit
code is unchanged (see below). Never a traceback.

## Exit codes

- `0` — report produced.
- `1` — error: file not found, malformed JSON, or a validation failure
  (non-finite numbers, negative amounts, `fx_to_cad` ≤ 0, `cad_to_inr` ≤ 0,
  `fee_pct` outside 0–100, `fee_fixed` above the balance, bad `delay_days`,
  or a structural problem the message explains).

## Limits & honesty rules the agent must respect

- **A balance is not realized money.** Only `totals.realized` is income
  that has landed. Never report `payable`, `stuck`, or `unknown` amounts
  as earnings, revenue, or "money made" — they are balances that may land
  later, in part, or never.
- **Rates are data, not truth.** FX figures come from the input file; if
  `rates_date` is old, say so instead of presenting conversions as current.
- **UNKNOWN means unverified.** A row whose threshold was never verified
  is labelled UNKNOWN on purpose — do not guess a threshold for it.
- **The tool never invents figures.** Invalid input is an error, not a
  zero. If the JSON output contains `error`, surface that message; do not
  fall back to estimating totals yourself.
- Local and offline: the tool reads only the file it is given and sends
  nothing anywhere.
