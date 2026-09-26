/* 只留一條 bus(其他 gain 0),量「每一層單獨多大聲」。bus 名由 REALISM_SOLO 給(render.mjs 設 window.__soloBus)。
   REALISM_PROBE=tools/realism/probe_solo.js REALISM_SOLO=combBus node tools/realism/render.mjs <cases> */
(() => { const keep = window.__soloBus;
  const all = ['drumBus', 'bassBus', 'combBus', 'keysBus', 'padBus', 'percBus', 'reverbBus', 'roomBus', 'echoBus'];
  setInterval(() => { for (const n of all) { const b = window.eval('typeof ' + n + ' !== "undefined" ? ' + n + ' : null'); if (b && n !== keep) b.gain.value = 0; } }, 20);
  window.__probeReport = () => keep; })();
