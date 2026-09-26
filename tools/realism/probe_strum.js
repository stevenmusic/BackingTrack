/* 記下每一下吉他排在第幾拍(`strum` / `pluck` 的 when 換成拍數),錄完由 render.mjs 印出來。
   REALISM_PROBE=tools/realism/probe_strum.js node tools/realism/render.mjs <cases> */
(() => { const log = []; const os = window.strum, op = window.pluck;
  const beat = w => +(anchorBeat + (w - anchorTime) / spb).toFixed(3);
  window.strum = function(notes, when){ log.push(['strum', beat(when)]); return os.apply(this, arguments); };
  window.pluck = function(m, when){ log.push(['pluck', beat(when)]); return op.apply(this, arguments); };
  window.__probeReport = () => log.slice(0, 60); })();
