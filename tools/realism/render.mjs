/* 產生評測片段:每一筆 case 用**真的取樣**錄 10 秒,寫成 WAV,並把聲學特徵寫進 db/clips.jsonl。
   用法:node tools/realism/render.mjs [cases.json]   (需要 /tmp/smp 裡的取樣,見 README)
   - 取樣從本機讀(雲端環境連不到 CDN,見 CLAUDE.md「雲端環境量聲音」)
   - 從第 32 拍開始錄(背景的力度層都載完),長度用取樣數算,兩次錄同一筆差 ≤0.3dB */
import { chromium } from 'playwright';
import fs from 'fs'; import path from 'path'; import { execSync } from 'child_process';
import crypto from 'crypto'; import http from 'http';
/* 頁面一律從 http 開,不從 file:// 開:正式站在 GitHub Pages(https),而 file:// 底下
   AudioWorklet 載不到模組(看前面的限幅器會靜靜退回舊的鏈),量到的就不是使用者聽到的那一條 */
const SERVE = await new Promise(ok => { const sv = http.createServer((q, s) => {
  const f = decodeURIComponent(q.url.split('?')[0]);
  if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); }
  s.writeHead(200, { 'content-type': f.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream' }); s.end(fs.readFileSync(f)); });
  sv.listen(0, '127.0.0.1', () => ok({ sv, port: sv.address().port })); });
const HERE = path.dirname(new URL(import.meta.url).pathname);
const REPO = path.resolve(HERE, '../..');
const SECS = +process.env.REALISM_SECS || 10, FROM_BEAT = 32;
const cfg = JSON.parse(fs.readFileSync(process.argv[2] || path.join(HERE, 'cases.json'), 'utf8'));
/* REALISM_OUT:校準集(calib/)用自己的資料夾與 jsonl,不跟盲聽的題庫混在一起 */
const OUT = process.env.REALISM_OUT ? path.resolve(process.env.REALISM_OUT) : HERE;
const CLIPS = path.join(OUT, 'clips'); fs.mkdirSync(CLIPS, { recursive: true });
const missing = new Set(), prod404 = new Set();
/* **每一筆各自數**:用全域的 Set 大小判斷的話,兩個曲風缺同一批檔案時
   後面那一筆不會被擋下來(Swing 踩過:低音提琴的取樣全缺,照樣被收進來) */
let caseMissing = 0;
const trees = {};
function inRepo(repo, p){
  if (!trees[repo]) {
    try { trees[repo] = new Set(execSync(`git -C /tmp/smp/${repo} ls-tree -r --name-only HEAD`, { maxBuffer: 1 << 28 }).toString().split('\n')); }
    catch { trees[repo] = new Set(); }
  }
  return trees[repo].has(p);
}

function htmlFor(version){
  const out = `/tmp/realism-${version}.html`;
  if (version === 'WORKTREE') return path.join(REPO, 'index.html');
  fs.writeFileSync(out, execSync(`git -C ${REPO} show ${version}:index.html`));
  return out;
}
function commitOf(version){ return version === 'WORKTREE' ? 'worktree' : execSync(`git -C ${REPO} rev-parse --short ${version}`).toString().trim(); }
async function localSamples(pg, synth){
  await pg.route(/cdn\.jsdelivr\.net\/gh\/|raw\.githubusercontent\.com\/|tonejs\.github\.io\/audio\//, async r => {
    const u = r.request().url();
    /* `synth: true` 的 case 故意一個取樣都不給,錄到的就是合成備援——校準用的「已知比較假」那一組 */
    if (synth) return r.fulfill({ status: 404, body: '' });
    const m = /jsdelivr\.net\/gh\/[^/]+\/([^@]+)@[^/]+\/(.*)$/.exec(u) || /githubusercontent\.com\/[^/]+\/([^/]+)\/[^/]+\/(.*)$/.exec(u);
    let repo, p; if (m) { repo = m[1]; p = decodeURIComponent(m[2]); } else { repo = 'audio'; p = decodeURIComponent(/tonejs\.github\.io\/audio\/(.*)$/.exec(u)[1]); }
    const f = `/tmp/smp/${repo}/${p}`;
    if (fs.existsSync(f)) return r.fulfill({ status: 200, body: fs.readFileSync(f), headers: { 'access-control-allow-origin': '*' } });
    /* 原始 repo 裡**本來就沒有**這個檔案 = 正式環境也是 404(app 會改用別的 round robin),照錄;
       repo 裡有但還沒抓下來 = 要補抓,這一筆不能收 */
    if (inRepo(repo, p)) { missing.add(`${repo}/${p}`); caseMissing++; } else prod404.add(`${repo}/${p}`);
    return r.fulfill({ status: 404, body: '' });
  });
}
function wav16(L, R, sr){
  const n = L.length, buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 4, 4); buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(sr, 24);
  buf.writeUInt32LE(sr * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) { buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(L[i] * 32767))), 44 + i * 4); buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(R[i] * 32767))), 46 + i * 4); }
  return buf;
}
function features(L, R, sr){
  const n = L.length; let sl = 0, sr2 = 0, slr = 0, pk = 0, sm = 0;
  for (let i = 0; i < n; i++) { sl += L[i]*L[i]; sr2 += R[i]*R[i]; slr += L[i]*R[i]; const m = (L[i]+R[i])/2; sm += m*m; pk = Math.max(pk, Math.abs(L[i]), Math.abs(R[i])); }
  const rms = 10*Math.log10((sl+sr2)/2/n);
  const N = 8192, c = [31.5,63,125,250,500,1000,2000,4000,8000,16000], acc = new Float64Array(c.length); let fr = 0;
  const re = new Float64Array(N), im = new Float64Array(N);
  for (let o = 0; o + N <= n; o += N) { for (let i = 0; i < N; i++) { re[i] = (L[o+i]+R[o+i])/2*(0.5-0.5*Math.cos(2*Math.PI*i/N)); im[i] = 0; }
    for (let i = 1, j = 0; i < N; i++) { let b = N >> 1; for (; j & b; b >>= 1) j ^= b; j ^= b; if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; } }
    for (let len = 2; len <= N; len <<= 1) { const a = -2*Math.PI/len; for (let i = 0; i < N; i += len) for (let k = 0; k < len/2; k++) { const wr = Math.cos(a*k), wi = Math.sin(a*k), p = i+k+len/2, vr = re[p]*wr-im[p]*wi, vi = re[p]*wi+im[p]*wr; re[p] = re[i+k]-vr; im[p] = im[i+k]-vi; re[i+k] += vr; im[i+k] += vi; } }
    for (let k = 1; k < N/2; k++) { const f = k*sr/N, p = re[k]*re[k]+im[k]*im[k]; for (let b = 0; b < c.length; b++) if (f >= c[b]/Math.SQRT2 && f < c[b]*Math.SQRT2) acc[b] += p; } fr++; }
  const bands = [...acc].map(v => +(10*Math.log10(v/fr/(N*N)*8+1e-20)).toFixed(1));
  return { rms: +rms.toFixed(2), peak: +pk.toFixed(3), crest: +(20*Math.log10(pk)-rms).toFixed(2), corr: +(slr/Math.sqrt(sl*sr2)).toFixed(3),
    monoLoss: +(10*Math.log10(sm/((sl+sr2)/2))).toFixed(2), bal: +(10*Math.log10(sl/sr2)).toFixed(2), bands, bandsRel: bands.map(v => +(v-bands[2]).toFixed(1)) };
}

