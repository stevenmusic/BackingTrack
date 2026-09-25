/* 鼓的探針:open hat 打了幾下、在哪一格、有沒有被掐;大鼓與貝斯同一格時差幾毫秒;限幅器壓了多少 */
(() => {
  const P = window.__P = { ohat: [], chokes: 0, kick: {}, bass: {}, gate: null };
  const oPlay = window.playDrum, oBass = window.playBassNote, oChoke = window.chokeOhat;
  const beatOf = t => anchorBeat + (t - anchorTime) / spb;
  window.chokeOhat = function (w) { if (lastOhat && w > lastOhat.at + 0.02) P.chokes++; return oChoke.apply(this, arguments); };
  // humanTime 在函式裡面才加,所以要從它的回傳值算實際落點
  const oHT = window.humanTime;
  window.humanTime = function (name, when, salt) {
    const d = oHT.apply(this, arguments);
    const slot = Math.round(beatOf(when) * 4);
    if (name === 'kick') P.kick[slot] = (when + d) * 1000;
    if (name === 'bass') P.bass[slot] = (when + d) * 1000;
    return d;
  };
  window.playDrum = function (piece, when) {
    if (piece === 'ohat') P.ohat.push(+((beatOf(when) % 4)).toFixed(2));
    return oPlay.apply(this, arguments);
  };
  window.__probeReport = () => {
    const diffs = Object.keys(P.kick).filter(k => k in P.bass).map(k => P.bass[k] - P.kick[k]);
    const pos = {}; P.ohat.forEach(b => pos[b] = (pos[b] || 0) + 1);
    const lr = (typeof limRed !== 'undefined' && limRed.length) ? limRed.slice().sort((a, b) => a - b) : [];
    return { ohat次數: P.ohat.length, ohat位置: pos, 掐音次數: P.chokes, 大鼓貝斯同格: diffs.length,
             貝斯減大鼓ms: diffs.length ? { 平均: +(diffs.reduce((a, b) => a + b, 0) / diffs.length).toFixed(2), 最大絕對值: +Math.max(...diffs.map(Math.abs)).toFixed(2) } : null,
             gate送: gateSend ? gateSend.gain.value : null, open載到: drumReady('ohat'),
             限幅器壓縮dB中位數: lr.length ? +lr[Math.floor(lr.length / 2)].toFixed(2) : null };
  };
})();
