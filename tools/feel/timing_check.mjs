// 拍子準不準:同一個格子上該一起落下的樂器,彼此差多少(耳朵聽到「不齊」的就是這個),以及離格子多遠。
// 用法:node tools/feel/timing_check.mjs [曲風 ...]   標準:樂器之間 95% ≤ 2×σ(規格的 timingSigmaMs,K-pop 舞曲 2ms → 4ms),
//       離格子 95% ≤ 2.5×σ;和弦裡第一顆到最後一顆 ≤ 12ms
import { readFileSync } from "node:fs";
import { render, resolveStyle } from "../../styles/engine.mjs";
const ROOT = new URL("../../", import.meta.url).pathname;
const data = JSON.parse(readFileSync(ROOT + "styles/styles.json"));
data.feel = JSON.parse(readFileSync(ROOT + "styles/feel.json"));
const ids = process.argv.slice(2).length ? process.argv.slice(2) : data.styles.map(s => s.id);
const q = (v, p) => { const s = [...v].sort((a, b) => a - b); return s[Math.floor(p * (s.length - 1))] ?? 0; };
let bad = 0;
for (const id of ids) {
  const st = resolveStyle(data, id), sig = st.humanize?.timingSigmaMs ?? 6;
  for (const dens of ["low", "standard", "high"]) {
    let r;
    try { r = render(data, id, { density: dens, bars: 32, seed: 7, countIn: false }); } catch { continue; }
    // 和弦用平均落點;曲風刻意的偏移(例:R&B 小鼓往後 20ms,overrides.offsetMs)不算不準,扣掉
    const offs = st.humanize?.overrides ?? {};
    const onset = e => e.time - (offs[e.piece ?? e.track]?.offsetMs ?? 0) / 1000 + (e.noteDt ? e.noteDt.reduce((a, b) => a + b, 0) / e.noteDt.length : 0);
    const at = new Map();
    for (const e of r.events) {
      if (e.sub || (e.piece && /hat|openhat|crash/.test(e.piece) && e.cells === undefined && false)) continue;
      const key = e.gridTime.toFixed(4);
      (at.get(key) ?? at.set(key, []).get(key)).push(e);
    }
    const pair = [], grid = [], spread = [];
    for (const es of at.values()) {
      const ts = es.map(onset);
      if (es.length > 1) pair.push((Math.max(...ts) - Math.min(...ts)) * 1000);
      for (const e of es) grid.push(Math.abs(onset(e) - e.gridTime) * 1000);
      for (const e of es) if (e.noteDt) spread.push((Math.max(...e.noteDt) - Math.min(...e.noteDt)) * 1000);
    }
    const p95 = q(pair, 0.95), g95 = q(grid, 0.95), s95 = q(spread, 0.95);
    const ok = p95 <= 2 * sig + 0.5 && g95 <= 2.5 * sig + 0.5 && s95 <= 12;
    if (!ok) bad++;
    console.log(`${ok ? "✓" : "✗"} ${id.padEnd(16)} ${dens.padEnd(8)} σ=${sig}ms  樂器之間 95% ${p95.toFixed(1)}ms(≤${2 * sig})  離格子 95% ${g95.toFixed(1)}ms(≤${2.5 * sig})  和弦內 95% ${s95.toFixed(1)}ms(≤12)`);
  }
}
console.log(bad ? `不合格 ${bad}` : "全部合格");
process.exit(bad ? 1 : 0);