const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--autoplay-policy=no-user-gesture-required'] });
const out = fs.createWriteStream(path.join(OUT, OUT === HERE ? 'db/clips.jsonl' : 'clips.jsonl'), { flags: 'a' });
for (const cs of cfg.cases) {
  const commit = commitOf(cs.version), prog = cs.prog || cfg.progressions[cs.feel];
  const ovr = cs.ovr ? JSON.stringify(cs.ovr) : '';
  const id = crypto.createHash('sha1').update([commit, cs.feel, cs.style, prog, SECS, FROM_BEAT].join('|') + (ovr ? '|' + ovr : '') + (cs.synth ? '|synth' : '')).digest('hex').slice(0, 10);
  const wavPath = path.join(CLIPS, id + '.wav');
  if (fs.existsSync(wavPath)) { console.log('skip', id, commit, cs.feel, cs.style); continue; }
  caseMissing = 0;
  const pg = await b.newPage(); await localSamples(pg, !!cs.synth);
  const errs = []; pg.on('pageerror', e => errs.push(e.message));
  await pg.addInitScript(() => {
    window.__rec = { L: [], R: [], on: false };
    const orig = AudioNode.prototype.connect;
    AudioNode.prototype.connect = function (dst, ...r) {
      if (dst instanceof AudioDestinationNode && !this.__tap) { this.__tap = 1;
        const sp = this.context.createScriptProcessor(4096, 2, 2);
        sp.onaudioprocess = e => { if (!window.__rec.on) return; __rec.L.push(new Float32Array(e.inputBuffer.getChannelData(0))); __rec.R.push(new Float32Array(e.inputBuffer.getChannelData(1))); };
        orig.call(this, sp); orig.call(sp, dst); }
      return orig.call(this, dst, ...r);
    };
  });
  await pg.goto(`http://127.0.0.1:${SERVE.port}` + htmlFor(cs.version));
  await pg.fill('#chordInput', prog); await pg.dispatchEvent('#chordInput', 'input');
  /* A/B 用的覆寫:點曲風之前併進 FEELS[曲風](null = 拿掉那一層) */
  if (ovr) await pg.evaluate(([f, o]) => { const m = (t, x) => { for (const k in x) { if (x[k] && typeof x[k] === 'object' && !Array.isArray(x[k])) { t[k] = t[k] || {}; m(t[k], x[k]); } else t[k] = x[k]; } }; m(FEELS[f], JSON.parse(o)); }, [cs.feel, ovr]);
  await pg.click(`[data-feel="${cs.feel}"]`); await pg.click(`[data-style="${cs.style}"]`);
  /* REALISM_PROBE=<js 檔>:按播放之前在頁面裡跑(包函式記錄用),錄完呼叫 window.__probeReport() 印出來 */
  // REALISM_SOLO=<bus 名>:給 probe_solo.js 用(只留那條 bus)
  if (process.env.REALISM_SOLO) await pg.evaluate(b => { window.__soloBus = b; }, process.env.REALISM_SOLO);
  if (process.env.REALISM_PROBE) await pg.evaluate(fs.readFileSync(process.env.REALISM_PROBE, 'utf8'));
  /* REALISM_CPU=6:CPU 降速 6×(效能量測,配 probe_perf.js) */
  if (process.env.REALISM_CPU) { const c = await pg.context().newCDPSession(pg); await c.send('Emulation.setCPUThrottlingRate', { rate: +process.env.REALISM_CPU }); }
  await pg.click('#playBtn');
  await pg.waitForFunction(() => typeof playing !== 'undefined' && playing, null, { timeout: 120000 });
  await pg.waitForFunction(b => currentBeat() >= b, FROM_BEAT, { timeout: 180000, polling: 5 });
  await pg.evaluate(() => { __rec.on = true; });
  await pg.waitForFunction(s => __rec.L.length * 4096 >= s * ctx.sampleRate, SECS, { timeout: 120000, polling: 50 });
  const r = await pg.evaluate((s) => { const cat = a => { const n = a.reduce((q, x) => q + x.length, 0), o = new Float32Array(n); let p = 0; for (const x of a) { o.set(x, p); p += x.length; } return o; };
    const L = cat(__rec.L), R = cat(__rec.R), n = Math.floor(s * ctx.sampleRate); return { L: Array.from(L.subarray(0, n)), R: Array.from(R.subarray(0, n)), sr: ctx.sampleRate, bpm: Math.round(60 / spb) }; }, SECS);
  if (process.env.REALISM_PROBE) console.log('probe', cs.feel, cs.style, JSON.stringify(await pg.evaluate(() => window.__probeReport ? window.__probeReport() : null)));
  await pg.close();
  /* 有取樣沒載到的話,錄到的是合成備援的聲音——那一筆不能收,補抓之後重跑 */
  if (caseMissing) { console.log('retry', id, cs.feel, cs.style, '(缺', caseMissing, '個取樣)'); continue; }
  fs.writeFileSync(wavPath, wav16(r.L, r.R, r.sr));
  const row = { id, commit, version: cs.version, feel: cs.feel, style: cs.style, prog, ovr: cs.ovr || null, label: cs.label || null, synth: !!cs.synth, batch: cs.batch || 1, bpm: r.bpm, secs: SECS, fromBeat: FROM_BEAT, sr: r.sr,
    renderedAt: new Date().toISOString(), errors: errs, features: features(r.L, r.R, r.sr) };
  out.write(JSON.stringify(row) + '\n');
  console.log('ok', id, commit, cs.feel, cs.style, row.features.rms, row.features.peak, errs.length ? 'ERR ' + errs[0] : '');
}
out.end(); await b.close(); SERVE.sv.close();
if (prod404.size) fs.writeFileSync(path.join(HERE, 'db/prod404.txt'), [...prod404].sort().join('\n') + '\n');
if (missing.size) { fs.writeFileSync('/tmp/smp/missing.txt', [...missing].join('\n')); console.log('MISSING', missing.size, '→ 補抓後重跑(已錄的會跳過)'); }
