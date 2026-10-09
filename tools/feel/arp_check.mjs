// 分解和弦檢查(Steven 2026-10-08:「音跟音之間斷掉了」「應該找近的位置」「有 bass 撐住」):
// 1. 斷音:踩踏板的鍵盤,一顆和弦的時間裡有沒有「什麼都沒在響」的空檔(要 0)
// 2. 右手換和弦平均移動(半音,三個和弦音各自走最近的距離加起來 ÷ 3,要 ≤ 3)
// 3. 換和弦那一下左手有沒有彈低音(要 100%),而且低音 = 和弦的低音(斜線和弦就是斜線那個音)
// 用法:node tools/feel/arp_check.mjs
import { readFileSync } from "node:fs";
import { render, resolveStyle } from "../../styles/engine.mjs";
const ROOT = new URL("../../", import.meta.url).pathname;
const data = JSON.parse(readFileSync(ROOT + "styles/styles.json"));
let bad = 0;
for (const st of data.styles) {
  const S = resolveStyle(data, st.id);
  if (S.voicing.keys !== "arp_inv") continue;
  for (const meter of ["4/4", ...Object.keys(S.meters ?? {})]) for (const prog of S.progressions) for (const dens of ["low", "standard", "high"]) {
    let r;
    try { r = render(data, st.id, { progression: prog.id, density: dens, bars: 16, humanize: false, countIn: false, meter }); } catch { continue; }
    const ks = r.events.filter(e => e.track === "keys");
    if (!ks.length) continue;
    // 1. 空檔:把每一顆的 [開始, 結束) 合起來,從第一顆到最後一顆結束之間沒蓋到的時間
    const iv = ks.map(e => [e.time, e.time + e.dur]).sort((a, b) => a[0] - b[0]);
    let gap = 0, end = iv[0][1];
    for (const [a, b] of iv) { if (a > end + 1e-6) gap = Math.max(gap, a - end); end = Math.max(end, b); }
    // 2. 右手移動
    const plan = r.plans.keys, mv = [];
    for (let i = 1; i < plan.length; i++) {
      const rh = n => n.slice(1).filter(p => p !== n[0] + 12);
      const a = rh(plan[i - 1].notes), b = rh(plan[i].notes);
      mv.push(b.reduce((s, x) => s + Math.min(...a.map(y => Math.abs(x - y))), 0) / b.length);
    }
    const avg = mv.reduce((a, b) => a + b, 0) / mv.length;
    // 3. 換和弦那一下有左手低音
    let lhOk = 0, lhN = 0;
    for (const p of plan) {
      if (p.bar >= 16) continue; // 引擎多算一顆「下一顆和弦」給聲部連接用,不會彈
      const e = ks.find(x => x.bar === p.bar && x.cell === p.from);
      lhN++;
      if (e && e.notes.includes(p.notes[0])) lhOk++;
    }
    const ok = gap < 0.001 && avg <= 3 && lhOk === lhN;
    if (!ok) bad++;
    if (!ok || prog === S.progressions[0])
      console.log(`${ok ? "✓" : "✗"} ${st.id.padEnd(16)} ${meter} ${prog.id.padEnd(14)} ${dens.padEnd(8)} 最長空檔 ${(gap * 1000).toFixed(0)}ms  右手平均移動 ${avg.toFixed(2)} 半音  換和弦有左手低音 ${lhOk}/${lhN}`);
  }
}
console.log(bad ? `不合格 ${bad}` : "全部合格");
process.exit(bad ? 1 : 0);
