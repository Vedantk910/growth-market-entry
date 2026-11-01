# Market-Entry Decision Page — Last-Mile Logistics → E-Commerce Fulfillment
*One page. Top-down funnel on public sources + bottom-up operator filings, the
enter / partner / decline trigger quantified per parcel. Every figure
reproducible via `python notebooks/run_notebook.py` (offline, writes
`out/decision_numbers.json`).*

## The one-liner
**At the 100k-parcel launch wedge, partner at $5.00/parcel; build in-house
only above the 417k-parcel/yr flip volume; decline if the partner rate drifts
past $5.20 (the margin floor collapses the lease).** The SAM is 0.75B
parcels/yr with 22.5M capturable at a 3% capture — the funnel sets
**headroom, not the trigger**: halve the SAM and the flip volume does not
move.

## 1. The sizing funnel (context block, not the pivot)
| Stage | Parcels/yr | Tag |
|---|---|---|
| US total parcels (Menzies '23) | 124.9B | EST |
| × e-comm last-mile slice (30%) | 37.5B | EST |
| × one-metro serviceable share (2%) | **0.75B (SAM)** | EST |
| × capture rate (3%) | **22.5M capturable** | EST |

**Anchor:** 53.5B USPS commercial parcels (2023, filed) — the EST top-down
lands inside the filed envelope.  **Headroom:** capturable flow is
**54× the flip volume** — the network has runway, the trigger is not
bottled by the market.

## 2. The decision boundary (the flip volume)
In-house all-in cost/parcel is `cv + F/V` ($3.80 marginal + $500k hub
amortised); the partner rate is the flat $5.00.  In-house is cheaper exactly
when `V ≥ F/(p − cv)`:

| Quantity | Value | Read |
|---|---|---|
| **Flip volume (Y1)** | **416,667 parcels/yr** | below it, partner; above it, build |
| 5-yr PV break-even | **383,511 parcels/yr** | cost decay makes PV strictly tighter than Y1 |
| Decline rate | **$5.20/parcel** | partner margin at its $0.30 floor; above it, decline |

Year-1 contribution table: 100k and 200k/yr → **PARTNER**; 500k/yr and
above → **BUILD** (in-house cost/parcel $4.80 vs $5.00 lease).

## 3. The enter / partner / decline surface
The 72-cell (9 cost × 8 rate) sweep is the partner-screenshot frame
(`decision.surface`).  The one yardstick is USD/parcel net contribution;
build, lease and decline are priced against it, not against three
independent gut calls.  Committee inputs (hub fixed cost, partner rate,
the cost decay) are tagged `[unverified]` — the defensible part is that
the trigger is a *number the client can re-run*.

## 4. What we would ask the client
1. **Partner rate card** — is $5.00/parcel the 3PL's published rate or the
   negotiated one, and does it hold at 500k+ parcels?
2. **Hub fixed cost** — the $500k/yr facility figure is a committee input;
   what does the ops team actually quote for one metro hub?
3. **Capture rate** — 3% of the SAM in year 1–3; is CAC $18/customer the
   real acquisition cost, and what does retention look like at the partner
   margin ($0.50/parcel)?
4. **Cost decay** — the 1.5%/yr route-density decay is the value of the
   PV break-even sitting *below* the Y1 flip; what do the last-mile
   operators on the bottom-up bench actually run?
5. **The adjacent-market question** — RRD filed +41% volume growth in
   fulfillment; does the client enter now (the filings are still
   pre-scale) or wait for the adjacent market to prove out?

## 5. Honest limits
- **The whole decision rests on two `[unverified]` numbers** (hub fixed
  cost and the partner rate).  The tool's value is that it *isolates* them:
  flip = F/(p−cv), so the client can see exactly how much each is worth.
- **USPS revenue-per-parcel ($0.56) is derived, not filed** — revenue and
  volume are filed; the division is ours.  RRD's $223.94/parcel is the same
  derived figure and says nothing about last-mile unit cost; it anchors the
  *fulfillment* margin, not the delivery one.
- **No drift / no live data**: the funnel factors (30% e-comm slice, 2%
  metro share) are order-of-magnitude EST.  The SAM sets headroom — the
  trigger does not move with it (proven by `data/sanity.cross_check`,
  offline, in the test suite).

## CV bullet
> Market-entry decision tool for last-mile logistics: top-down SAM →
> capturable funnel on public filings (USPS, Menzies) and bottom-up
> operator benchmarks; quantified enter/partner/decline triggers —
> 417k-parcel flip volume, $5.20 decline rate, 54× headroom.
