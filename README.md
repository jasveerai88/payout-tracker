# Payout Arrival Tracker

**A balance is not money.** Most payout dashboards add up your platform balances and call it earnings. This one refuses: it sorts every balance into REALIZED (actually landed), PAYABLE (at the payout threshold — with the date it would arrive), STUCK (below threshold — with how much more you need), or UNKNOWN (threshold not verified — it says so instead of inventing a number), and prints every total net of fees and FX, in CAD + INR.

Built Canada-first (no PayPal assumptions), 100% local: your data file never leaves your machine. No accounts, no logins, no tracking.

## Run it
```
python3 src/payout_tracker.py data/sample.json
```
Your data is one JSON file: per platform — balance, realized (money that has actually landed), payout threshold, fees, FX rate, payout delay. Rates are data: update the file, never the code.

## Why it's free
I build free, local-first tools for small and faceless creators from measured failure data on real channels. If this saves you one "wait, that's not spendable?" moment, GitHub Sponsors is LIVE: **[github.com/sponsors/jasveerai88](https://github.com/sponsors/jasveerai88)** — sponsors keep the tools free and fund the next ones. The full version (multi-currency books, templates for Gumroad / Polar / Adobe Stock / YouTube, and the weekly reconciliation format) is a sponsor perk on the Studio tier.

## Proof, not promises
The tracker is tested with a built-in honesty trap: feed it balances with zero realized and its realized line must stay exactly 0 — the test suite fails the build if a balance ever leaks into "money". It runs weekly on my own channels' books.

MIT licensed. Python 3 stdlib only.

## Real example

Run on the bundled sample data (`--today` pinned so the output is reproducible):

```
$ python3 src/payout_tracker.py data/sample.json --today 2026-11-03
PAYOUT ARRIVAL TRACKER v0.1.1 — 2026-11-03
Rates: CAD→INR 67.97 (checked 2026-10-26; rates are data, not truth)

REALIZED (money that has landed): CAD $336.00 / ₹22,838
PAYABLE NOW (could land, has NOT): CAD $270.76 / ₹18,404
STUCK below thresholds (balances): CAD $52.50 / ₹3,568
THRESHOLD UNKNOWN (balances):      CAD $0.00 / ₹0

- Adobe Stock [PAYABLE]: balance CAD $85.40 / ₹5,805 · realized CAD $336.00 / ₹22,838 · would land CAD $85.40 / ₹5,805 · arrival ~2026-12-18 · (one payout already landed last quarter)
- YouTube (AdSense) [PAYABLE]: balance CAD $185.36 / ₹12,599 · would land CAD $185.36 / ₹12,599 · arrival ~2026-11-24 · (monthly cycle)
- Gumroad [STUCK]: balance CAD $52.50 / ₹3,568 · needs CAD $87.50 / ₹5,947 more to reach the threshold

Rule printed on every report: a balance is not money until it lands.
```

Note the honesty trap in action: the sample carries CAD $336.00 / ₹22,838 realized (one Adobe Stock payout that actually landed) — the much larger platform balances sit under PAYABLE / STUCK, never inside REALIZED.

## Privacy
- What it touches: only the JSON file you pass on the command line.
- What it stores: nothing — no database, no cache, no history.
- What it sends: nothing. No network, no accounts, no tracking.
- Your data file never leaves your machine.
- Delete the tool folder and everything is gone.

## Tests
```
python3 -m unittest discover -s tests -v
```
(Stdlib only — no dependencies. The tests also run under pytest.)
