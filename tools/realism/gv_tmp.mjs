import { chromium } from 'playwright';
import fs from 'fs';
const b = await chromium.launch(); const pg = await b.newPage();
pg.on('pageerror', e => console.log('pageerror', e.message.slice(0, 200)));
await pg.route('http://gv.local/ck/**', r => r.fulfill({ status: 200, body: fs.readFileSync('/tmp/gv/ck/' + r.request().url().split('/ck/')[1]) }));
await pg.route('http://gv.local/', r => r.fulfill({ status: 200, contentType: 'text/html', body: '<html><body></body></html>' }));
await pg.goto('http://gv.local/');
await pg.addScriptTag({ content: fs.readFileSync('/tmp/gv/node_modules/@magenta/music/dist/magentamusic.js', 'utf8') });
const res = await pg.evaluate(async () => {
  const qpm = 110, spq = 4, notes = [];
  for (let bar = 0; bar < 2; bar++) for (let s = 0; s < 16; s++) {
    const q = bar * 16 + s, add = p => notes.push({ pitch: p, quantizedStartStep: q, quantizedEndStep: q + 1, isDrum: true, velocity: 80 });
    add(42); if ([0, 7, 10].includes(s)) add(36); if ([4, 12].includes(s)) add(38);
  }
  const seq = { notes, quantizationInfo: { stepsPerQuarter: spq }, totalQuantizedSteps: 32, tempos: [{ time: 0, qpm }] };
  const m = new mm.MusicVAE('http://gv.local/ck'); await m.initialize();
  const step = 60 / qpm / spq, out = [];
  for (let run = 0; run < 3; run++) {
    const t0 = performance.now();
    const z = await m.encode([seq]); const r = (await m.decode(z, 0.5 + run * 0.25, undefined, spq, qpm))[0];
    const ms = performance.now() - t0;
    const by = {}; for (const n of r.notes) { const g = Math.round(n.startTime / step); (by[n.pitch] = by[n.pitch] || []).push([g % 16, Math.round((n.startTime - g * step) * 1000), n.velocity]); }
    out.push({ temp: 0.5 + run * 0.25, n: r.notes.length, ms: Math.round(ms), by });
  }
  return out; });
for (const r of res) { console.log('temperature', r.temp, 'notes', r.n, '算一次', r.ms, 'ms');
  for (const p of Object.keys(r.by)) console.log('  ', p, r.by[p].slice(0, 16).map(x => `${x[0]}:${x[1]}/${x[2]}`).join(' ')); }
await b.close();
