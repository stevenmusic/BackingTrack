/* 一顆拆兩顆(和弦變化的 split)會不會把律動弄亂:
   同一段進行,把「有拆的小節」與「同一個位置沒拆的小節」逐層比每小節的下數與落點。
   node tools/realism/rhythm_split.mjs <曲風> "<進行>" [秒數] */
import { chromium } from 'playwright';
import http from 'http'; import fs from 'fs';
const [feel, prog, secsArg] = process.argv.slice(2);
const SECS = +secsArg || 90;
const sv = http.createServer((q, s) => { const f = decodeURIComponent(q.url.split('?')[0]); if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); } s.writeHead(200); s.end(fs.readFileSync(f)); });
await new Promise(ok => sv.listen(0, ok));
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--autoplay-policy=no-user-gesture-required'] });
const pg = await b.newPage();
await pg.route(/^https:/, r => r.abort());
await pg.goto(`http://127.0.0.1:${sv.address().port}/home/user/BackingTrack/index.html`);
await pg.fill('#chordInput', prog); await pg.dispatchEvent('#chordInput', 'input');
await pg.click(`[data-feel="${feel}"]`); await pg.click('[data-style="comp"]');
await pg.evaluate(() => {
  window.__R = { notes: [], bars: {} };
  const tb = t => anchorBeat + (t - anchorTime) / spb;
  const rec = (inst, t) => __R.notes.push([inst, tb(t)]);
  const wrap = (name, inst) => { const o = window[name]; window[name] = function () { try { rec(inst, arguments[1]); } catch (e) {} return o.apply(this, arguments); }; };
  wrap('playNote', 'keys'); wrap('playBassNote', 'bass'); wrap('pluck', 'gtr');
  const od = window.playDrum; window.playDrum = function (p, t) { try { rec('drum:' + p, t); } catch (e) {} return od.apply(this, arguments); };
  const ob = window.scheduleBeat;
  window.scheduleBeat = function (i) {
    const r = ob.apply(this, arguments);
    try { const beats = beatsInBar(), mb = i - countInBeats; if (mb >= 0) {
      const bar = Math.floor(mb / beats), pos = bar % voicings.length;
      if (!__R.bars[bar]) __R.bars[bar] = { pos, split: barsNow()[pos].chords.some(c => c.added), names: barsNow()[pos].chords.map(c => c.text).join(' ') };
    } } catch (e) {}
    return r;
  };
});
await pg.click('#playBtn');
await pg.waitForFunction(s => typeof playing !== 'undefined' && playing && currentBeat() > 8 + s / spb, SECS, { timeout: 600000, polling: 500 });
const R = await pg.evaluate(() => Object.assign(__R, { beats: beatsInBar(), ci: countInBeats, div: divNow() }));
await b.close(); sv.close();
// 同一下(10ms 以內)的音算一下
const per = {};
for (const [inst, beat] of R.notes) {
  const mb = beat - R.ci; if (mb < 0) continue;
  const bar = Math.floor(mb / R.beats), info = R.bars[bar]; if (!info) continue;
  const key = info.pos + '|' + (info.split ? 'S' : 'N');
  const g = inst.startsWith('drum:') ? 'drums' : inst;
  const slot = Math.round((mb - bar * R.beats) * R.div * 2);
  ((per[key] ||= {})[g] ||= { bars: new Set(), hits: new Set() });
  per[key][g].bars.add(bar); per[key][g].hits.add(bar + ':' + slot);
}
const out = {};
for (const [key, L] of Object.entries(per)) for (const [g, v] of Object.entries(L)) {
  const nb = new Set(Object.entries(R.bars).filter(([k, x]) => x.pos + '|' + (x.split ? 'S' : 'N') === key).map(([k]) => k)).size;
  (out[key] ||= {})[g] = +(v.hits.size / nb).toFixed(2);
}
const names = {}; for (const x of Object.values(R.bars)) if (x.split) names[x.pos] = (names[x.pos] || new Set()).add(x.names);
for (const k of Object.keys(out).sort()) console.log(k.padEnd(5), JSON.stringify(out[k]), k.endsWith('S') ? [...names[k.split('|')[0]]].join(' / ') : '');
