// 鼓組壓縮的 6ms 預讀延遲有沒有補齊:同一個時間點送一個脈衝進大鼓匯流排與貝斯匯流排(分開算),量峰值位置差
// 用法:node tools/samples/align_check.mjs   (目標:< 0.2ms)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, extname } from "node:path";
const ROOT = new URL("../../", import.meta.url).pathname;
const server = createServer((q, r) => { try { const p = join(ROOT, decodeURIComponent(q.url.split("?")[0])); r.writeHead(200, { "content-type": { ".html": "text/html", ".mjs": "text/javascript", ".json": "application/json" }[extname(p)] ?? "application/octet-stream" }); r.end(readFileSync(p)); } catch { r.writeHead(404); r.end(); } }).listen(0);
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`http://localhost:${server.address().port}/styles/index.html`);
await page.waitForFunction(() => window.__player);
const r = await page.evaluate(async () => {
  const { Player } = await import("./player.mjs");
  const data = window.__player.data, man = window.__player.manifest;
  const peakAt = async bus => {
    const sr = 44100, ctx = new OfflineAudioContext(2, sr, sr);
    const p = new Player(data, man);
    p.setupAudio(ctx);
    await p.limiterReady;
    p.master.disconnect(); p.master.connect(ctx.destination);
    p.noReverb = true;
    const st = data.styles.find(s => s.id === "pop");
    p.style = st;
    const { buses } = p.buildBuses(st);
    const b = ctx.createBuffer(1, 64, sr); b.getChannelData(0)[0] = 0.3;
    const s = ctx.createBufferSource(); s.buffer = b; s.connect(buses[bus].in); s.start(0.1);
    const out = (await ctx.startRendering()).getChannelData(0);
    let m = 0, at = 0; for (let i = 0; i < out.length; i++) if (Math.abs(out[i]) > m) { m = Math.abs(out[i]); at = i; }
    return at / sr * 1000;
  };
  const kick = await peakAt("kick"), bass = await peakAt("bass"), keys = await peakAt("keys");
  return { kick, bass, keys };
});
const d = Math.max(Math.abs(r.kick - r.bass), Math.abs(r.kick - r.keys));
console.log(`大鼓峰值 ${r.kick.toFixed(3)}ms、貝斯 ${r.bass.toFixed(3)}ms、鍵盤 ${r.keys.toFixed(3)}ms → 差 ${d.toFixed(3)}ms ${d < 0.2 ? "✓" : "✗"}`);
await browser.close(); server.close();
process.exit(d < 0.2 ? 0 : 1);
