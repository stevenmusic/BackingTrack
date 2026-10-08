// 小節編輯條「滑方塊改長度」的冒煙測試:手指(touch)與滑鼠各滑一次,看拍數、拍線發亮、觸覺、直滑不搶捲動
// 用法:node tools/samples/swipe_test.mjs
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, extname } from "node:path";
const ROOT = new URL("../../", import.meta.url).pathname;
const server = createServer((q, r) => { try { const b = readFileSync(join(ROOT, decodeURIComponent(q.url.split("?")[0]))); r.writeHead(200, { "content-type": { ".html": "text/html", ".mjs": "text/javascript", ".json": "application/json" }[extname(q.url.split("?")[0])] ?? "application/octet-stream" }); r.end(b); } catch { r.writeHead(404); r.end(); } }).listen(0);
const browser = await chromium.launch();
let fail = 0;
const ok = (c, m) => { console.log((c ? "✓ " : "✗ ") + m); if (!c) fail++; };
for (const touch of [true, false]) {
  const ctx = await browser.newContext({ hasTouch: touch, isMobile: touch, viewport: touch ? { width: 390, height: 844 } : { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.fulfill({ status: 200, body: "" }));
  await page.addInitScript(() => { window.__vib = 0; navigator.vibrate = () => { window.__vib++; return true; }; });
  page.on("pageerror", e => { console.log("pageerror", e.message); fail++; });
  await page.goto(`http://localhost:${server.address().port}/index.html`);
  const set = async t => { await page.fill("#chordInput", t); await page.dispatchEvent("#chordInput", "input"); await page.waitForTimeout(150); };
  const text = () => page.inputValue("#chordInput");
  const cells = async () => (await page.$$eval("#beLane .be-beat", els => els.map(e => e.getBoundingClientRect())));
  // 用 CDP 送 touch / 滑鼠的拖曳(一路經過每一格)
  const drag = async (x0, y0, x1, y1, inspect) => {
    const steps = 12;
    if (touch) {
      const cdp = await ctx.newCDPSession(page);
      const tp = (x, y) => [{ x, y, id: 1 }];
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: tp(x0, y0) });
      for (let s = 1; s <= steps; s++) await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: tp(x0 + (x1 - x0) * s / steps, y0 + (y1 - y0) * s / steps) });
      if (inspect) await inspect();
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    } else {
      await page.mouse.move(x0, y0); await page.mouse.down();
      for (let s = 1; s <= steps; s++) await page.mouse.move(x0 + (x1 - x0) * s / steps, y0 + (y1 - y0) * s / steps);
      if (inspect) await inspect();
      await page.mouse.up();
    }
    await page.waitForTimeout(150);
  };
  const tag = touch ? "[手機 touch]" : "[桌機 滑鼠]";
  // 1. C G(各 2 拍)→ 把 C 從第 1 格滑到第 3 格 → C 3 拍、G 1 拍
  await set("C G | F G");
  await page.click("#barsGrid > *:first-child").catch(() => {});
  let c = await cells(), b = await page.$$eval("#beLane .be-block", els => els.map(e => e.getBoundingClientRect()));
  const y = c[0].y + c[0].height / 2;
  let lit = -1;
  await drag(c[0].x + c[0].width / 2, y, c[2].x + c[2].width / 2, y, async () => {
    lit = await page.$$eval("#beLane .be-beat", els => els.findIndex(e => e.classList.contains("lit")));
  });
  ok((await text()).replace(/\s+/g, " ").startsWith("C / / G"), `${tag} 第一顆滑到第 3 格 → 「${await text()}」`);
  ok(lit === 3, `${tag} 滑的時候第 3 拍後面那條線亮(lit 在第 ${lit} 條)`);
  ok(await page.$$eval("#beLane .be-beat.lit", e => e.length) === 0, `${tag} 放開之後不亮`);
  if (touch) ok(await page.evaluate(() => window.__vib) >= 1, `${tag} 觸覺回饋 ${await page.evaluate(() => window.__vib)} 次`);
  // 2. 最後一顆:G(1 拍)往左滑到第 2 格 → C 1 拍、G 3 拍
  c = await cells(); b = await page.$$eval("#beLane .be-block", els => els.map(e => e.getBoundingClientRect()));
  await drag(b[1].x + b[1].width / 2, y, c[1].x + c[1].width / 2, y);
  ok((await text()).replace(/\s+/g, " ").startsWith("C G / /"), `${tag} 最後一顆往左滑到第 2 格(1 拍 + 3 拍) → 「${await text()}」`);
  // 3. 直的滑不改(在捲頁面)
  const before = await text();
  c = await cells();
  await drag(c[0].x + c[0].width / 2, y, c[0].x + c[0].width / 2 + 3, y + 60);
  ok(await text() === before, `${tag} 直的滑不改和弦`);
  // 4. 點一下還是選
  await set("C G | F G");
  b = await page.$$eval("#beLane .be-block", els => els.map(e => e.getBoundingClientRect()));
  if (touch) await page.tap("#beLane .be-block:nth-of-type(2)").catch(async () => page.touchscreen.tap(b[1].x + 5, b[1].y + 5));
  else await page.mouse.click(b[1].x + b[1].width / 2, b[1].y + b[1].height / 2);
  await page.waitForTimeout(100);
  ok(await page.$$eval("#beLane .be-block", els => els[1].classList.contains("sel")), `${tag} 點一下 = 選那一顆`);
  // 6. 一小節只有一顆:往左滑到第 3 格 → 撐 3 拍,剩 1 拍是同一個和弦,選到新的那顆
  await set("C | F");
  await page.click("#barsGrid > *:first-child").catch(() => {});
  c = await cells();
  await drag(c[3].x + c[3].width / 2, y, c[2].x + c[2].width / 2, y);
  ok((await text()).replace(/\s+/g, " ").startsWith("C / / C |"), `${tag} 一顆的時候往左滑到第 3 格 → 「${await text()}」`);
  ok(await page.$$eval("#beLane .be-block", els => els.length === 2 && els[1].classList.contains("sel")), `${tag} 切出來的那顆被選到`);
  await set("C | F");
  c = await cells();
  await drag(c[3].x + c[3].width / 2, y, c[3].x + c[3].width / 2 - 20, y);
  ok((await text()).replace(/\s+/g, " ").startsWith("C | F"), `${tag} 一顆的時候滑回第 4 格 = 不切`);
  // 5. 寫回去的字讀回來要一樣:1 拍 + 3 拍的那一格,編輯條上兩塊的寬度是 1:3
  await set("C G / / | F G");
  b = await page.$$eval("#beLane .be-block", els => els.map(e => e.getBoundingClientRect().width));
  ok(Math.abs(b[1] / b[0] - 3) < 0.15, `${tag} 「C G / /」畫成 1:3(${(b[1] / b[0]).toFixed(2)})`);
  await ctx.close();
}
console.log(fail ? `失敗 ${fail}` : "全部通過");
await browser.close(); server.close();
process.exit(fail ? 1 : 0);
