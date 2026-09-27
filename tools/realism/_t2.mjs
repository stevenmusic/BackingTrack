import { chromium } from 'playwright';
const b = await chromium.launch(); const p = await b.newPage();
p.on('console', m => console.log('console:', m.text()));
await p.goto('http://127.0.0.1:8765/tools/webmix/test.html');
await p.waitForFunction(() => window.__res, null, { timeout: 120000 });
console.log(JSON.stringify(await p.evaluate(() => window.__res)).slice(0, 300));
await b.close();
