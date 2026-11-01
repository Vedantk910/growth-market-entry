(function () {
  'use strict';
  var M = window.MEModel;
  var $ = function (id) { return document.getElementById(id); };

  // slider input -> state key, with its formatter
  var SLIDERS = [
    ['inV', 'volume', function (v) { return Math.round(v).toLocaleString('en-US'); }, 'oV'],
    ['inP', 'p', function (v) { return '$' + (+v).toFixed(2); }, 'oP'],
    ['inCV', 'cv', function (v) { return '$' + (+v).toFixed(2); }, 'oCV'],
    ['inF', 'F', function (v) { return '$' + (v / 1000).toFixed(0) + 'k/yr'; }, 'oF'],
    ['inR', 'R', function (v) { return '$' + (+v).toFixed(2); }, 'oR'],
    ['inFloor', 'floor', function (v) { return '$' + (+v).toFixed(2); }, 'oFloor'],
    ['inWacc', 'wacc', function (v) { return (+v).toFixed(1) + '%'; }, 'oWacc'],
    ['inDecay', 'decay', function (v) { return (+v).toFixed(2) + '%'; }, 'oDecay'],
    ['inUs', 'usTotal', function (v) { return (+v).toFixed(1) + 'B'; }, 'oUs'],
    ['inEcomm', 'ecomm', function (v) { return (+v) + '%'; }, 'oEcomm'],
    ['inMetro', 'metro', function (v) { return (+v) + '%'; }, 'oMetro'],
    ['inCap', 'capture', function (v) { return (+v) + '%'; }, 'oCap']
  ];
  var state = Object.assign({}, M.DEFAULTS);
  // percentages stored as fractions in the model; sliders show whole %
  function readState() {
    state = Object.assign({}, M.DEFAULTS);
    state.volume = +$('inV').value;
    state.p = +$('inP').value;
    state.cv = +$('inCV').value;
    state.F = +$('inF').value;
    state.R = +$('inR').value;
    state.floor = +$('inFloor').value;
    state.wacc = +$('inWacc').value / 100;
    state.decay = +$('inDecay').value / 100;
    state.usTotal = +$('inUs').value;
    state.ecomm = +$('inEcomm').value / 100;
    state.metro = +$('inMetro').value / 100;
    state.capture = +$('inCap').value / 100;
  }
  function pushState() {
    $('inV').value = state.volume; $('inP').value = state.p; $('inCV').value = state.cv;
    $('inF').value = state.F; $('inR').value = state.R; $('inFloor').value = state.floor;
    $('inWacc').value = state.wacc * 100; $('inDecay').value = state.decay * 100;
    $('inUs').value = state.usTotal; $('inEcomm').value = state.ecomm * 100;
    $('inMetro').value = state.metro * 100; $('inCap').value = state.capture * 100;
  }

  function fmtMoney(x) {
    if (!isFinite(x)) return '—';
    return '$' + (Math.abs(x) >= 1000 ? Math.round(x).toLocaleString('en-US') : x.toFixed(2));
  }
  function fmtInt(x) {
    if (!isFinite(x)) return '∞';
    return Math.round(x).toLocaleString('en-US');
  }

  // ------------------------------------------------------------------
  // render: one pass recomputes everything from `state`
  // ------------------------------------------------------------------
  function render() {
    var tr = M.trigger(state, state.volume);
    var pv = M.strategyPVs(state, state.volume);
    var ih = M.inHouseAllIn(state.cv, state.decay, state.F, state.volume, 1);

    // outputs next to sliders
    SLIDERS.forEach(function (s) {
      var el = $(s[0]);
      if (el) { $(s[3]).textContent = s[2](el.value); }
    });

    // verdict
    var rec = tr.rec;
    $('rec').textContent = rec;
    $('rec').className = 'badge ' + rec.toLowerCase();
    $('recLine').textContent = tr.line;
    $('pvBuild').textContent = fmtMoney(pv.pvBuild);
    $('pvLease').textContent = fmtMoney(pv.pvLease);

    // derivation
    $('dIH').textContent = fmtMoney(ih);
    $('dPar').textContent = fmtMoney(state.p);
    $('dFlip').textContent = fmtInt(tr.flip);
    $('dPv').textContent = fmtInt(tr.pvBe);
    $('dParMargin').textContent = '$' + M.partnerMargin(state.R, state.p).toFixed(2);
    $('dDecline').textContent = tr.declineRate.toFixed(2);
    $('dVol').textContent = fmtInt(state.volume);
    $('dRec').textContent = rec;

    // volume table (in-house vs partner at the committee's grid)
    var vols = [50000, 100000, 200000, 300000, 500000, 800000, 1000000];
    var rows = M.contributionTable(state, vols);
    var tb = $('volTable').querySelector('tbody');
    tb.innerHTML = rows.map(function (r) {
      var cls = r.v === state.volume ? ' class="you"' : '';
      return '<tr' + cls + '>' +
        '<td>' + fmtInt(r.v) + (r.v === state.volume ? ' <span class="hint">(you)</span>' : '') + '</td>' +
        '<td>$' + r.ihCost.toFixed(2) + '</td>' +
        '<td>$' + r.parCost.toFixed(2) + '</td>' +
        '<td>' + (r.ihMargin >= 0 ? '+' : '') + '$' + r.ihMargin.toFixed(2) + '</td>' +
        '<td>' + (r.parMargin >= 0 ? '+' : '') + '$' + r.parMargin.toFixed(2) + '</td>' +
        '<td>' + (r.ihWins ? '<span class="enter">BUILD</span>' : '<span class="partner">PARTNER</span>') + '</td>' +
        '</tr>';
    }).join('');

    // funnel
    var fn = M.funnel(state);
    var hr = M.headroom(state, tr.flip);
    var ca = M.cacPayback(state);
    $('funnel').innerHTML =
      '<div class="fstep"><b>US parcels/yr</b><span>' + (fn.usParcels / 1e9).toFixed(1) +
      'B <em>EST</em></span></div>' +
      '<div class="fstep"><b>× e-comm last-mile slice</b><span>' +
      (fn.ecommParcels / 1e9).toFixed(1) + 'B <em>EST</em></span></div>' +
      '<div class="fstep"><b>× one-metro serviceable</b><span>' +
      (fn.sam / 1e9).toFixed(2) + 'B <em>SAM · EST</em></span></div>' +
      '<div class="fstep"><b>× capture rate</b><span>' +
      fmtInt(fn.capturable) + ' capturable <em>EST</em></span></div>' +
      '<div class="fstep anchor"><b>Filed anchor</b><span>' +
      state.uspsAnchor.toFixed(1) + 'B USPS commercial parcels <em>CONFIRMED</em></span></div>';
    $('headroom').textContent = (hr == null || !isFinite(hr)) ? '∞' : hr.toFixed(0);
    $('cacIh').textContent = fmtInt(ca.inHouse);
    $('cacPar').textContent = fmtInt(ca.partner);

    // the decision surface: in-house cv x partner rate, at the queried volume
    var cvGrid = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5];
    var pGrid = [3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0];
    var cells = M.surface(state, cvGrid, pGrid, state.volume);
    var el = $('surface');
    el.innerHTML = '<div class="srows">' +
      // partner-rate axis (one header row)
      '<div class="srow paxis"><span class="corner"></span>' +
      pGrid.map(function (p) { return '<span>$' + p.toFixed(1) + '</span>'; }).join('') + '</div>' +
      // one row per in-house cost value, cells first
      cvGrid.map(function (c) {
        return '<div class="srow"><span class="rlabel">cv $' + c.toFixed(1) + '</span>' +
          pGrid.map(function (p) {
            var cell = null;
            for (var i = 0; i < cells.length; i++) {
              if (cells[i].cv === c && cells[i].p === p) { cell = cells[i]; break; }
            }
            return '<div class="scell ' + cell.win + '" data-cv="' + c + '" data-p="' + p + '" ' +
              'title="cv $' + c.toFixed(1) + ' · p $' + p.toFixed(1) + ' → ' +
              (isFinite(cell.flip) ? 'flip ' + fmtInt(cell.flip) + '/yr' : 'in-house never cheaper') +
              ' (' + cell.win + ')"></div>';
          }).join('') + '</div>';
      }).join('') + '</div>' +
      '<div class="skey">' +
      '<span><i class="enter"></i>build</span>' +
      '<span><i class="partner"></i>partner</span>' +
      '<span><i class="decline"></i>decline</span></div>';
    var youAt = (function () {
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].cv === state.cv && cells[i].p === state.p) { return cells[i].win; }
      }
      return null;
    })();
    $('surfaceNote').textContent = youAt
      ? 'You are at the ' + youAt + ' cell · in-house cost $' + state.cv.toFixed(2) +
        ' × partner rate $' + state.p.toFixed(2)
      : 'Your in-house cost $' + state.cv.toFixed(2) + ' / partner rate $' + state.p.toFixed(2) +
        ' falls off the grid · the recommendation still follows the trigger line above. Click any cell to set its cv and p.';

    el.querySelectorAll('.scell').forEach(function (d) {
      d.addEventListener('click', function () {
        $('inCV').value = d.getAttribute('data-cv');
        $('inP').value = d.getAttribute('data-p');
        readState(); render();
      });
    });
  }

  // ------------------------------------------------------------------
  SLIDERS.forEach(function (s) {
    $(s[0]).addEventListener('input', function () { readState(); render(); });
  });
  $('btnBaseline').addEventListener('click', function () {
    state = Object.assign({}, M.DEFAULTS); pushState(); render();
  });
  $('btnRandom').addEventListener('click', function () {
    function between(id, lo, hi) { return lo + Math.random() * (hi - lo); }
    $('inV').value = Math.round(between('inV', 50000, 800000) / 10000) * 10000;
    $('inP').value = between('inP', 4.0, 6.0).toFixed(2);
    $('inCV').value = between('inCV', 2.8, 4.6).toFixed(2);
    $('inF').value = Math.round(between('inF', 200000, 1200000) / 25000) * 25000;
    $('inR').value = between('inR', 5.0, 7.0).toFixed(2);
    $('inFloor').value = between('inFloor', 0.2, 0.8).toFixed(2);
    readState(); render();
  });

  pushState(); render();
})();
