"""The top-down sizing funnel: SAM -> serviceable -> capturable (C2).

This is the *context* block of the decision page - the number a partner
screenshots when they ask "how big is it and what would you ask first?".
It is deliberately separated from the *pivot* (cost, capture and the
partner rate) that actually decides enter / partner / decline.  ``data.
sanity.cross_check`` locks that separation: halve the funnel and the flip
volume does not move, because the funnel sets headroom, not the trigger.

The funnel, each stage a named parcel flow with its own confidence tag
carried in from ``data.facts``:

    US total parcels/yr            124.9B   EST   (Menzies Parcel Economy)
    x e-commerce last-mile slice      .30   EST   (~30% of US parcels)
    -> e-comm last-mile parcels/yr   37.5B   EST
    x one-metro serviceable share     .02   EST   (one large metro)
    -> serviceable (SAM) parcels/yr 0.75B   EST
    x capture rate                    .03   EST   (CAC + retention,
                                                  committee input)
    -> capturable parcels/yr         22.5M   EST

The USPS commercial-package figure (53.5B, CONFIRMED) is kept as an
independent *anchor*: it is a filed number, not our estimate, and the
screenshot reads "our EST top-down lands inside the filed envelope".

Nothing here is the decision.  The decision rests on cost-to-serve and
the partner rate; the funnel tells the client how much headroom sits
*above* the flip volume - the room to grow before the network is full.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from data.facts import Facts, USPS_COMMERCIAL_PARCELS_BILLION


def _stage(name: str, parcels_per_year: float, share_applied: float,
           confidence: str, note: str = "") -> Dict:
    return {
        "stage": name,
        "parcels_per_year": parcels_per_year,
        "share_applied": share_applied,
        "confidence": confidence,
        "note": note,
    }


def e_comm_last_mile_billion(f: Facts) -> float:
    """US e-commerce last-mile parcels/yr: the national parcel flow times
    the e-commerce slice.  EST (both factors are estimates)."""
    return f.us_total_parcels_billion * f.e_comm_last_mile_share


def serviceable_billion(f: Facts) -> float:
    """The Serviceable Addressable Market - one large metro's e-commerce
    last-mile parcel flow.  EST.  This is the SAM the funnel funnels to."""
    return e_comm_last_mile_billion(f) * f.metro_serviceable_share


def capturable_parcels(f: Facts) -> float:
    """The capturable flow at the stated capture rate - the realistic
    ceiling on annual parcels the entry can take in one metro.  EST."""
    return serviceable_billion(f) * 1e9 * f.capture_rate


def funnel(f: Facts) -> Dict:
    """The partner-screenshot table: every stage of the top-down funnel
    with its value, the share that produced it, and its confidence tag."""
    us_total = f.us_total_parcels_billion
    e_comm = e_comm_last_mile_billion(f)
    sam = serviceable_billion(f)
    cap = capturable_parcels(f)
    stages: List[Dict] = [
        _stage("US total parcels/yr", us_total * 1e9, 1.0,
               f.market_confidence,
               "national parcel flow (Menzies, EST)"),
        _stage("e-comm last-mile slice", e_comm * 1e9,
               f.e_comm_last_mile_share, "EST",
               f"~{f.e_comm_last_mile_share:.0%} of US parcels are "
               f"e-commerce last-mile"),
        _stage("serviceable (SAM, one metro)", sam * 1e9,
               f.metro_serviceable_share, "EST",
               f"one large metro ~{f.metro_serviceable_share:.0%} of "
               f"national e-comm flow"),
        _stage("capturable @ capture rate", cap, f.capture_rate, "EST",
               f"capture {f.capture_rate:.0%} of the SAM (CAC + "
               f"retention, committee input)"),
    ]
    return {
        "stages": stages,
        "sam_billion": sam,
        "capturable_parcels": cap,
        "anchor": {
            "usps_commercial_parcels_billion": USPS_COMMERCIAL_PARCELS_BILLION,
            "confidence": "CONFIRMED",
            "note": ("independent filed anchor (USPS 2023 commercial-package "
                     "figure); the EST top-down lands inside this envelope"),
        },
    }


def cac_payback(f: Facts) -> Dict:
    """Parcels of contribution a single customer's flow must clear to
    recover the annual CAC, on each yardstick the decision page uses.

    ``cac_per_customer`` is a USD/yr acquisition cost (ad + first-parcel
    discount).  The payback is measured in parcels of *contribution
    margin* - the in-house yardstick (``R - cv``) is fast; the partner
    yardstick (``R - p``) is the thin sliver a 3PL leaves you, and the
    contrast is the finding: acquiring a customer is only cheap when you
    own the margin, not when you lease it.  Below the partner margin
    floor the partner number is ``inf`` - the customer is never
    economical to acquire through a 3PL at that rate.
    """
    R = f.revenue_per_parcel
    cv = f.in_house_var_cost_per_parcel
    p = f.partner_rate_per_parcel
    cac = f.cac_per_customer

    ih_margin = R - cv
    par_margin = R - p

    ih_parcels = cac / ih_margin if ih_margin > 0 else float("inf")
    par_parcels = (cac / par_margin if par_margin >= f.partner_margin_floor
                   else float("inf"))
    return {
        "cac_per_customer": cac,
        "in_house_margin_pp": round(ih_margin, 4),
        "partner_margin_pp": round(par_margin, 4),
        "parcels_to_recover_cac_in_house": _fmt(ih_parcels),
        "parcels_to_recover_cac_partner": _fmt(par_parcels),
        "note": ("acquiring a customer pays back fast on the in-house "
                 "yardstick and slowly (or never) on the partner one - "
                 "the margin you keep, not the price you pay, sets CAC "
                 "payback"),
    }


def headroom(f: Facts) -> Dict:
    """How much room the funnel leaves *above* the flip volume - the
    growth story the decision page pairs with the trigger.  If the
    capturable flow is far above the in-house break-even, entering at the
    launch wedge sits well inside the SAM; the SAM sets headroom, not the
    decision."""
    from . import unit_economics as ue
    cap = capturable_parcels(f)
    flip = ue.flip_volume(f)
    pv = ue.pv_break_even_volume(f)
    return {
        "capturable_parcels": cap,
        "flip_volume": _fmt(flip),
        "pv_break_even_volume": _fmt(pv),
        "headroom_over_flip": None if flip in (float("inf"),)
        else cap - flip,
        "headroom_multiple": None if flip in (float("inf"),)
        else cap / flip,
        "note": ("the SAM sets how far the network can grow before it is "
                 "full - not whether to enter.  Enter/partner/decline is "
                 "the flip volume; this is the runway beyond it."),
    }


def _fmt(x: Optional[float]) -> Optional[float]:
    """Round for the screenshot; keep inf/null honest."""
    if x is None:
        return None
    if x in (float("inf"), float("-inf")):
        return float("inf")
    return float(round(x, 2))


if __name__ == "__main__":
    import json
    f = Facts()
    print(json.dumps(funnel(f), indent=2, default=float))
    print(json.dumps(cac_payback(f), indent=2, default=float))
    print(json.dumps(headroom(f), indent=2, default=float))
