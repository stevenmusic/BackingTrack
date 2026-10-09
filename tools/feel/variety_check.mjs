// 彈法有多「複製貼上」:每個曲風、每件樂器,32 小節裡
//   整小節跟上一小節一模一樣(音高 + 節奏)的比例、節奏一樣的比例、出現過幾種不同的小節
// 真人參考(POP909 鋼琴,878 首):整個一樣 2.4%、節奏一樣 28.1%
// 用法:node tools/feel/variety_check.mjs [密度]
import { readFileSync } from "node:fs";
import { render, resolveStyle } from "../../styles/engine.mjs";
const ROOT = new URL("../../", import.meta.url).pathname;
const data = JSON.parse(readFileSync(ROOT + "styles/styles.json"));
data.feel = JSON.parse(readFileSync(ROOT + "styles/feel.json"));
const dens = process.argv[2] ?? "standard";
console.log(`密度 ${dens},32 小節;格式:整小節一樣% / 節奏一樣% / 不同的小節幾種`);
for (const st of data.styles) {
  const r = render(data, st.id, { density: dens, bars: 32, humanize: false, countIn: false, seed: 7, progression: resolveStyle(data, st.id).progressions[0].id });
  const tracks = [...new Set(r.events.map(e => e.track === "drums" ? "drums" : e.track))];
  const row = [];
  for (const t of tracks) {
    const bars = Array.from({ length: 32 }, () => ({ rh: new Set(), full: [] }));
    for (const e of r.events) {
      if ((e.track === "drums" ? "drums" : e.track) !== t || e.bar < 0 || e.bar >= 32) continue;
      const pos = e.cell * 2 + (e.sub ?? 0);
      bars[e.bar].rh.add(pos);
      bars[e.bar].full.push(pos + ":" + (e.piece ?? "") + ":" + (e.notes ?? []).map(n => n % 12).join(","));
    }
    const sig = bars.map(b => [...b.full].sort().join("|")), rsig = bars.map(b => [...b.rh].sort((a, b) => a - b).join(","));
    let same = 0, rsame = 0;
    for (let i = 1; i < 32; i++) { same += sig[i] === sig[i - 1]; rsame += rsig[i] === rsig[i - 1]; }
    row.push(`${t} ${Math.round(same / 31 * 100)}/${Math.round(rsame / 31 * 100)}/${new Set(rsig).size}`);
  }
  console.log(st.id.padEnd(16), row.join("   "));
}
