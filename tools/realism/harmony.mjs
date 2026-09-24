/* 和聲檢查:每一件樂器彈的每一顆音,對照「那一刻真的在響的和弦」(含和弦變化換過的那一顆)。
   node tools/realism/harmony.mjs <曲風> "<和弦進行>" [秒數] [style]
   分類:和弦音 / 可用的延伸音 / 經過音(短、弱拍) / **衝突**(長或落在強拍的非和弦音)/ 跨和弦(延音撐到下一顆和弦卻不是它的音) */
import { chromium } from 'playwright';
import http from 'http'; import fs from 'fs';
const [feel, prog, secsArg, style] = process.argv.slice(2);
const SECS = +secsArg || 30;
const sv = http.createServer((q, s) => { const f = decodeURIComponent(q.url.split('?')[0]); if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); } s.writeHead(200, { 'content-type': f.endsWith('.html') ? 'text/html' : 'application/octet-stream' }); s.end(fs.readFileSync(f)); });
await new Promise(ok => sv.listen(0, ok));
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--autoplay-policy=no-user-gesture-required'] });
const pg = await b.newPage();
await pg.route(/^https:/, r => r.abort());                       // 取樣不用載:只記「彈了哪些音」
await pg.goto(`http://127.0.0.1:${sv.address().port}/home/user/BackingTrack/index.html`);
await pg.fill('#chordInput', prog); await pg.dispatchEvent('#chordInput', 'input');
await pg.click(`[data-feel="${feel}"]`); await pg.click(`[data-style="${style || 'comp'}"]`);
await pg.evaluate(() => {
  window.__H = { notes: [], chords: {} };
  const tb = t => anchorBeat + (t - anchorTime) / spb;              // 時間 → 拍
  const rec = (inst, m, t, d) => { if (typeof m === 'number' && isFinite(m)) __H.notes.push([inst, m, tb(t), d / spb]); };
  const wrap = (name, fn) => { const o = window[name]; window[name] = function () { try { fn.apply(null, arguments); } catch (e) {} return o.apply(this, arguments); }; };
  wrap('playNote', (m, t, d) => rec('keys', m, t, d));
  wrap('playBassNote', (m, t, d) => rec('bass', m, t, d));
  wrap('pluck', (m, t, g, tone, mute) => rec('gtr', m, t, mute > 0 ? mute : 0.5 * spb));
  wrap('playKeysChord', (ms, t, d, g, kind) => (ms || []).forEach(m => rec(kind === 'low' ? 'padlow' : 'pad', m, t, d)));
  wrap('playBrass', (ms, t, d) => (ms || []).forEach(m => rec('brass', m, t, d)));
  wrap('synthKeyNote', (m, t, d) => rec('synth', m, t, d));
  const ob = window.scheduleBeat;
  window.scheduleBeat = function (i, when) {
    const r = ob.apply(this, arguments);
    try {
      const beats = beatsInBar(), mb = i - countInBeats; if (mb < 0) return r;
      const bar = Math.floor(mb / beats) % voicings.length, bsb = countInBeats + Math.floor(mb / beats) * beats;
      if (!__H.chords[bsb]) {
        const div = divNow();
        __H.chords[bsb] = voicings[bar].map(sp => ({ from: bsb + sp.from / div, to: bsb + sp.to / div,
          pcs: [...new Set(sp.chord.intervals.map(x => (sp.chord.rootPc + x + transposeOn) % 12))],
          root: (sp.chord.rootPc + transposeOn) % 12, bass: (sp.chord.bassPc + transposeOn) % 12,
          iv: sp.chord.intervals.map(x => x % 12), name: sp.chord.text || sp.chord.name || '' }));
      }
    } catch (e) {}
    return r;
  };
});
await pg.click('#playBtn');
await pg.waitForFunction(s => typeof playing !== 'undefined' && playing && currentBeat() > 8 + s / spb, SECS, { timeout: 300000, polling: 500 });
const H = await pg.evaluate(() => __H);
await b.close(); sv.close();
const chords = Object.values(H.chords).flat().sort((a, b) => a.from - b.from);
const at = beat => chords.find(c => beat >= c.from - 1e-6 && beat < c.to - 1e-6);
/* 可用的延伸音(相對根音):大三/大七可以 9、#11、13;小三可以 9、11(13 看情況,當可用);
   屬七全部可以(9、b9、#9、#11、b13、13);減/半減 9、11、b13 */
