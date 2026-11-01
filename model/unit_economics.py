"""Unit economics + the enter/partner/decline decision boundary (C2).

The whole case reduces to one number: the **flip volume** - the annual
parcel volume at which building the last-mile network in-house costs no
more per parcel than leasing a 3PL's capacity.

Notation (all per-parcel unless noted):
    R   = revenue_per_parcel            (what the client pays you)
    cv  = in_house_var_cost_per_parcel  (your marginal last-mile cost)
    F   = hub_fixed_annual              (your metro hub, USD / year)
    p   = partner_rate_per_parcel      (what the 3PL charges you)
    floor = partner_margin_floor        (3PL minimum margin, USD/parcel)

In-house, per year at volume V:
    in_house_cost(V)   = cv*V + F
    in_house_margin(V) = (R - cv)*V - F
Partner (lease their capacity), per year at volume V:
    partner_cost(V)    = p*V
    partner_margin(V)  = (R - p)*V

The in-house all-in cost per parcel is ``cv + F/V``; the partner's is the
flat ``p``. In-house is cheaper exactly when

    cv + F/V <= p   <=>   V >= F / (p - cv)          [flip volume]

so the **flip volume** ``V* = F / (p - cv)`` is a closed form, and below
``V*`` you partner, above it you build.  ``p - cv`` is the cost gap the
hub's fixed cost has to be amortised over - a single, re-runnable number.

The 5-year PV break-even is the same boundary with the cost decay
(smaller volume -> denser routes -> ``cv`` falls ``cost_decay_per_year``
each year) and the committee's discount rate applied; it is strictly
<= ``V*`` and is a closed form too (a ratio of two annuity sums), pinned
against a numeric sweep in the tests.

Nothing here depends on the market size: the decision rests on cost,
capture and the partner rate, never on the SAM - which is exactly what
``data.sanity.cross_check`` proves.
"""

from __future__ import annotations

import math
from typing import Dict

import numpy as np

from data.facts import Facts

EPS = 1e-12


# ---------------------------------------------------------------------------
# per-parcel cost / margin primitives
# ---------------------------------------------------------------------------

def in_house_all_in_cost(f: Facts, volume: float, year: int = 1) -> float:
    """In-house all-in cost per parcel at ``volume`` in a given ``year``.

    = decayed marginal cost + hub fixed cost amortised over the volume.
    ``year`` enters through the cost decay (see ``decayed_var_cost``).
    """
    if volume <= 0:
        raise ValueError("volume must be > 0")
    cv_t = decayed_var_cost(f, year)
    return cv_t + f.hub_fixed_annual / volume


def partner_rate(f: Facts) -> float:
    return f.partner_rate_per_parcel


def in_house_beats_partner(f: Facts, volume: float, year: int = 1) -> bool:
    """True when in-house all-in cost/parcel <= partner rate this year."""
    if f.partner_rate_per_parcel - decayed_var_cost(f, year) <= 0:
        # partner is cheaper at every volume; in-house can never win
        return False
    return in_house_all_in_cost(f, volume, year) <= f.partner_rate_per_parcel + EPS


# ---------------------------------------------------------------------------
# the flip volume (the zero-line / decision boundary)
# ---------------------------------------------------------------------------

def flip_volume(f: Facts, year: int = 1) -> float:
    """The closed-form volume at which in-house all-in cost/parcel equals
    the partner rate: ``V* = F / (p - cv_t)``.

    Returns ``inf`` when ``p - cv_t <= 0`` - the partner's rate is at or
    below your marginal cost, so no volume makes in-house cheaper and the
    only option is partner (or decline if the partner margin is also gone).
    Year-1 (``year=1``) is the binding constraint because the cost decay
    only lowers ``V*`` in later years.
    """
    cv_t = decayed_var_cost(f, year)
    gap = f.partner_rate_per_parcel - cv_t
    if gap <= 0:
        return math.inf
    return f.hub_fixed_annual / gap


def pv_break_even_volume(f: Facts) -> float:
    """5-year PV break-even volume: the smallest constant annual volume V
    at which the discounted 5-yr in-house margin >= the 5-yr partner
    margin, given the cost decay and the committee discount rate.

    Closed form: ``V = F * A / B`` where
        A = sum_t df^t                          (annuity of the fixed cost)
        B = sum_t (p - cv_t) * df^t             (discounted cost-gap stream)
    df^t = 1/(1+wacc)^t.  Because ``cv_t`` decays, B/A > (p-cv_1), so
    ``V_pv < V*_1`` - the decay is worth real PV.  Returns inf when no
    positive gap stream exists.
    """
    wacc = f.discount_rate
    n = f.horizon_years
    num = 0.0    # F * sum_t df^t  (the fixed cost is constant each year)
    den = 0.0    # sum_t (p - cv_t) * df^t
    gap_neg = False
    for t in range(1, n + 1):
        df = 1.0 / (1.0 + wacc) ** t
        cv_t = decayed_var_cost(f, t)
        num += f.hub_fixed_annual * df
        den += (f.partner_rate_per_parcel - cv_t) * df
        if f.partner_rate_per_parcel - cv_t <= 0:
            gap_neg = True
    if den <= 0 or gap_neg:
        return math.inf
    return num / den


def decayed_var_cost(f: Facts, year: int) -> float:
    """In-house marginal cost in ``year`` after cost decay (route density
    + fleet scale): ``cv * (1 - cost_decay_per_year) ** (year - 1)``."""
    if year < 1:
        raise ValueError("year must be >= 1")
    return f.in_house_var_cost_per_parcel * (
        1.0 - f.cost_decay_per_year) ** (year - 1)


def partner_margin_per_parcel(f: Facts) -> float:
    """The contribution your partner keeps: ``R - p``.  Below
    ``partner_margin_floor`` the 3PL will not serve you - that is the
    decline trigger."""
    return f.revenue_per_parcel - f.partner_rate_per_parcel


def decline_rate(f: Facts) -> float:
    """The partner rate at which the partner margin falls to the floor:
    ``R - floor``.  Above this rate, partner (and hence the whole entry)
    is unprofitable - decline."""
    return f.revenue_per_parcel - f.partner_margin_floor


# ---------------------------------------------------------------------------
# the per-volume contribution tables the report / partner screenshots
# ---------------------------------------------------------------------------

def contribution_table(f: Facts, volumes) -> Dict:
    """For each volume: in-house vs partner all-in cost/parcel, the
    per-parcel margin for each, and which wins.  One row the client can
    read off without the model."""
    rows = []
    for v in volumes:
        v = float(v)
        ih_cost = in_house_all_in_cost(f, v)
        ih_margin = f.revenue_per_parcel - ih_cost
        par_cost = f.partner_rate_per_parcel
        par_margin = f.revenue_per_parcel - par_cost
        rows.append({
            "volume_per_year": v,
            "in_house_cost_pp": round(ih_cost, 4),
            "partner_cost_pp": round(par_cost, 4),
            "in_house_margin_pp": round(ih_margin, 4),
            "partner_margin_pp": round(par_margin, 4),
            "in_house_wins": in_house_beats_partner(f, v),
        })
    return {"volumes": rows,
            "flip_volume": flip_volume(f),
            "pv_break_even": pv_break_even_volume(f),
            "partner_margin_pp": partner_margin_per_parcel(f),
            "decline_rate": decline_rate(f)}
