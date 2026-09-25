/* 新進行加進段落庫之前先驗:判得回 C 大調、解析得了。node tools/realism/keytest.mjs "<進行>" ... */
import { chromium } from 'playwright';
const T = process.argv.slice(2);
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const pg = await b.newPage(); await pg.route(/^https:/, r => r.abort());
await pg.goto('file:///home/user/BackingTrack/index.html');
for (const t of T) {
  const r = await pg.evaluate(t => { const p = parseProgression(t); const k = keyOf(p.bars); return { ok: p.bars.every(x => x.ok), n: p.bars.length, k: JSON.stringify(k) }; }, t);
  console.log(t.padEnd(46), r.ok ? '' : '解析失敗', r.n + ' 小節', 'key=' + r.k);
}
await b.close();
