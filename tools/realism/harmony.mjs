/* 和聲檢查:每一件樂器彈的每一顆音,對照「那一刻真的在響的和弦」(含和弦變化換過的那一顆)。
   node tools/realism/harmony.mjs <曲風> "<和弦進行>" [秒數] [style]
   分類:和弦音 / 可用的延伸音 / 經過音(短、弱拍) / **衝突**(長或落在強拍的非和弦音)/ 跨和弦(延音撐到下一顆和弦卻不是它的音) */
import { chromium } from 'playwright';
import http from 'http'; import fs from 'fs';
const [feel, prog, secsArg, style, meter] = process.argv.slice(2);
const SECS = +secsArg || 30;
const sv = http.createServer((q, s) => { const f = decodeURIComponent(q.url.split('?')[0]); if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); } s.writeHead(200, { 'content-type': f.endsWith('.html') ? 'text/html' : 'application/octet-stream' }); s.end(fs.readFileSync(f)); });
await new Promise(ok => sv.listen(0, ok));
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--autoplay-policy=no-user-gesture-required'] });
const pg = await b.newPage();
await pg.route(/^https:/, r => r.abort());                       // 取樣不用載:只記「彈了哪些音」
await pg.goto(`http://127.0.0.1:${sv.address().port}/home/user/BackingTrack/index.html`);
await pg.fill('#chordInput', prog); await pg.dispatchEvent('#chordInput', 'input');
if (meter) await pg.click(`[data-meter="${meter}"]`);
await pg.click(`[data-feel="${feel}"]`); await pg.click(`[data-style="${style || 'comp'}"]`);
/* HOVR='{...}':跟 render.mjs 的 ovr 一樣,深合併進 FEELS[曲風](A/B 用,例如 HOVR='{"color":{"maj7":[14]}}') */
if (process.env.HOVR) await pg.evaluate(([f, o]) => { const m = (t, x) => { for (const k in x) { if (x[k] && typeof x[k] === 'object' && !Array.isArray(x[k])) { t[k] = t[k] || {}; m(t[k], x[k]); } else t[k] = x[k]; } }; m(FEELS[f], JSON.parse(o)); }, [feel, process.env.HOVR]);
await pg.evaluate(() => {
  window.__H = { notes: [], chords: {} };
  const tb = t => anchorBeat + (t - anchorTime) / spb;              // 時間 → 拍
  const rec = (inst, m, t, d) => { if (typeof m === 'number' && isFinite(m)) __H.notes.push([inst, m, tb(t), d / spb]); };
  const wrap = (name, fn) => { const o = window[name]; window[name] = function () { try { fn.apply(null, arguments); } catch (e) {} return o.apply(this, arguments); }; };
  wrap('playNote', (m, t, d) => rec('keys', m, t, d));
  wrap('playBassNote', (m, t, d) => rec('bass', m, t, d));
  wrap('pluck', (m, t, g, tone, mute) => rec('gtr', m, t, mute > 0 ? mute : 0.5 * spb));
  wrap('playKeysChord', (ms, t, d, g, kind) => (ms || []).forEach(m => rec(kind === 'low' ? 'padlow' : 'pad', m, t, d)));
  wrap('padLegato', (ms, t, d) => (ms || []).forEach(m => rec('pad', m, t, d)));
  wrap('playBrass', (ms, t, d) => (ms || []).forEach(m => rec('brass', m, t, d)));
  wrap('synthKeyNote', (m, t, d) => rec('synth', m, t, d));
  wrap('playArp', (m, t, d) => rec('arp', m, t, d));
  wrap('playVox', (m, t, d) => rec('vox', m, t, d));
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
          iv: sp.chord.intervals.map(x => x % 12), ivCore: sp.chord.intervals.filter(x => x < 12).map(x => x % 12), name: sp.chord.text || sp.chord.name || '' }));
      }
    } catch (e) {}
    return r;
  };
});
await pg.click('#playBtn');
await pg.waitForFunction(s => typeof playing !== 'undefined' && playing && currentBeat() > 8 + s / spb, SECS, { timeout: 300000, polling: 500 });
const H = await pg.evaluate(() => Object.assign(__H, { loopBars: voicings.length, countIn: countInBeats }));
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
const lastTo = chords.length ? chords[chords.length - 1].to : 0;
for (const [inst, m, beat, dur] of H.notes) {
  const c = at(beat + 0.01); if (!c) continue;
  // 錄音最後那顆和弦還不知道下一顆是誰,接近音判不出來——不算
  if (c.to >= lastTo - 1e-6) continue;
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
  /* HARM_DUMP=1:屬七和弦上的「十一度」(大三度上面的四度,避免音)每一顆都印出來 */
  if (process.env.HARM_CLASH && kind === 'clash') console.log('  [衝突]', inst, m, '拍', beat.toFixed(2), '長', dur.toFixed(2), 'over', c.name, '小節內第', ((beat - (H.countIn||0)) % 3).toFixed(2), '拍,下一顆', (chords.find(x => x.from >= c.to - 1e-6) || {}).name, '從', c.from.toFixed(2), '到', c.to.toFixed(2));
  if (process.env.HARM_DUMP && c.iv.includes(4) && c.iv.includes(10) && rel === 5)
    console.log('  [十一度]', inst, m, '拍', beat.toFixed(2), '長', dur.toFixed(2), '歸類', kind, 'over', c.name);
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
/* ══ 旋律檢查(規則見 index.html 的 `melodyOk`)════════════════════
   旋律 = 和弦樂器**每一下的頂音** + 單音線條(arp、人聲切片)的**每一顆**。
   只准用和弦骨架音(根、三、五、六、七、sus 的二/四、轉位低音),
   九/十一/十三度與調外音都不准,屬七和弦的降七度也不准。**一定要是 0** */
{
  const core = (c, pc) => {
    const rel = ((pc - c.root) % 12 + 12) % 12, iv = new Set(c.iv);
    if (iv.has(4) && iv.has(10) && rel === 10) return false;
    if (pc === c.bass) return true;
    return c.ivCore.includes(rel);
  };
  /* 同一下的音**不是同時落下的**(和弦攤開 4–12ms、刷弦一條一條錯開),
     所以照時間排序、間隔小於 0.1 拍的算同一下,不能用四捨五入的格子切 */
  const groups = [];
  const byInst = {};
  for (const [inst, m, beat] of H.notes) {
    if (inst === 'bass' || inst === 'padlow') continue;
    (byInst[inst] || (byInst[inst] = [])).push([beat, m]);
  }
  for (const [inst, arr] of Object.entries(byInst)) {
    arr.sort((a, b) => a[0] - b[0]);
    const single = inst === 'arp' || inst === 'vox';
    let cur = null;
    for (const [beat, m] of arr) {
      if (single || !cur || beat - cur.last > 0.1) { cur = { inst, beat, last: beat, ms: [] }; groups.push(cur); }
      cur.ms.push(m); cur.last = beat;
    }
  }
  const T = {}, ex = {};
  for (const g of groups) {
    const c = at(g.beat + 0.01); if (!c) continue;
    const top = Math.max(...g.ms), pc = ((top % 12) + 12) % 12;
    const S = T[g.inst] || (T[g.inst] = { 下數: 0, 違規: 0 });
    S.下數++;
    if (!core(c, pc)) { S.違規++; const k = `${g.inst} ${['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'][pc]} over ${c.name}`; ex[k] = (ex[k] || 0) + 1; }
  }
  /* HARM_TOPS=1:鋼琴頂音線有多「活」——用了幾種音、多常換音、色彩音佔幾成 */
  if (process.env.HARM_TOPS) {
    // 只看右手:左手的低音常常跟右手不同時落下,單獨成一「下」會把頂音線攪亂
    const ks = groups.filter(g => g.inst === 'keys' && Math.max(...g.ms) >= 55).sort((a, b) => a.beat - b.beat);
    const tops = ks.map(g => Math.max(...g.ms));
    let moves = 0, steps = 0, color = 0;
    for (let i = 1; i < tops.length; i++) { const d = Math.abs(tops[i] - tops[i - 1]); if (d) { moves++; if (d <= 2) steps++; } }
    for (const g of ks) { const c = at(g.beat + 0.01); if (c && !c.ivCore.includes((((Math.max(...g.ms) - c.root) % 12) + 12) % 12)) color++; }
    console.log('頂音線:', JSON.stringify({ 下數: tops.length, 用了幾種音: new Set(tops).size, 換音比例: +(moves / Math.max(1, tops.length - 1)).toFixed(2), 級進佔換音: +(steps / Math.max(1, moves)).toFixed(2), 色彩音比例: +(color / Math.max(1, tops.length)).toFixed(2) }));
  }
  const total = Object.values(T).reduce((a, S) => a + S.違規, 0);
  console.log('旋律上的和弦外音:', total, JSON.stringify(T));
  Object.entries(ex).sort((a, b) => b[1] - a[1]).slice(0, 10).forEach(([k, n]) => console.log('   ', n, '×', k));
}
