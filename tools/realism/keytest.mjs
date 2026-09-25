import { chromium } from 'playwright';
const T = ["Cmaj7 - Am7 - Dm7 - F/G","Am7 - Em7 - Fmaj7 - G7sus4","Cmaj7 - Em7 - Fmaj7 - F/G"];
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const pg = await b.newPage(); await pg.route(/^https:/, r => r.abort());
await pg.goto('file:///home/user/BackingTrack/index.html');
for (const t of T) {
  const r = await pg.evaluate(t => { const p = parseProgression(t); const k = keyOf(p.bars); return { ok: p.bars.every(x => x.ok), k: JSON.stringify(k) }; }, t);
  console.log(t.padEnd(38), r.ok ? '' : '解析失敗', r.k);
}
await b.close();
