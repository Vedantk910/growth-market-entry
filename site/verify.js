#!/usr/bin/env node
'use strict';
// Cross-language pin: the JS model in site/model.js must reproduce the
// Python model's baseline numbers (repo defaults from data/facts.py), to the
// bit. Run `node site/verify.js`; CI runs it after the Python test suite.
const assert = require('assert');
const M = require('./model.js');

const inp = Object.assign({}, M.DEFAULTS);
const t = M.trigger(inp, inp.volume);
const pv = M.strategyPVs(inp, inp.volume);
const fn = M.funnel(inp);

// Reference values: repo out/decision_numbers.json (baseline Facts),
// rounded to the nearest cent/parcel where the Python side rounds to 0.
function near(label, got, want, tol) {
  tol = tol == null ? 1e-9 : tol;
  const ok = (want === Infinity && got === Infinity) || Math.abs(got - want) <= tol;
  assert.ok(ok, label + ': got ' + got + ', want ' + want);
  console.log('ok  ' + label + ' = ' + got);
}

near('flip volume', t.flip, 416666.6666666666);
near('5-yr PV break-even', t.pvBe, 383511.07283260993);
near('decline rate', t.declineRate, 5.2, 1e-12);
assert.strictEqual(t.rec, 'PARTNER');
console.log('ok  trigger @wedge = ' + t.rec);

// strategy PVs: Python rounds to the dollar for the page, so compare on the
// unrounded JS values at a dollar tolerance.
near('pv_build @wedge', pv.pvBuild, -1276173.0, 1.0);
near('pv_lease @wedge', pv.pvLease, 199636.0, 1.0);

near('SAM (B/yr)', fn.sam / 1e9, 0.7494, 1e-12);
near('capturable', fn.capturable, 22482000.0, 1e-12);
near('headroom over flip', M.headroom(inp, t.flip), 53.95680000000001, 1e-9);
near('CAC payback in-house', M.cacPayback(inp).inHouse, 18.0 / 1.7, 1e-12);
near('CAC payback partner', M.cacPayback(inp).partner, 36.0, 1e-12);

// the contribution table flags: 100k/200k/300k partner, 500k+ build
const rows = M.contributionTable(inp, [50000, 100000, 200000, 300000, 500000, 800000, 1000000]);
assert.deepStrictEqual(
  rows.map(r => r.ihWins),
  [false, false, false, false, true, true, true]
);
console.log('ok  contribution table flags');

// invariant: halving the funnel leaves the flip bit-identical
const half = Object.assign({}, inp, { usTotal: inp.usTotal * 0.5 });
assert.strictEqual(M.trigger(half, half.volume).flip, t.flip);
console.log('ok  SAM invariance (halving usTotal does not move the flip)');

console.log('\nAll JS pins match the Python baseline.');
