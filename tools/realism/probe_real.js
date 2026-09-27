/* 演奏真實度的三件有沒有真的在用:Rhodes 力度層(layerBufs 載到幾個、playNote 用到幾次)、
   hi-hat 互掐(lastSMHat 有沒有在換)、貝斯放弦聲(bassRelBufs 載到幾個音)。
   REALISM_PROBE=tools/realism/probe_real.js node tools/realism/render.mjs <cases> */
(() => { const n = { notes: 0, hats: 0 }, lv = [0, 0, 0, 0]; const pn = window.playNote;
  // 力度分級照 playNote 的 keysTrueVel 算法(peak ÷ 0.42,不含音量修正):≤72 / ≤95 / ≤111 / >111(× 127)
  window.playNote = function(m, w, d, peak){ n.notes++; const v = Math.min(1, peak / 0.42) * 127;
    lv[v <= 72 ? 0 : v <= 95 ? 1 : v <= 111 ? 2 : 3]++; return pn.apply(this, arguments); };
  window.__probeReport = () => ({ notes: n.notes, levels_48_73_96_112: lv, layerFiles: layerBufs.size,
    relNotes: [...bassRelBufs.values()].filter(l => l.length).length, lastHat: !!lastSMHat }); })();
