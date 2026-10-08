// 主網頁(index.html)接上新引擎之後的冒煙測試:每個風格按播放、換拍號、改和弦、停止;不能有錯誤、要真的排到音
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, extname } from "node:path";
const ROOT = new URL("../../", import.meta.url).pathname, SMP = process.env.SMP ?? "/tmp/smp";
const DIR = { SalamanderGrandPiano: "SalamanderGrandPiano", "VSCO-2-CE": "VSCO-2-CE", virtuosity_drums: "virtuosity_drums",
  "karoryfer.black-and-green-guitars": "karoryfer.black-and-green-guitars", "karoryfer.black-and-blue-basses": "bb",
  "jlearman.jRhodes3c": "jr", "jlearman.jRhodes3d": "jr3d", "Dirt-Samples": "Dirt-Samples",
  "Project16Rickenbacker4001": "Project16Rickenbacker4001", "karoryfer.meatbass": "karoryfer.meatbass", "karoryfer.emilyguitar": "karoryfer.emilyguitar",
  "CC0-Public-Domain-Sounds": "cc0sounds", "ScrollScore": "/home/user/stevenmusic/scrollscore" };
const server = createServer((q, s) => { try { const p = join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  s.writeHead(200, { "content-type": { ".html": "text/html", ".mjs": "text/javascript", ".json": "application/json" }[extname(p)] ?? "application/octet-stream" });
  s.end(readFileSync(p)); } catch { s.writeHead(404); s.end(); } }).listen(0);
