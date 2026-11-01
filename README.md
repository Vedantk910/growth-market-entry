# growth-market-entry

Market-entry told like a case file: should a last-mile logistics operator
enter e-commerce fulfillment, and how. Top-down sizing on public sources,
bottom-up operator filings, unit economics with a closed-form flip volume,
and an enter / partner / decline decision surface the client can re-run.

**C2 flagship — the Market-Entry Growth Case.** C1 (`ma-case-file`) answers
"should we acquire"; this one answers "should we enter, and how." One
decision tool on deals + one on growth covers the full strategy-track case
book. That decision page — not a market description — is what separates a
growth deck from a tool a client can act on.

## The honest numbers

Sizing (baseline):
- SAM 0.75B parcels/yr for one large metro (US e-comm last-mile, EST top-down)
  anchored by 53.5B filed USPS commercial parcels (CONFIRMED).
- 22.5M parcels capturable at a 3% capture rate; that flow is 54× the flip
  volume, so the market is headroom, not the constraint.

Decision tool (new):
- **Flip volume:** in-house all-in cost/parcel `cv + F/V` crosses the flat
  $5.00 partner rate at **416,667 parcels/yr**; the 5-yr PV break-even is
  **383,511** (cost decay is worth real PV, pinned to a numeric sweep).
- **Decline rate:** $5.20/parcel — the partner rate at which the 3PL margin
  hits its $0.30 floor and the lease stops being offered.
- **At the 100k launch wedge the answer is PARTNER**; build only above the
  flip. CAC pays back in 10.6 parcels on the in-house margin vs 36 on the
  partner one — owning the margin is what makes acquisition cheap.

## What it does

1. **Data** — named market figures with confidence tags
   (`data/facts.py`), bottom-up operator filings (USPS, UPS, RRD), and an
   offline cross-check that the decision rests on cost, not SAM
   (`data/sanity.py`)
2. **Model** — the `model/` package:
   - `sizing.py` — SAM → serviceable → capturable funnel, CAC payback on
     both yardsticks, headroom over the flip
   - `unit_economics.py` — the flip volume closed form, the PV break-even,
     per-volume contribution tables
   - `decision.py` — the enter / partner / decline trigger line, the 2-D
     cost × rate surface, strategy PVs, and the partner-screenshot page
3. **Output** — a one-page decision page (`report/decision_page.md`) a
   partner would screenshot, plus `out/decision_numbers.json` pinned by the
   notebook run

## Project layout

```
data/       # facts layer (named figures + tags) + offline cross-checks
model/      # sizing.py, unit_economics.py, decision.py
notebooks/  # case_full.ipynb + runner (one-command end-to-end, writes out/)
report/     # decision_page.md one-pager
tests/      # pytest suite (offline; 33 cases)
```

## Quick start

```bash
pip install -r requirements.txt
python notebooks/run_notebook.py   # end-to-end, writes out/decision_numbers.json
python -m pytest tests/ -q         # 33 offline tests
```

The flip-volume maths is the deliverable: it states the parcel volume at
which building beats leasing, reports the decline rate rather than burying
it, and — in the decision tool — says *what to do* (enter / partner /
decline) with a number you can re-run.

## 7-gate trail (C2 decision tool)

- **G0 scope** — one decision: enter in-house, partner (lease capacity), or
  decline, for a last-mile operator entering e-commerce fulfillment.
- **G1 build** — three `model/` modules over a pure-python facts layer;
  offline, no network, deterministic (the case is a function of its
  constants, so the test suite can lock every behaviour).
- **G2 test** — 33 offline tests; each module has a
  closed-form-vs-numeric pin (the PV break-even vs a binary-search sweep),
  an invariance check, and a sensitivity check on the pivot inputs.
- **G3 verify** — `python notebooks/run_notebook.py` regenerates
  `out/decision_numbers.json` with every quoted number; the report quotes
  only from that file.
- **G4 stress/ablation** — halving any market-size factor (US total, the
  USPS anchor, the e-comm slice, the metro share) leaves the flip volume
  bit-identical; halving the capture rate moves headroom, not the boundary.
  The ablation *is* the "cost, not SAM" claim.
- **G5 document** — this README + `report/decision_page.md` with the honest
  limits (hub fixed cost and partner rate tagged `[unverified]`).
- **G6 hostile pass** — the three attacks and the answers:

| Attack | Answer |
|---|---|
| "Your market number is a range — which number does the decision actually rest on?" | Not the SAM. The decision rests on the flip volume F/(p−cv) and the decline rate R−floor, both closed forms in cost and the partner rate. `data/sanity.cross_check` proves it: halve the SAM and the trigger does not move. The SAM sets headroom (54× the flip), the cost structure sets the trigger. |
| "The partner rate and hub cost are just two committee inputs you picked — the whole thing is one parameter." | Two inputs, but isolated by the formula: flip = F/(p−cv) means the client sees exactly how much each is worth, and the 72-cell cost × rate surface is the partner screenshot — the trigger moves *continuously* across the band, which is the re-runnable part. What's defensible is that build/lease/decline are priced on one yardstick (USD/parcel net contribution), not three gut calls. |
| "RRD's $223/parcel says nothing about last-mile cost — your bottom-up bench is broken." | It's tagged: USPS/UPS/RRD per-parcel figures are *derived* (revenue ÷ volume), not filed, and the confidence tag carries that. RRD anchors the *fulfillment* margin (+41% volume growth, the adjacent-market entry case); it does not anchor delivery unit cost, which is why the decision pivot is the committee's cost-to-serve, not the filing. The filings set order of magnitude; the trigger is the cost structure. |

What I would change next: a sourced partner rate card (the $5.00 is a
committee input), a hub cost model broken out by facility tier, and a
multi-metro extension that re-derives the flip per metro instead of
scaling it.
