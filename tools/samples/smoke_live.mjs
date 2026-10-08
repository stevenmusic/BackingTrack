// 試聽頁的即時播放冒煙測試:按播放 → 換風格 → 停止,不能有錯誤、要真的排到音
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, extname } from "node:path";
const ROOT = new URL("../../", import.meta.url).pathname, SMP = process.env.SMP ?? "/tmp/smp";
const DIR = { SalamanderGrandPiano: "SalamanderGrandPiano", "VSCO-2-CE": "VSCO-2-CE", virtuosity_drums: "virtuosity_drums",
  "karoryfer.black-and-green-guitars": "karoryfer.black-and-green-guitars", "karoryfer.black-and-blue-basses": "bb",
  "jlearman.jRhodes3c": "jr", "Dirt-Samples": "Dirt-Samples" };
const server = createServer((q, s) => { try { const p = join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  s.writeHead(200, { "content-type": { ".html": "text/html", ".mjs": "text/javascript", ".json": "application/json" }[extname(p)] ?? "application/octet-stream" });
  s.end(readFileSync(p)); } catch { s.writeHead(404); s.end(); } }).listen(0);
const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", e => errors.push(e.message));
await page.route(/cdn\.jsdelivr\.net\/gh\//, r => {
  const m = new URL(r.request().url()).pathname.match(/^\/gh\/[^/]+\/([^@]+)@[^/]+\/(.*)$/);
  try { r.fulfill({ status: 200, body: execFileSync("git", ["-C", join(SMP, DIR[m[1]]), "show", "HEAD:" + decodeURIComponent(m[2])], { maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "ignore"] }) }); }
  catch { r.fulfill({ status: 404 }); }
});
await page.goto(`http://localhost:${server.address().port}/styles/index.html`);
await page.click("#play");
await page.waitForFunction(() => document.querySelector("#play").dataset.state === "playing", null, { timeout: 120000 });
await page.waitForTimeout(3000);
const a = await page.evaluate(() => ({ idx: window.__player.idx, bar: document.querySelector(".bar.on")?.dataset.i }));
await page.click('.chip[data-id="citypop"]');
await page.waitForFunction(() => document.querySelector("#play").dataset.state === "playing" && window.__player.style.id === "citypop", null, { timeout: 120000 });
await page.waitForTimeout(2000);
const b = await page.evaluate(() => window.__player.idx);
await page.fill("#chords", "C | Hm");
await page.dispatchEvent("#chords", "change");
await page.waitForTimeout(500);
const err = await page.textContent("#err");
await page.fill("#chords", "");
await page.dispatchEvent("#chords", "change");
await page.waitForTimeout(500);
// 看不懂的和弦會停掉播放;清空後按一次播放、再按一次停止
await page.click("#play");
await page.waitForFunction(() => document.querySelector("#play").dataset.state === "playing", null, { timeout: 120000 });
await page.click("#play");
const state = await page.evaluate(() => document.querySelector("#play").dataset.state);
console.log({ popScheduled: a.idx, barLit: a.bar, citypopScheduled: b, err, stateAfterStop: state, errors });
await browser.close(); server.close();
