/* 用 Playwright 跑 tools/webmix/ 的兩個測試頁(nulltest.html、test.html)。先在 repo 根目錄開 http:
     python3 -m http.server 8765 &   然後   node tools/realism/webmix_test.mjs */
import { chromium } from 'playwright';
const b = await chromium.launch(); let bad = 0;
for (const page of ['nulltest.html', 'test.html']) {
  const p = await b.newPage();
  await p.goto('http://127.0.0.1:8765/tools/webmix/' + page);
  await p.waitForFunction(() => window.__res, null, { timeout: 180000 });
  const r = await p.evaluate(() => { const x = Object.assign({}, window.__res); delete x.L; delete x.R; return x; });
  console.log('==', page, JSON.stringify(r)); if (!r.ok) bad++;
}
await b.close(); process.exit(bad ? 1 : 0);
