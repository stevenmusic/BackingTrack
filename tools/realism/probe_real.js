/* 演奏真實度的三件有沒有真的在用:Rhodes 力度層(layerBufs 載到幾個、playNote 用到幾次)、
   hi-hat 互掐(lastSMHat 有沒有在換)、貝斯放弦聲(bassRelBufs 載到幾個音)。
   REALISM_PROBE=tools/realism/probe_real.js node tools/realism/render.mjs <cases> */
(() => { const n = { notes: 0, hats: 0 }; const pn = window.playNote;
  window.playNote = function(){ n.notes++; return pn.apply(this, arguments); };
  window.__probeReport = () => ({ notes: n.notes, layerFiles: layerBufs.size,
    relNotes: [...bassRelBufs.values()].filter(l => l.length).length, lastHat: !!lastSMHat }); })();
