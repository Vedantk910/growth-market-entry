"""The enter / partner / decline decision page (C2, partner-screenshot).

This is the artifact that makes the case a *decision tool*, not a market
description.  For a named last-mile operator entering e-commerce
fulfillment it returns one quantified trigger line, in the house
(``ma-case-file``) idiom: the volume at which build overtakes lease, the
rate at which lease collapses to decline, and the honest "the decision
rests on cost and capture, not the SAM" caveat.

Three strategies, priced per parcel on one yardstick:

* **ENTER (in-house)** - you build the metro network.  All-in cost
  ``cv + F/V``; you win at scale (route density).  Margin ``(R-cv)V - F``.
* **PARTNER (lease)** - a 3PL ships on their network at rate ``p``.  Flat
  cost per parcel; no fixed cost; you keep ``(R - p)`` per parcel.  The
  low-commitment floor.
* **DECLINE** - the partner margin ``(R - p)`` is below the 3PL floor, so
  neither strategy clears the hurdle: don't enter at this price.

The trigger is the **flip volume** ``V* = F / (p - cv)`` - below it you
partner, above it you build - plus the **decline rate** ``R - floor`` on
the partner side.  Both are closed forms in the module; the tests pin the
PV version against a numeric sweep and prove scale/parameter sensitivity.

The committee inputs (``hub_fixed_annual``, ``partner_rate_per_parcel``,
the cost decay) are tagged ``[unverified]``; what makes the page
defensible is that build / lease / decline are priced on one yardstick,
so the trigger is a number a client can re-run - not a gut call.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from data.facts import Facts, OPERATORS
from . import unit_economics as ue
from . import sizing


# --- sweep grids (the committee's policy band - not free parameters) -----
DEFAULT_VOLUME_GRID = np.array([50_000, 100_000, 200_000, 300_000,
                                500_000, 800_000, 1_000_000])
DEFAULT_RATE_GRID = np.arange(3.5, 7.0 + 1e-9, 0.5)          # partner rate $/parcel
DEFAULT_COST_GRID = np.arange(3.0, 5.0 + 1e-9, 0.25)          # in-house var cost


def _annuity_pv(wacc: float, years: int) -> float:
    """PV factor for a level `years`-yr annuity of $1 at `wacc`."""
    if wacc == 0:
        return float(years)
    return (1.0 - (1.0 + wacc) ** (-years)) / wacc


def strategy_pvs(f: Facts, volume: float, years: int = 5,
                 wacc: float = 0.08) -> Dict[str, float]:
    """5-yr PV of the per-parcel margin, build vs lease, at a fixed volume.

    In-house margin is amortised (the hub's fixed cost is a *recurring*
    per-year facility cost, charged every year; the cost decay lowers the
    marginal cost each year); partner margin is flat.  The PV difference
    is the entry decision the committee re-runs - and it is the numeric
    twin of ``unit_economics.pv_break_even_volume`` (the closed form
    prices the same recurring-fixed-cost assumption), which the test
    suite pins against a binary-search sweep.
    """
    cv = f.in_house_var_cost_per_parcel
    R = f.revenue_per_parcel
    gap = f.partner_rate_per_parcel - cv
    pv_lease = (R - f.partner_rate_per_parcel) * volume * _annuity_pv(wacc, years)
    pv_build = 0.0
    for t in range(1, years + 1):
        cv_t = ue.decayed_var_cost(f, t)
        margin_t = (R - cv_t) * volume - f.hub_fixed_annual
        pv_build += margin_t / (1.0 + wacc) ** t
    return {"pv_build": round(pv_build, 0), "pv_lease": round(pv_lease, 0),
            "gap_per_parcel": round(gap, 4),
            "in_house_wins": pv_build >= pv_lease}


def trigger_line(f: Facts, volume: Optional[float] = None,
                 rate: Optional[float] = None) -> Dict:
    """The single one-liner the client quotes, with the number on it.

    ``volume`` defaults to the launch wedge; ``rate`` overrides the partner
    rate.  Returns the recommendation (ENTER / PARTNER / DECLINE), the
    flip volume, the decline rate, and the PVs at the queried point."""
    rate = f.partner_rate_per_parcel if rate is None else rate
    volume = f.launch_wedge_parcels_per_year if volume is None else volume

    par_margin = f.revenue_per_parcel - rate
    # partner margin floor: below it the 3PL won't serve -> decline
    below_floor = par_margin < f.partner_margin_floor
    # flip volume at this rate (in-house var cost vs rate)
    gap = rate - f.in_house_var_cost_per_parcel
    flip = f.hub_fixed_annual / gap if gap > 0 else float("inf")
    pv = strategy_pvs(f, volume, years=f.horizon_years, wacc=f.discount_rate)

    if below_floor:
        rec = "DECLINE"
        line = (f"DECLINE at partner rate ${rate:.2f}/parcel: the 3PL "
                f"margin ${par_margin:.2f} is below the ${f.partner_margin_floor:.2f} "
                f"floor - lease is not offered at this price.")
    elif volume >= flip and not np.isinf(flip):
        rec = "ENTER"
        line = (f"ENTER in-house at >= {flip:,.0f} parcels/yr (you clear "
                f"{volume:,.0f}); below that, PARTNER at ${rate:.2f}/parcel.")
    else:
        rec = "PARTNER"
        line = (f"PARTNER at ${rate:.2f}/parcel up to the flip "
                f"({flip:,.0f} parcels/yr); build only above it.")
    return {"recommendation": rec, "line": line, "volume_queried": volume,
            "rate_queried": rate, "flip_volume": flip,
            "decline_rate": f.revenue_per_parcel - f.partner_margin_floor,
            "partner_margin_pp": par_margin,
            "pv_build": pv["pv_build"], "pv_lease": pv["pv_lease"]}


def surface(f: Facts,
            volumes: Optional[np.ndarray] = None,
            rates: Optional[np.ndarray] = None,
            cost_grid: Optional[np.ndarray] = None) -> pd.DataFrame:
    """The 2-D decision surface a partner screenshots: for each (in-house
    var cost, partner rate) pair, the flip volume and the strategy that
    wins at the launch wedge.  Grids are the committee band, not free
    parameters."""
    vols = DEFAULT_VOLUME_GRID if volumes is None else np.asarray(volumes)
    cg = DEFAULT_COST_GRID if cost_grid is None else np.asarray(cost_grid)
    rg = DEFAULT_RATE_GRID if rates is None else np.asarray(rates)
    rows = []
    for cv in cg:
        for rate in rg:
            ff = _with_pivot(f, in_house_var_cost_per_parcel=cv,
                             partner_rate_per_parcel=rate)
            flip = f.hub_fixed_annual / max(rate - cv, 1e-9) if (rate - cv) > 0 \
                else float("inf")
            par_margin = f.revenue_per_parcel - rate
            below_floor = par_margin < f.partner_margin_floor
            win = "decline" if below_floor else \
                ("enter" if f.launch_wedge_parcels_per_year >= flip
                 else "partner")
            rows.append({"in_house_var_cost": round(float(cv), 2),
                        "partner_rate": round(float(rate), 2),
                        "flip_volume": None if np.isinf(flip) else int(flip),
                        "in_house_wins_at_wedge": win,
                        "partner_margin_pp": round(par_margin, 2)})
    return pd.DataFrame(rows)


def _with_pivot(f: Facts, **kw) -> Facts:
    d = f.to_dict()
    d.update(kw)
    return Facts(**d)


def page(f: Facts, volumes: Optional[np.ndarray] = None) -> pd.DataFrame:
    """The partner-screenshot frame: trigger, flip volume, decline rate,
    and the build-vs-lease PV at the launch wedge."""
    t = trigger_line(f)
    ctable = ue.contribution_table(f, volumes or DEFAULT_VOLUME_GRID)
    out = {
        "recommendation_at_wedge": t["recommendation"],
        "trigger_line": t["line"],
        "flip_volume": t["flip_volume"],
        "pv_break_even": ue.pv_break_even_volume(f),
        "decline_rate": t["decline_rate"],
        "partner_margin_pp": t["partner_margin_pp"],
        "pv_build_at_wedge": t["pv_build"],
        "pv_lease_at_wedge": t["pv_lease"],
    }
    df = pd.DataFrame(out, index=[0])
    df["volume_grid"] = [
        [{"v": r["volume_per_year"], "ih": r["in_house_wins"]}
         for r in ctable["volumes"]]
    ]
    # the context block a partner screenshots first: how big it is, the
    # filed anchor, the headroom beyond the flip, and CAC payback.  The
    # pivot above decides; the size below sets runway.
    fl = sizing.funnel(f)
    hr = sizing.headroom(f)
    ca = sizing.cac_payback(f)
    df["size"] = [
        {
            "sam_billion": fl["sam_billion"],
            "capturable_parcels": fl["capturable_parcels"],
            "anchor_billion": fl["anchor"]["usps_commercial_parcels_billion"],
            "headroom_multiple_over_flip": hr["headroom_multiple"],
            "cac_payback_in_house_parcels": ca["parcels_to_recover_cac_in_house"],
            "cac_payback_partner_parcels": ca["parcels_to_recover_cac_partner"],
        }
    ]
    return df


def bottom_up_benchmarks(f: Facts) -> pd.DataFrame:
    """The bottom-up block: per-operator revenue/parcel, op margin and the
    derived cost/parcel - the filings that anchor the top-down estimate."""
    rows = []
    for op in OPERATORS:
        rows.append({
            "operator": op.name,
            "revenue_usd": op.revenue_usd,
            "operating_income_usd": op.operating_income_usd,
            "volume_million": op.volume_million,
            "revenue_per_parcel": round(op.revenue_usd / (op.volume_million * 1e6), 2)
            if op.volume_million else None,
            "op_margin": round(op.operating_income_usd / op.revenue_usd, 3)
            if op.revenue_usd else None,
            "derived_revenue_per_parcel": op.derived_revenue_per_parcel,
            "confidence": op.confidence,
            "adjacent_entry_case": op.adjacent_entry,
            "source": op.source,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import json
    f = Facts()
    print(json.dumps(trigger_line(f), indent=2, default=float))
    print(page(f).to_string())
    print(surface(f).to_string(index=False, max_rows=12))
