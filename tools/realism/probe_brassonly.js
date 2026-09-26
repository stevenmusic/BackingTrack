/* 只聽銅管:吉他 `pluck` 換成空的、其他 bus 全關,combBus 降到 0.062(原本 0.62,−20dB)——
   原樣錄的話銅管每一下都頂到總線的限幅器(−1.4dBFS),比不出大小。也記下吹了幾聲、幾聲是取樣
   REALISM_PROBE=tools/realism/probe_brassonly.js REALISM_SECS=20 REALISM_OUT=/tmp/bcal node tools/realism/render.mjs tools/realism/cases_bcal.json
   /tmp/abx/bin/python tools/realism/hits.py /tmp/bcal */
(() => { window.pluck = function(){}; const n = { b: 0, s: 0 }; const pb = window.playBrass;
  window.playBrass = function(ms){ n.b += ms.length; return pb.apply(this, arguments); };
  const ps = window.playBrassSmp; window.playBrassSmp = function(ms){ const r = ps.apply(this, arguments); n.s += ms.length - r.length; return r; };
  const all = ['drumBus', 'bassBus', 'keysBus', 'padBus', 'percBus', 'reverbBus', 'roomBus', 'echoBus'];
  setInterval(() => { for (const k of all) { const b = window.eval('typeof ' + k + ' !== "undefined" ? ' + k + ' : null'); if (b) b.gain.value = 0; } }, 20);
  setInterval(() => { if (typeof combBus !== 'undefined' && combBus) combBus.gain.value = 0.062; }, 20);
  window.__probeReport = () => n; })();
