import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--autoplay-policy=no-user-gesture-required'] });
for (const u of ['file:///home/user/BackingTrack/index.html', 'http://127.0.0.1:8765/index.html']) {
  const pg = await b.newPage(); await pg.route(/^https:/, r => r.abort());
  await pg.goto(u);
  const r = await pg.evaluate(async () => { ensureAudio(); await new Promise(r => setTimeout(r, 1500));
    try { const url = URL.createObjectURL(new Blob([LIMITER_SRC], {type:'application/javascript'})); await ctx.audioWorklet.addModule(url); } catch (e) { return 'ERR ' + e.message; }
    return 'trueLimiter=' + !!trueLimiter; });
  console.log(u, r); await pg.close();
}
await b.close();
