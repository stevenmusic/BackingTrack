/* 排程一跳多久(`scheduleBeat` 每呼叫一次的毫秒數)與「來不及」次數(排到的時間已經過了)。
   REALISM_PROBE=tools/realism/probe_perf.js REALISM_CPU=6 node tools/realism/render.mjs <cases>
   標準(CLAUDE.md):CPU 降速 6× 跑三四次看中位數,「來不及 0 次」 */
(() => { const ms = []; let late = 0; const orig = window.scheduleBeat;
  window.scheduleBeat = function(b, when){
    if (ctx && when < ctx.currentTime) late++;
    const t0 = performance.now(); const r = orig.apply(this, arguments); ms.push(performance.now() - t0); return r; };
  window.__probeReport = () => { const s = ms.slice(8).sort((a, b) => a - b);
    return { beats: s.length, maxMs: +(s[s.length - 1] || 0).toFixed(1), p95: +(s[Math.floor(s.length * 0.95)] || 0).toFixed(1), late }; }; })();
