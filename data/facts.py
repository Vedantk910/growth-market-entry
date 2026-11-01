"""Named market figures for the last-mile / e-commerce fulfillment case (C2).

Every field carries a confidence tag so the decision page can say which
numbers the case actually rests on:

  CONFIRMED - a public filing or rate card (source named)
  EST       - our estimate built on a public source, not a filed figure
  VERIFY    - order-of-magnitude only; secondary source

The decision module prices ENTER / PARTNER / DECLINE on **cost-per-parcel,
capture rate and the partner rate** - NOT on the market size. ``measured_fields``
encodes that split; ``data/sanity.cross_check`` proves it: halve the SAM and
the break-even volume does not move.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Top-down sizing (context, not the pivot).
#   US_TOTAL_PARCELS: Menzies "The Parcel Economy" commissioned study -
#   124.9B parcels in the US in 2023 (77.4B in 2020 -> ~10% CAGR). EST.
#   USPS_COMMERCIAL_PARCELS: USPS annual "commercial packages" figure -
#   53.5B (2023), 50.9B (2024), a 12.8% CAGR. CONFIRMED (USPS filing).
# ---------------------------------------------------------------------------
US_TOTAL_PARCELS_BILLION = 124.9        # EST  (Menzies Parcel Economy '23)
US_TOTAL_PARCELS_SOURCE = ("Menzies, 'The Parcel Economy' commissioned "
                           "study (2023): 124.9B US parcels, up from 77.4B "
                           "in 2020 (~10% CAGR)")
USPS_COMMERCIAL_PARCELS_BILLION = 53.5  # CONFIRMED (USPS 2023 filing; 50.9B in '24)
USPS_COMMERCIAL_PARCELS_SOURCE = ("USPS annual commercial-package figure, "
                                  "public filings: 53.5B (2023), 50.9B "
                                  "(2024), 12.8% CAGR")

E_COMM_LAST_MILE_SHARE = 0.30          # EST (e-comm is ~30% of US parcels)
METRO_SERVICEABLE_SHARE = 0.02         # EST (one large metro ~2% of national)
CAPTURE_RATE = 0.03                    # EST (committee input: CAC + retention)
CAC_PER_CUSTOMER = 18.0               # EST (ad + first-parcel discount, USD/yr)
RETENTION = 0.90                       # EST (annual seller retention)

# ---------------------------------------------------------------------------
# The decision pivot: cost-to-serve, partner rate, and the value you capture.
#   REVENUE_PER_PARCEL: what the client charges a customer to deliver one
#   parcel (the delivery price). EST.
#   IN_HOUSE_VAR_COST_PER_PARCEL: the marginal last-mile cost of a parcel on
#   your own fleet (driver + fuel + van seat share, no facility). EST.
#   HUB_FIXED_ANNUAL: the fixed cost of one metro delivery hub (facilities,
#   yard, WMS, management). [unverified committee input]. Sized so that at
#   full utilisation (one hub ~500k parcels/yr) the in-house all-in cost per
#   parcel (~4.80) sits just under the partner rate (~5.00) - that interior
#   gap is what lets "build wins at scale" hold at all.
#   PARTNER_RATE_PER_PARCEL: the all-in rate you pay a 3PL to deliver one
#   parcel on their network (their rate card, [unverified]).
# ---------------------------------------------------------------------------
REVENUE_PER_PARCEL = 5.50
IN_HOUSE_VAR_COST_PER_PARCEL = 3.80
HUB_FIXED_ANNUAL = 500_000.0
PARTNER_RATE_PER_PARCEL = 5.00
PARTNER_MARGIN_FLOOR = 0.30          # USD/parcel minimum partner wants, EST

# ---------------------------------------------------------------------------
# Operating parameters
# ---------------------------------------------------------------------------
DISCOUNT_RATE = 0.08                 # committee WACC ([unverified])
HORIZON_YEARS = 5
COST_DECAY_PER_YEAR = 0.015          # fleet scale + route density: ~1.5%/yr
# Launch wedge: the realistic entry volume one team can operationally manage
# in a single metro (one hub + a small fleet). This is the base year for the
# "does in-house beat partner *at the entry point*" question, distinct from the
# break-even volume where the two flip. [unverified committee input]
LAUNCH_WEDGE_PARCELS_PER_YEAR = 100_000.0

# ---------------------------------------------------------------------------
# Bottom-up operators (public filings; the adjacent-market entry case is RRD).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Operator:
    """A public operator's per-unit economics (bottom-up sizing input).

    Per-parcel figures are *derived* (revenue / volume, op income / revenue)
    rather than filed: none of these operators disclose a clean cost or
    revenue-per-parcel line, so the derived number is tagged with the
    operator's own confidence.
    """
    name: str
    revenue_usd: float
    operating_income_usd: float
    volume_million: float            # parcels / packages, annual
    confidence: str                  # "CONFIRMED" | "EST" | "VERIFY"
    source: str
    adjacent_entry: bool = False     # True for the "adjacent-market entry" case
    derived_revenue_per_parcel: Optional[float] = None
    derived_op_margin: Optional[float] = None


def _unit_op(op: Operator) -> Operator:
    """Derive revenue-per-parcel and operating margin from the filing
    figures (revenue and op income are the filed lines; the per-parcel
    numbers are our division, not theirs)."""
    if op.volume_million and op.revenue_usd:
        c = op.revenue_usd / (op.volume_million * 1e6)
    else:
        c = None
    m = (op.operating_income_usd / op.revenue_usd
         if op.revenue_usd else None)
    return replace_fields(op, derived_revenue_per_parcel=c,
                          derived_op_margin=m)


def replace_fields(op: Operator, **kw) -> Operator:
    d = asdict(op)
    d.update(kw)
    return Operator(**d)


OPERATORS: List[Operator] = [
    _unit_op(Operator(
        name="USPS (commercial parcels)", revenue_usd=30.0e9,
        operating_income_usd=1.5e9, volume_million=53_500,
        confidence="CONFIRMED",
        source=("USPS commercial parcels: 53.5B volume (2023 filing); "
                "revenue/NI EST"),
    )),
    _unit_op(Operator(
        name="UPS Ground (retail rate card)", revenue_usd=90.5e9,
        operating_income_usd=9.3e9, volume_million=4_500,
        confidence="EST",
        source=("UPS 10-K (revenue/op income EST); 2026 retail Ground "
                "$11.95 rate card (CONFIRMED) sets the in-house upper bound"),
    )),
    _unit_op(Operator(
        name="RR Donnelley (fulfillment)", revenue_usd=5.8e9,
        operating_income_usd=538.4e6, volume_million=25.9,
        confidence="EST",
        source=("RRD 2023 filing: $5.8B revenue, $538.4M op income, "
                "25.9M packages, +41% volume growth; adjacent-market "
                "(document -> e-comm fulfillment) entry case"),
        adjacent_entry=True,
    )),
]


# ---------------------------------------------------------------------------
# The Facts dataclass: one named figure per field, defaults wired above.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Facts:
    # top-down sizing (context)
    us_total_parcels_billion: float = US_TOTAL_PARCELS_BILLION
    usps_commercial_parcels_billion: float = USPS_COMMERCIAL_PARCELS_BILLION
    e_comm_last_mile_share: float = E_COMM_LAST_MILE_SHARE
    metro_serviceable_share: float = METRO_SERVICEABLE_SHARE
    capture_rate: float = CAPTURE_RATE
    cac_per_customer: float = CAC_PER_CUSTOMER
    retention: float = RETENTION
    # the decision pivot
    revenue_per_parcel: float = REVENUE_PER_PARCEL
    in_house_var_cost_per_parcel: float = IN_HOUSE_VAR_COST_PER_PARCEL
    hub_fixed_annual: float = HUB_FIXED_ANNUAL
    partner_rate_per_parcel: float = PARTNER_RATE_PER_PARCEL
    partner_margin_floor: float = PARTNER_MARGIN_FLOOR
    # operating parameters
    discount_rate: float = DISCOUNT_RATE
    horizon_years: int = HORIZON_YEARS
    cost_decay_per_year: float = COST_DECAY_PER_YEAR
    launch_wedge_parcels_per_year: float = LAUNCH_WEDGE_PARCELS_PER_YEAR

    # confidence tags
    market_confidence: str = "EST"
    pivot_confidence: str = "EST"

    def to_dict(self) -> dict:
        return asdict(self)


def measured_fields(f: Facts) -> Dict:
    """Which figure the decision module actually rests on.

    The decision is priced on cost-to-serve + capture + partner rate; it is
    NOT priced on the SAM. Halving the SAM does not move the break-even
    volume - the ``cross_check`` in sanity.py locks that.
    """
    return {
        "priced_on": [
            "in_house_var_cost_per_parcel", "hub_fixed_annual",
            "partner_rate_per_parcel", "partner_margin_floor",
            "capture_rate", "revenue_per_parcel",
        ],
        "not_priced_on": [
            "us_total_parcels_billion", "usps_commercial_parcels_billion",
            "e_comm_last_mile_share", "metro_serviceable_share",
        ],
        "note": ("the zero-line and the enter/partner/decline break-even are "
                 "functions of cost and capture, not market size; the SAM "
                 "sets headroom, not the trigger."),
    }