const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on("pageerror", e => errors.push(e.message));
page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text()); });
await page.route(/cdn\.jsdelivr\.net\/gh\/|raw\.githubusercontent\.com\//, r => {
  const u = new URL(r.request().url());
  const m = u.host === "cdn.jsdelivr.net" ? u.pathname.match(/^\/gh\/[^/]+\/([^@]+)@[^/]+\/(.*)$/) : u.pathname.match(/^\/[^/]+\/([^/]+)\/[^/]+\/(.*)$/);
  const dir = DIR[m[1]];
  if (!dir) return r.fulfill({ status: 404 });
  try { r.fulfill({ status: 200, headers: { "access-control-allow-origin": "*" }, body: execFileSync("git", ["-C", dir.startsWith("/") ? dir : join(SMP, dir), "show", "HEAD:" + decodeURIComponent(m[2])], { maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "ignore"] }) }); }
  catch { r.fulfill({ status: 404 }); }
});
await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.fulfill({ status: 200, body: "" }));
await page.goto(`http://localhost:${server.address().port}/index.html`);
await page.waitForFunction(() => typeof BT !== "undefined" && BT, null, { timeout: 60000 });
const results = [];
const styles = ["pop", "mandopop_ballad", "jpop", "citypop", "kpop_dance", "kpop_ballad", "rnb_neosoul", "lofi", "reggaeton"];
for (const id of styles) {
  await page.click(`#feelSeg [data-feel="${id}"]`);
  await page.click("#playBtn");
  await page.waitForFunction(() => playing && btSession, null, { timeout: 120000 });
  await page.waitForTimeout(2500);
  const r = await page.evaluate(() => ({ feel: feelNow, beat: currentBeat().toFixed(1), cached: btCache.size, bpm: bpmOn,
    on: document.querySelector("#barsGrid .on") ? 1 : 0, transport: document.querySelector("#transportL1")?.textContent }));
  results.push([id, r]);
  await page.click("#playBtn");
  await page.waitForTimeout(200);
}
// 3/4 與 6/8、改和弦、移調
await page.click(`#feelSeg [data-feel="pop"]`);
for (const m of ["3/4", "6/8"]) {
  await page.click(`#meterSeg [data-meter="${m}"]`);
  await page.click("#playBtn");
  await page.waitForFunction(() => playing && btSession, null, { timeout: 120000 });
  await page.waitForTimeout(2000);
  results.push([m, await page.evaluate(() => ({ meter: meterOn, beats: beatsInBar(), beat: currentBeat().toFixed(1) }))]);
  await page.click("#playBtn");
}
await page.click(`#meterSeg [data-meter="4/4"]`);
await page.fill("#chordInput", "Cmaj7 | A7b9 | Dm9 G13 | C6/9");
await page.dispatchEvent("#chordInput", "input");
await page.click("#playBtn");
await page.waitForFunction(() => playing && btSession, null, { timeout: 120000 });
await page.waitForTimeout(2000);
results.push(["chords", await page.evaluate(() => ({ text: chordInput.value, bars: parsed.bars.length, ok: parsed.bars.every(b => b.ok) }))]);
await page.click("#playBtn");
// 真的有聲音:在限幅器之後掛分析器,播 8 秒(預備拍之後)量音量與排了幾顆音
await page.click(`#feelSeg [data-feel="citypop"]`);
await page.fill("#chordInput", "Fmaj7 | E7 | Am7 | Gm7 C7");
await page.dispatchEvent("#chordInput", "input");
await page.click("#playBtn");
await page.waitForFunction(() => playing && btSession, null, { timeout: 120000 });
const level = await page.evaluate(async () => {
  const an = ctx.createAnalyser(); an.fftSize = 2048;
  (btPlayer.limiter || btPlayer.loud).connect(an);
  let n = 0; const orig = btPlayer.sampler.note.bind(btPlayer.sampler);
  btPlayer.sampler.note = (...a) => { n++; return orig(...a); };
  const buf = new Float32Array(2048); let peak = 0, sum = 0, k = 0;
  const t0 = performance.now();
  while (performance.now() - t0 < 8000) {
    await new Promise(r => setTimeout(r, 50));
    an.getFloatTimeDomainData(buf);
    for (const x of buf) { peak = Math.max(peak, Math.abs(x)); sum += x * x; k++; }
  }
  return { notes: n, peak: +peak.toFixed(3), rmsDb: +(10 * Math.log10(sum / k)).toFixed(1), lit: document.querySelector("#barsGrid .on")?.dataset?.i ?? document.querySelectorAll("#barsGrid .on").length };
});
results.push(["audio", level]);
await page.click("#playBtn");
// B1:播放中換曲風,新曲風的樂器要跟上(換完之後 12 拍內 Rhodes 漏音 ≤ 2)
await page.click(`#feelSeg [data-feel="pop"]`);
await page.fill("#chordInput", "C | Am | F | G");
await page.dispatchEvent("#chordInput", "input");
await page.click("#playBtn");
await page.waitForFunction(() => playing && btSession && currentBeat() > 16, null, { timeout: 120000 });
const b1 = await page.evaluate(async () => {
  const stat = { ok: 0, miss: 0 };
  const orig = btPlayer.sampler.note.bind(btPlayer.sampler);
  btPlayer.sampler.note = (instr, ...a) => { const r = orig(instr, ...a); if (instr === "rhodes") r ? stat.ok++ : stat.miss++; return r; };
  document.querySelector('#feelSeg [data-feel="citypop"]').click();
  const start = currentBeat();
  while (currentBeat() < start + 12) await new Promise(r => setTimeout(r, 100));
  return stat;
});
results.push(["B1 換曲風", b1]);
// B3:第 2 圈中途改和弦,這一圈的聲音要用畫面上的和弦(barsNow)
const b3 = await page.evaluate(async () => {
  while (btCurLap < 1) await new Promise(r => setTimeout(r, 100));
  chordInput.value = "Dm | G | C | C"; chordInput.dispatchEvent(new Event("input"));
  await new Promise(r => setTimeout(r, 600));
  return { lap: btCurLap, sameAsScreen: btBarsOfLap(btCurLap) === barsNow(), lapBars: lapBars === null };
});
results.push(["B3 改和弦", b3]);
await page.click("#playBtn");
// B2:重新開頁面,第一次播 Lo-fi,預備拍不能排到過去
results.push(["B2 Lo-fi 第一次", await (async () => {
  await page.goto(page.url());
  await page.waitForFunction(() => typeof BT !== "undefined" && BT, null, { timeout: 60000 });
  await page.click(`#feelSeg [data-feel="lofi"]`);
  await page.evaluate(() => { window.__late = []; const h = () => { if (!btPlayer) return setTimeout(h, 5); const o = btPlayer.sampler.hit.bind(btPlayer.sampler);
    btPlayer.sampler.hit = (k, pc, v, when, d) => { window.__late.push(when - ctx.currentTime); return o(k, pc, v, when, d); }; }; h(); });
  await page.click("#playBtn");
  await page.waitForFunction(() => playing && window.__late.length > 4, null, { timeout: 120000 });
  const r = await page.evaluate(() => ({ minAhead: +Math.min(...window.__late.slice(0, 4)).toFixed(3) }));
  await page.click("#playBtn");
  return r;
})()]);
for (const [k, v] of results) console.log(k.padEnd(16), JSON.stringify(v));
console.log("errors:", errors.length ? errors : "none");
await browser.close(); server.close();
