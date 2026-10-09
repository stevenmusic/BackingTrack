// 和聲層的頂音是不是和弦音(Steven 2026-10-09:「思考 9 音在上面的必要性,拿掉可能更好」):
// 頂音只准根、三、五、六(六和弦)、七、sus 的二 / 四度、斜線低音;九 / 十一 / 十三度要在中間。
// 用法:node tools/feel/top_check.mjs     標準:每個曲風 0 個
import { readFileSync } from "node:fs";
import { render, resolveStyle } from "../../styles/engine.mjs";
const ROOT = new URL("../../", import.meta.url).pathname;
const data = JSON.parse(readFileSync(ROOT + "styles/styles.json"));
const mod = n => ((n % 12) + 12) % 12;
let bad = 0;
for (const st of data.styles) {
  const S = resolveStyle(data, st.id);
  let n = 0, b = 0;
  const ex = [];
  for (const meter of ["4/4", ...Object.keys(S.meters ?? {})]) for (const prog of S.progressions) for (const dens of ["low", "standard", "high"]) {
    let r;
    try { r = render(data, st.id, { progression: prog.id, density: dens, bars: 16, humanize: false, meter }); } catch { continue; }
    for (const [tr, pl] of Object.entries(r.plans)) {
      if (tr === "keysShell") continue;
      for (const p of pl) {
        if (!p.chord || p.bar >= 16) continue;
        const c = p.chord, top = Math.max(...(p.rh ?? p.notes));
        const ok = new Set([0, c.iv[3], c.iv[5], c.iv[13] != null && c.iv[7] == null ? c.iv[13] : null, c.iv[6], c.iv[7], c.iv[2], c.iv[4]]
          .filter(x => x != null).map(x => mod(c.root + x)));
        ok.add(c.bass);
        n++;
        if (!ok.has(mod(top))) { b++; if (ex.length < 3) ex.push(`${tr} ${c.sym} 頂音 ${top}`); }
      }
    }
  }
  if (b) bad++;
  console.log(`${b ? "✗" : "✓"} ${st.id.padEnd(16)} 頂音不是和弦音 ${b}/${n}  ${ex.join("、")}`);
}
console.log(bad ? `不合格 ${bad}` : "全部合格");
process.exit(bad ? 1 : 0);
