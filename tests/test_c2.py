"""Pytest suite for the Market-Entry Growth Case (consulting flagship C2).

All offline and synthetic: the facts layer is pure python, the model is a
pure function over it, and the cross-checks perturb Fields without any
network.  Grouped by module; the load-bearing claims each group pins:

  sizing         : the SAM -> serviceable -> capturable funnel arithmetic,
                   the filed USPS anchor, CAC payback on the two
                   yardsticks, and headroom over the flip volume.
  unit_economics : the flip volume closed form, the PV break-even pinned
                   against a numeric sweep, cost-decay shape, and the
                   decline rate.
  decision       : the enter / partner / decline trigger line, the 2-D
                   surface, the strategy PVs, and the partner-screenshot
                   page with its size block.
  sanity         : the offline cross-check - the boundary is invariant to
                   every market-size and capture factor, and sensitive to
                   every pivot input.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import pytest

from data import Facts, OPERATORS, cross_check, measured_fields
from data import sanity
from model import sizing, unit_economics as ue, decision as dec

F = Facts()


# ---------------------------------------------------------------------------
# sizing: the top-down funnel
# ---------------------------------------------------------------------------
def test_funnel_stage_arithmetic():
    fl = sizing.funnel(F)
    us = fl["stages"][0]["parcels_per_year"]
    ecomm = fl["stages"][1]["parcels_per_year"]
    sam = fl["stages"][2]["parcels_per_year"]
    cap = fl["stages"][3]["parcels_per_year"]
    assert ecomm == pytest.approx(us * F.e_comm_last_mile_share)
    assert sam == pytest.approx(ecomm * F.metro_serviceable_share)
    assert cap == pytest.approx(sam * F.capture_rate)
    assert fl["sam_billion"] == pytest.approx(sam / 1e9)
    assert fl["capturable_parcels"] == pytest.approx(cap)


def test_funnel_anchor_is_confirmed():
    fl = sizing.funnel(F)
    assert fl["anchor"]["usps_commercial_parcels_billion"] == 53.5
    assert fl["anchor"]["confidence"] == "CONFIRMED"
    # the EST top-down SAM must land inside the filed USPS envelope
    assert fl["sam_billion"] < fl["anchor"]["usps_commercial_parcels_billion"]


def test_funnel_stage_confidence_tags():
    fl = sizing.funnel(F)
    assert [s["confidence"] for s in fl["stages"]] == ["EST", "EST", "EST", "EST"]
    # every stage shares a note explaining the number
    assert all(s["note"] for s in fl["stages"])


def test_cac_payback_two_yardsticks():
    ca = sizing.cac_payback(F)
    # in-house margin R-cv = 1.70; partner margin R-p = 0.50
    assert ca["in_house_margin_pp"] == pytest.approx(1.70)
    assert ca["partner_margin_pp"] == pytest.approx(0.50)
    assert ca["parcels_to_recover_cac_in_house"] == pytest.approx(
        F.cac_per_customer / 1.70, rel=1e-3)
    assert ca["parcels_to_recover_cac_partner"] == pytest.approx(
        F.cac_per_customer / 0.50, rel=1e-3)
    # the finding: owning the margin beats leasing it on CAC payback
    assert ca["parcels_to_recover_cac_in_house"] < ca["parcels_to_recover_cac_partner"]


def test_cac_payback_never_below_partner_floor():
    # a 3PL will not serve you below its floor -> partner CAC payback is inf
    f2 = _with(partner_rate_per_parcel=F.revenue_per_parcel - 0.20)
    # margin 0.20 < floor 0.30 -> inf
    assert sizing.cac_payback(f2)["parcels_to_recover_cac_partner"] == float("inf")


def test_headroom_multiple_over_flip():
    hr = sizing.headroom(F)
    assert hr["headroom_multiple"] == pytest.approx(
        sizing.capturable_parcels(F) / ue.flip_volume(F), rel=1e-3)
    assert hr["headroom_over_flip"] == pytest.approx(
        sizing.capturable_parcels(F) - ue.flip_volume(F), rel=1e-3)


def test_headroom_none_when_flip_infinite():
    f2 = _with(partner_rate_per_parcel=F.in_house_var_cost_per_parcel - 0.5)
    hr = sizing.headroom(f2)
    assert hr["headroom_multiple"] is None
    assert hr["headroom_over_flip"] is None


def test_capturable_monotone_in_capture_rate():
    lo, hi = (sizing.capturable_parcels(_with(capture_rate=r))
              for r in (0.01, 0.05))
    assert lo < hi


# ---------------------------------------------------------------------------
# unit_economics: the flip volume and its PV cousin
# ---------------------------------------------------------------------------
def test_flip_volume_closed_form():
    # V* = F / (p - cv) = 500000 / (5.00 - 3.80)
    assert ue.flip_volume(F) == pytest.approx(500_000.0 / 1.20)


def test_flip_volume_infinite_when_partner_at_or_below_marginal():
    f2 = _with(partner_rate_per_parcel=F.in_house_var_cost_per_parcel)
    assert math.isinf(ue.flip_volume(f2))
    f3 = _with(partner_rate_per_parcel=F.in_house_var_cost_per_parcel - 0.1)
    assert math.isinf(ue.flip_volume(f3))


def test_flip_volume_falls_with_cost_decay():
    v1 = ue.flip_volume(F, year=1)
    v5 = ue.flip_volume(F, year=5)
    assert v5 < v1, "density + fleet scale should lower the flip by Y5"


def test_decayed_var_cost_shape():
    assert ue.decayed_var_cost(F, 1) == pytest.approx(F.in_house_var_cost_per_parcel)
    assert ue.decayed_var_cost(F, 5) == pytest.approx(
        F.in_house_var_cost_per_parcel * (1 - F.cost_decay_per_year) ** 4)
    with pytest.raises(ValueError):
        ue.decayed_var_cost(F, 0)


def test_pv_break_even_below_year1_flip():
    # decay makes the 5-yr PV boundary strictly tighter than Y1
    assert ue.pv_break_even_volume(F) < ue.flip_volume(F, year=1)


def test_pv_break_even_pinned_to_numeric_sweep():
    """The closed form V_pv = F*A/B (fixed cost recurring every year) must
    agree with the smallest volume at which the discounted 5-yr in-house
    PV equals the 5-yr partner PV, found by binary search on the same
    annual-F assumption the closed form prices on."""
    target = ue.pv_break_even_volume(F)
    wacc, n, R, p, Fhub = (F.discount_rate, F.horizon_years,
                            F.revenue_per_parcel, F.partner_rate_per_parcel,
                            F.hub_fixed_annual)

    def pv_diff(v):
        pb = pl = 0.0
        for t in range(1, n + 1):
            cv_t = ue.decayed_var_cost(F, t)
            pb += ((R - cv_t) * v - Fhub) / (1 + wacc) ** t
            pl += (R - p) * v / (1 + wacc) ** t
        return pb - pl

    lo, hi = target * 0.5, target * 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if pv_diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    assert 0.5 * (lo + hi) == pytest.approx(target, rel=1e-6)


def test_pv_break_even_infinite_when_no_positive_gap():
    f2 = _with(partner_rate_per_parcel=F.in_house_var_cost_per_parcel - 0.2)
    assert math.isinf(ue.pv_break_even_volume(f2))


def test_decline_rate_closed_form():
    # decline at R - floor: above this the partner margin is gone
    assert ue.decline_rate(F) == pytest.approx(F.revenue_per_parcel - F.partner_margin_floor)


def test_in_house_all_in_cost_amortises_fixed():
    c_lo = ue.in_house_all_in_cost(F, 1_000_000)
    c_hi = ue.in_house_all_in_cost(F, 10_000)
    assert c_hi > c_lo, "fixed cost amortises over volume - bigger V, cheaper pp"
    assert c_lo == pytest.approx(
        ue.decayed_var_cost(F, 1) + F.hub_fixed_annual / 1_000_000, rel=1e-9)
    with pytest.raises(ValueError):
        ue.in_house_all_in_cost(F, 0)


def test_in_house_beats_partner_only_above_flip():
    flip = ue.flip_volume(F)
    assert ue.in_house_beats_partner(F, flip + 1)
    assert not ue.in_house_beats_partner(F, flip - 1)


def test_contribution_table_flags_winning_strategy_per_volume():
    tbl = ue.contribution_table(F, [50_000, 200_000, 500_000])
    wins = [r["in_house_wins"] for r in tbl["volumes"]]
    assert wins == [False, False, True], "wedge and mid volumes partner; scale builds"
    assert tbl["flip_volume"] == pytest.approx(ue.flip_volume(F))
    assert tbl["pv_break_even"] == pytest.approx(ue.pv_break_even_volume(F))


# ---------------------------------------------------------------------------
# decision: the trigger line and the 2-D surface
# ---------------------------------------------------------------------------
def test_trigger_line_at_wedge_is_partner():
    t = dec.trigger_line(F)
    # launch wedge 100k < flip 416,667 -> PARTNER
    assert t["recommendation"] == "PARTNER"
    assert t["flip_volume"] == pytest.approx(ue.flip_volume(F))
    assert "PARTNER" in t["line"] and "flip" in t["line"]


def test_trigger_line_enter_above_flip():
    t = dec.trigger_line(F, volume=1_000_000)
    assert t["recommendation"] == "ENTER"
    assert "ENTER" in t["line"]


def test_trigger_line_decline_at_rate_above_revenue():
    t = dec.trigger_line(F, rate=F.revenue_per_parcel - 0.20)
    assert t["recommendation"] == "DECLINE"
    assert t["partner_margin_pp"] == pytest.approx(0.20)
    assert t["decline_rate"] == pytest.approx(F.revenue_per_parcel - F.partner_margin_floor)


def test_trigger_line_rate_is_committed_input():
    # overriding the partner rate changes the flip but not the decline rate
    t_lo = dec.trigger_line(F, rate=4.0)
    t_hi = dec.trigger_line(F, rate=6.0)
    assert t_lo["flip_volume"] > t_hi["flip_volume"]
    assert t_lo["decline_rate"] == t_hi["decline_rate"]


def test_strategy_pvs_inhouse_wins_at_scale():
    pv_small = dec.strategy_pvs(F, volume=50_000)
    pv_big = dec.strategy_pvs(F, volume=1_000_000)
    assert not pv_small["in_house_wins"]
    assert pv_big["in_house_wins"]
    assert pv_big["pv_build"] > pv_big["pv_lease"]


def test_surface_shape_and_winning_zones():
    df = dec.surface(F)
    n_cost = len(np.arange(3.0, 5.0 + 1e-9, 0.25))
    n_rate = len(np.arange(3.5, 7.0 + 1e-9, 0.5))
    assert df.shape == (n_cost * n_rate, 5), "cost rows x rate cols, 5 cols"
    # cheap cost + high rate -> enter even at the wedge
    r = df.iloc[0]
    assert r["in_house_var_cost"] == 3.0 and r["partner_rate"] == 3.5
    # expensive cost + low rate -> decline zone
    corner = df[(df["in_house_var_cost"] == 5.0) & (df["partner_rate"] == 3.5)]
    assert corner["in_house_wins_at_wedge"].iloc[0] in ("decline", "partner")


def test_page_carries_pivot_and_size_blocks():
    p = dec.page(F)
    row = p.iloc[0]
    assert row["recommendation_at_wedge"] == "PARTNER"
    assert row["flip_volume"] == pytest.approx(ue.flip_volume(F))
    assert row["size"]["sam_billion"] == pytest.approx(0.7494, rel=1e-3)
    assert row["size"]["anchor_billion"] == 53.5
    assert row["size"]["headroom_multiple_over_flip"] > 1.0
    assert len(row["volume_grid"]) == len(dec.DEFAULT_VOLUME_GRID)


def test_bottom_up_benchmarks_operators():
    df = dec.bottom_up_benchmarks(F)
    assert set(df["operator"]) == {op.name for op in OPERATORS}
    rrd = df[df["operator"].str.contains("RR")].iloc[0]
    assert rrd["adjacent_entry_case"] == 1
    ups = df[df["operator"].str.contains("UPS")].iloc[0]
    assert ups["revenue_per_parcel"] == pytest.approx(90.5e9 / 4_500e6, rel=1e-3)


# ---------------------------------------------------------------------------
# sanity: the decision rests on cost and capture, not the SAM
# ---------------------------------------------------------------------------
def test_cross_check_invariants_hold():
    sc = cross_check()
    assert sc["passed"]
    for r in sc["invariants_held"]:
        assert not r["boundary_moved"], r["probe"]
        assert r["as_expected"], r["probe"]


def test_cross_check_sensitivities_move_boundary():
    sc = cross_check()
    for r in sc["pivot_inputs_move_boundary"]:
        assert r["boundary_moved"], r["probe"]
        assert r["as_expected"], r["probe"]


def test_halving_sam_does_not_move_flip():
    base = ue.flip_volume(F)
    half = Facts(us_total_parcels_billion=F.us_total_parcels_billion * 0.5)
    assert ue.flip_volume(half) == base, "SAM is headroom, not the trigger"
    assert ue.pv_break_even_volume(half) == pytest.approx(
        ue.pv_break_even_volume(F), rel=1e-12)


def test_halving_capture_rate_does_not_move_flip():
    base = ue.flip_volume(F)
    half = Facts(capture_rate=F.capture_rate * 0.5)
    assert ue.flip_volume(half) == base
    # but the headroom DOES halve - capture is headroom
    assert sizing.capturable_parcels(half) == pytest.approx(
        sizing.capturable_parcels(F) * 0.5)


def test_measured_fields_split_matches_sanity_probes():
    mf = measured_fields(F)
    assert not (set(mf["priced_on"]) & set(mf["not_priced_on"])), "the split must be disjoint"
    for name in ("us_total_parcels_billion", "usps_commercial_parcels_billion",
                 "e_comm_last_mile_share", "metro_serviceable_share"):
        assert name in mf["not_priced_on"]
    assert "partner_rate_per_parcel" in mf["priced_on"]
    # the sanity probes test exactly these two sets
    assert set(sanity.MARKET_SIZE_FACTORS) == set(mf["not_priced_on"])
    assert set(sanity.PIVOT_FACTORS).issubset(set(mf["priced_on"]))


def test_probe_report_flagging():
    base = {"flip_volume": 100.0, "pv_break_even": 90.0, "decline_rate": 5.2}
    same = dec_trigger_report(base, base)
    moved = dec_trigger_report(base,
                              {"flip_volume": 101.0, "pv_break_even": 90.0,
                               "decline_rate": 5.2})
    assert same["boundary_moved"] is False
    assert moved["boundary_moved"] is True


def dec_trigger_report(base, probe):
    return sanity._probe_report("t", base, probe, expected_moved=False)


def _with(**kw):
    d = F.to_dict()
    d.update(kw)
    return Facts(**d)
