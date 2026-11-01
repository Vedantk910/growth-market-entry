"""Offline cross-checks for the C2 decision page - no network, no cache.

The whole point of the decision tool is that enter / partner / decline is
priced on **cost-to-serve, capture and the partner rate** - NOT on the
market size.  ``data.facts.measured_fields`` states that split; this module
*proves* it so the case can say the trigger is a number, not the SAM.

``cross_check`` perturbs a ``Facts`` object in two directions and reads the
decision boundary off the model each time:

* **invariance to market size.**  Halve any of the top-down funnel factors
  (US total parcels, the USPS filed anchor, the e-commerce slice, the
  metro share) - the flip volume and the PV break-even do not move, to the
  last bit.  The SAM sets headroom, not the trigger.
* **capture is headroom, not the boundary.**  Halving the capture rate also
  leaves the flip volume and PV break-even fixed - capture decides how much
  of the funnel you actually take, which side of the flip volume the entry
  lands on.  The boundary itself is cost-driven.
* **sensitivity to the pivot.**  Perturbing any decision input - partner
  rate, in-house variable cost, hub fixed cost, the partner margin floor -
  moves the boundary.  These are the numbers the case is priced on.

If ``passed`` is True, every invariance held and every pivot input moved
the boundary - the split the decision page claims is genuinely the split
the model behaves as.  This is the offline twin of C1's EDGAR sanity
check: same discipline (a small, re-runnable proof), no fetch.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from data.facts import Facts

# factors that scale the top-down funnel (SAM / serviceable / capturable).
# halving any of these must NOT move the decision boundary.
MARKET_SIZE_FACTORS = (
    "us_total_parcels_billion",
    "usps_commercial_parcels_billion",
    "e_comm_last_mile_share",
    "metro_serviceable_share",
)

# the capture rate sets how much of the SAM you take - headroom, not the
# boundary.  Halving it must NOT move the flip volume / PV break-even.
CAPTURE_FACTOR = "capture_rate"

# the decision pivot.  perturbing any of these MUST move the boundary -
# these are exactly the inputs the case is priced on.
PIVOT_FACTORS = (
    "partner_rate_per_parcel",
    "in_house_var_cost_per_parcel",
    "hub_fixed_annual",
    "partner_margin_floor",
)

_TOL = 1e-9


def _probe(f: Facts, **overrides) -> Facts:
    """A copy of ``f`` with the named fields overridden - the pure-python
    way to perturb one input without touching the caller's object."""
    d = f.to_dict()
    d.update(overrides)
    return Facts(**d)


def _boundary(f: Facts) -> Dict[str, float]:
    """The decision boundary under a given Facts: the two quantities the
    invariance / sensitivity claims are about."""
    from model import unit_economics as ue  # local import: no module cycle
    return {
        "flip_volume": ue.flip_volume(f),
        "pv_break_even": ue.pv_break_even_volume(f),
        "decline_rate": ue.decline_rate(f),
    }


def _moved(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """True if any boundary quantity moved beyond float noise."""
    return any(abs(a[k] - b[k]) > _TOL for k in a)


def cross_check(f: Optional[Facts] = None) -> Dict:
    """Run every invariance and sensitivity probe; return the evidence.

    Returns a dict with ``passed`` (all invariants held AND every pivot
    input moved the boundary), plus the per-factor evidence so a notebook
    cell can render the proof, not just the verdict.
    """
    f = Facts() if f is None else f
    base = _boundary(f)

    invariants: List[Dict] = []
    for field in MARKET_SIZE_FACTORS:
        probe = _probe(f, **{field: getattr(f, field) * 0.5})
        invariants.append(_probe_report("half " + field, base, _boundary(probe),
                                        expected_moved=False))

    cap_probe = _probe(f, **{CAPTURE_FACTOR: getattr(f, CAPTURE_FACTOR) * 0.5})
    invariants.append(_probe_report("half capture (headroom)", base,
                                    _boundary(cap_probe), expected_moved=False))

    sensitivities: List[Dict] = []
    for field in PIVOT_FACTORS:
        probe = _probe(f, **{field: getattr(f, field) * 1.10})
        sensitivities.append(_probe_report("raise " + field, base,
                                          _boundary(probe),
                                          expected_moved=True))

    passed = (all(not r["boundary_moved"] for r in invariants)
              and all(r["boundary_moved"] for r in sensitivities))

    return {
        "passed": passed,
        "boundary_at_base": {k: (v if math.isfinite(v) else None)
                             for k, v in base.items()},
        "invariants_held": invariants,
        "pivot_inputs_move_boundary": sensitivities,
        "note": ("the enter/partner/decline trigger is a function of "
                 "cost-to-serve and the partner rate - the SAM and the "
                 "capture rate set how much you take, never the flip "
                 "volume.  This is the claim the decision page makes, and "
                 "it is what the model behaves as."),
    }


def _probe_report(label: str, base: Dict[str, float],
                  probe: Dict[str, float],
                  expected_moved: bool) -> Dict:
    moved = _moved(base, probe)
    ok = (moved if expected_moved else not moved)
    return {
        "probe": label,
        "base_flip_volume": _clean(base["flip_volume"]),
        "probe_flip_volume": _clean(probe["flip_volume"]),
        "boundary_moved": moved,
        "as_expected": ok,
    }


def _clean(x: float) -> Optional[float]:
    return None if not math.isfinite(x) else float(x)


if __name__ == "__main__":
    import json
    print(json.dumps(cross_check(), indent=2, default=float))