function tensions(c){
  const iv = new Set(c.iv), M3 = iv.has(4), m3 = iv.has(3), b7 = iv.has(10), M7 = iv.has(11), b5 = iv.has(6) && !iv.has(7);
  if (M3 && b7) return [1, 2, 3, 6, 8, 9];
  if (M3) return [2, 6, 9];
  if (m3 && b5) return [2, 5, 8];
  if (m3) return [2, 5, 9];
  return [2, 5, 9];
}
const stats = {}; const bad = [];
for (const [inst, m, beat, dur] of H.notes) {
  const c = at(beat + 0.01); if (!c) continue;
  const pc = ((m % 12) + 12) % 12, rel = ((pc - c.root) % 12 + 12) % 12;
  const S = stats[inst] || (stats[inst] = { n: 0, chord: 0, tension: 0, passing: 0, clash: 0, cross: 0 });
  S.n++;
  let kind;
  if (c.pcs.includes(pc) || pc === c.bass) kind = 'chord';
  else if (tensions(c).includes(rel) && inst !== 'bass') kind = 'tension';
  // 貝斯的藍調 boogie 六度(C7 上的 A)是那個曲風的本家寫法
  else if (inst === 'bass' && rel === 9 && c.iv.includes(10) && c.iv.includes(4)) kind = 'tension';
  // 接近音:這顆和弦的最後一拍裡、離下一顆和弦的根音(或低音)半音或全音——走動低音與過門的正常寫法
  else if ((() => { const nx = chords.find(x => x.from >= c.to - 1e-6); if (!nx) return false;
      if (nx.from - beat > 1.05) return false;
      return [nx.root, nx.bass].some(r => { const d = Math.min((pc - r + 12) % 12, (r - pc + 12) % 12); return d === 1 || d === 2; }); })()) kind = 'passing';
  else {
    const frac = beat - Math.floor(beat);
    const weak = Math.abs(frac) > 0.05 && Math.abs(frac - 1) > 0.05;          // 不在拍點上
    kind = (dur <= 0.35 && weak) || dur <= 0.2 ? 'passing' : 'clash';
  }
  S[kind]++;
  if (kind === 'clash' && bad.length < 400) bad.push(`${inst} ${['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'][pc]}(${m}) @拍${beat.toFixed(2)} 長${dur.toFixed(2)}拍 over ${c.name}`);
  // 延音撐到下一顆和弦:下一顆不含這個音(也不是它的延伸音)就算跨和弦衝突
  if (kind !== 'passing') {
    const nx = chords.find(x => x.from > beat + 0.01 && x.from < beat + dur - 0.12);
    if (nx && !nx.pcs.includes(pc) && !tensions(nx).includes(((pc - nx.root) % 12 + 12) % 12)) {
      S.cross++; if (bad.length < 400) bad.push(`${inst} ${pc}(${m}) 撐進 ${nx.name}(從拍${beat.toFixed(2)}撐${dur.toFixed(2)}拍)`);
    }
  }
}
const out = { feel, prog, style: style || 'comp', secs: SECS, stats };
for (const [k, S] of Object.entries(stats)) S.clash_pct = +(100 * S.clash / S.n).toFixed(1), S.cross_pct = +(100 * S.cross / S.n).toFixed(1);
console.log(JSON.stringify(out));
const counts = {}; for (const x of bad) { const k = x.replace(/@拍[0-9.]+ /, '').replace(/\(從拍[0-9.]+/, '('); counts[k] = (counts[k] || 0) + 1; }
Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 25).forEach(([k, n]) => console.log('  ', n, '×', k));
