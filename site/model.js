(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.MEModel = factory(); }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // The repo's committee baseline (data/facts.py defaults) — the "repo
  // baseline" preset restores exactly these.
  var DEFAULTS = {
    volume: 100000, p: 5.00, cv: 3.80, F: 500000.0, R: 5.50, floor: 0.30,
    wacc: 0.08, decay: 0.015, cac: 18.0,
    usTotal: 124.9, ecomm: 0.30, metro: 0.02, capture: 0.03,
    uspsAnchor: 53.5
  };

  // ------------------------------------------------------------------
  // per-parcel cost / margin primitives (mirror model/unit_economics.py)
  // ------------------------------------------------------------------
  function decayedCV(cv, decay, year) {
    return cv * Math.pow(1 - decay, year - 1);
  }

  // flip volume: in-house all-in cv + F/V <= p  <=>  V >= F / (p - cv)
  function flipVolume(F, p, cv) {
    var gap = p - cv;
    return gap <= 0 ? Infinity : F / gap;
  }

  // 5-yr PV break-even: closed form V = F*A / B, A/B discounted annuity
  // sums (mirror pv_break_even_volume, pinned to a binary-search sweep).
  function pvBreakEven(F, p, cv, decay, horizon, wacc) {
    var num = 0, den = 0, bad = false;
    for (var t = 1; t <= horizon; t++) {
      var df = Math.pow(1 + wacc, -t);
      var cvt = decayedCV(cv, decay, t);
      num += F * df;
      den += (p - cvt) * df;
      if (p - cvt <= 0) { bad = true; }
    }
    if (den <= 0 || bad) { return Infinity; }
    return num / den;
  }

  function inHouseAllIn(cv, decay, F, v, year) {
    return decayedCV(cv, decay, year || 1) + F / v;
  }

  function partnerMargin(R, p) { return R - p; }
  function declineRate(R, floor) { return R - floor; }
  function annuity(wacc, n) { return wacc === 0 ? n : (1 - Math.pow(1 + wacc, -n)) / wacc; }

  // build-vs-lease PV at a fixed volume (mirror strategy_pvs: the hub's
  // fixed cost is a recurring per-year facility cost, charged every year)
  function strategyPVs(inp, volume, years) {
    years = years || 5;
    var pvBuild = 0;
    for (var t = 1; t <= years; t++) {
      var cvt = decayedCV(inp.cv, inp.decay, t);
      pvBuild += ((inp.R - cvt) * volume - inp.F) / Math.pow(1 + inp.wacc, t);
    }
    var pvLease = (inp.R - inp.p) * volume * annuity(inp.wacc, years);
    return { pvBuild: pvBuild, pvLease: pvLease, inHouseWins: pvBuild >= pvLease };
  }

  // ------------------------------------------------------------------
  // the trigger line (mirror decision.trigger_line)
  // ------------------------------------------------------------------
  function trigger(inp, volume) {
    volume = volume == null ? inp.volume : volume;
    var par = partnerMargin(inp.R, inp.p);
    var fl = flipVolume(inp.F, inp.p, inp.cv);
    var out = {
      flip: fl,
      pvBe: pvBreakEven(inp.F, inp.p, inp.cv, inp.decay, 5, inp.wacc),
      declineRate: declineRate(inp.R, inp.floor),
      partnerMargin: par,
      volume: volume
    };
    if (par < inp.floor) {
      out.rec = 'DECLINE';
      out.line = 'DECLINE at partner rate $' + inp.p.toFixed(2) +
        '/parcel: the 3PL margin $' + par.toFixed(2) + ' is below the $' +
        inp.floor.toFixed(2) + ' floor — lease is not offered at this price.';
    } else if (isFinite(fl) && volume >= fl) {
      out.rec = 'ENTER';
      out.line = 'ENTER in-house at ≥ ' + Math.round(fl).toLocaleString('en-US') +
        ' parcels/yr (you clear ' + Math.round(volume).toLocaleString('en-US') +
        '); below that, partner at $' + inp.p.toFixed(2) + '/parcel.';
    } else {
      out.rec = 'PARTNER';
      out.line = 'PARTNER at $' + inp.p.toFixed(2) + '/parcel up to the flip ' +
        (isFinite(fl) ? '(' + Math.round(fl).toLocaleString('en-US') + ' parcels/yr); build only above it.'
                      : '(the partner is cheaper at every volume); build never wins.');
    }
    return out;
  }

  // ------------------------------------------------------------------
  // the funnel (mirror sizing.py)
  // ------------------------------------------------------------------
  function funnel(inp) {
    var us = inp.usTotal * 1e9;
    var ecomm = us * inp.ecomm;
    var sam = ecomm * inp.metro;
    var capturable = sam * inp.capture;
    return {
      usParcels: us,
      ecommParcels: ecomm,
      sam: sam,
      capturable: capturable
    };
  }

  function headroom(inp, flip) {
    if (!isFinite(flip) || flip <= 0) { return null; }
    return funnel(inp).capturable / flip;
  }

  // CAC payback on each yardstick (mirror sizing.cac_payback)
  function cacPayback(inp) {
    var ih = inp.R - inp.cv;
    var par = inp.R - inp.p;
    return {
      inHouse: ih > 0 ? inp.cac / ih : Infinity,
      partner: (par >= inp.floor) ? inp.cac / par : Infinity
    };
  }

  // per-volume contribution table, year-1 costs (mirror contribution_table)
  function contributionTable(inp, volumes) {
    return volumes.map(function (v) {
      var ihCost = inHouseAllIn(inp.cv, inp.decay, inp.F, v, 1);
      var ihWins = (inp.p - inp.cv) > 0 && ihCost <= inp.p + 1e-12;
      return {
        v: v,
        ihCost: ihCost,
        ihMargin: inp.R - ihCost,
        parCost: inp.p,
        parMargin: inp.R - inp.p,
        ihWins: ihWins
      };
    });
  }

  // the (cost, rate) decision surface at the queried volume (mirror surface)
  function surface(inp, cvGrid, pGrid, volume) {
    volume = volume == null ? inp.volume : volume;
    var cells = [];
    for (var i = 0; i < cvGrid.length; i++) {
      for (var j = 0; j < pGrid.length; j++) {
        var c = { cv: cvGrid[i], p: pGrid[j] };
        var par = inp.R - c.p;
        var fl = flipVolume(inp.F, c.p, c.cv);
        var win = par < inp.floor ? 'decline'
               : (isFinite(fl) && volume >= fl) ? 'enter'
               : 'partner';
        cells.push({ cv: c.cv, p: c.p, flip: fl, win: win });
      }
    }
    return cells;
  }

  return {
    DEFAULTS: DEFAULTS,
    decayedCV: decayedCV,
    flipVolume: flipVolume,
    pvBreakEven: pvBreakEven,
    inHouseAllIn: inHouseAllIn,
    partnerMargin: partnerMargin,
    declineRate: declineRate,
    strategyPVs: strategyPVs,
    trigger: trigger,
    funnel: funnel,
    headroom: headroom,
    cacPayback: cacPayback,
    contributionTable: contributionTable,
    surface: surface
  };
}));
