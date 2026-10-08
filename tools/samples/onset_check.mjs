// 取樣本身準不準:不加人性化(格子上)、不加殘響、跳過母帶,每一軌單獨算,
// 量「聲音真的開始的時間 − 排程的時間」。取樣前面有空白 / 起音慢,耳朵會聽成拖拍,引擎的時間再準也沒用。
// 用法:node tools/samples/onset_check.mjs [曲風 ...]    標準:每一軌中位數 |偏差| ≤ 3ms、95% ≤ 8ms
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, extname } from "node:path";
const ROOT = new URL("../../", import.meta.url).pathname;
const SMP = process.env.SMP ?? "/tmp/smp";
const REPO_DIR = {
  "sfzinstruments/SalamanderGrandPiano": "SalamanderGrandPiano", "sgossner/VSCO-2-CE": "VSCO-2-CE",
  "sfzinstruments/virtuosity_drums": "virtuosity_drums", "sfzinstruments/karoryfer.black-and-green-guitars": "karoryfer.black-and-green-guitars",
  "sfzinstruments/karoryfer.black-and-blue-basses": "bb", "sfzinstruments/jlearman.jRhodes3c": "jr", "sfzinstruments/jlearman.jRhodes3d": "jr3d", "tidalcycles/Dirt-Samples": "Dirt-Samples",
  "freepats/spanish-classical-guitar": "spanish-classical-guitar", "sfzinstruments/Project16Rickenbacker4001": "Project16Rickenbacker4001",
  "sfzinstruments/karoryfer.meatbass": "karoryfer.meatbass", "sfzinstruments/karoryfer.emilyguitar": "karoryfer.emilyguitar",
  "lavenderdotpet/CC0-Public-Domain-Sounds": "cc0sounds", "stevenmusic/ScrollScore": process.env.SCROLLSCORE ?? "/home/user/stevenmusic/scrollscore",
};
const server = createServer((q, r) => { try { const p = join(ROOT, decodeURIComponent(q.url.split("?")[0])); r.writeHead(200, { "content-type": { ".html": "text/html", ".mjs": "text/javascript", ".json": "application/json" }[extname(p)] ?? "application/octet-stream" }); r.end(readFileSync(p)); } catch { r.writeHead(404); r.end(); } }).listen(0);
const browser = await chromium.launch();
const page = await browser.newPage();
await page.route(/cdn\.jsdelivr\.net\/gh\/|raw\.githubusercontent\.com\//, route => {
  const u = new URL(route.request().url());
  const m = u.host === "cdn.jsdelivr.net" ? u.pathname.match(/^\/gh\/([^/]+\/[^@]+)@[^/]+\/(.*)$/) : u.pathname.match(/^\/([^/]+\/[^/]+)\/[^/]+\/(.*)$/);
  const dir = REPO_DIR[m[1]];
  try { route.fulfill({ status: 200, body: execFileSync("git", ["-C", dir.startsWith("/") ? dir : join(SMP, dir), "show", "HEAD:" + decodeURIComponent(m[2])], { maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "ignore"] }), headers: { "access-control-allow-origin": "*" } }); }
  catch { route.fulfill({ status: 404 }); }
});
await page.goto(`http://localhost:${server.address().port}/styles/index.html`);
await page.waitForFunction(() => window.__player);
const ids = process.argv.slice(2).length ? process.argv.slice(2) : ["pop", "mandopop_ballad", "jpop", "citypop", "kpop_dance", "rnb_neosoul", "lofi", "reggaeton"];
let bad = 0;
for (const id of ids) {
  const rows = await page.evaluate(async ([id, process_th]) => {
    const p = window.__player, { render } = await import("./engine.mjs");
    const opt = { density: "high", seed: 7, humanize: false, noReverb: true, raw: true };
    const ev = render(p.data, id, { ...opt, bars: 8 }).events;
    const out = {};
    const tracks = [...new Set(ev.map(e => e.track))];
    for (const t of tracks) {
      const { buffer } = await p.renderOffline(id, { ...opt, only: [t] }, 8);
      const sr = buffer.sampleRate, d0 = buffer.getChannelData(0), d1 = buffer.getChannelData(1);
      const n = d0.length, env = new Float32Array(n);
      for (let i = 0; i < n; i++) env[i] = Math.abs(d0[i]) + Math.abs(d1[i]);
      // 每一下:往前 15ms 的最大值當「前面已經在響的」,往後 60ms 的最大值;第一個超過 前 + 0.3×(後−前) 的位置
      const groups = new Map();
      for (const e of ev) if (e.track === t) groups.set(e.gridTime.toFixed(4), e);
      const devs = [];
      for (const e of groups.values()) {
        const when = e.time + 0.05 + (t === "drums" ? 0.006 : 0.006); // renderOffline 的 0.05 + 鼓組壓縮對齊的 6ms(全部一起)
        const i0 = Math.round(when * sr), pre = Math.round(0.015 * sr), post = Math.round(0.06 * sr);
        let a = 0, b = 0;
        for (let i = i0 - pre; i < i0; i++) a = Math.max(a, env[i] ?? 0);
        for (let i = i0 - Math.round(0.01 * sr); i < i0 + post; i++) b = Math.max(b, env[i] ?? 0);
        if (b < 1e-3 || b < a * 1.5) continue;   // 被前面的音蓋住,量不到
        const th = a + process_th * (b - a);
        let k = i0 - Math.round(0.01 * sr);
        while (k < i0 + post && env[k] < th) k++;
        devs.push((k / sr - when) * 1000);
      }
      out[t] = devs;
    }
    return out;
  }, [id, +(process.env.TH ?? 0.3)]);
  for (const [t, v] of Object.entries(rows)) {
    if (!v.length) continue;
    const s = [...v].sort((a, b) => a - b), q = p => s[Math.floor(p * (s.length - 1))];
    const med = q(0.5), p95 = Math.max(Math.abs(q(0.05)), Math.abs(q(0.95)));
    const ok = Math.abs(med) <= 3 && p95 <= 8;
    if (!ok) bad++;
    console.log(`${ok ? "✓" : "✗"} ${id.padEnd(16)} ${t.padEnd(7)} n=${String(v.length).padStart(3)}  中位 ${med.toFixed(1)}ms  5% ${q(0.05).toFixed(1)}  95% ${q(0.95).toFixed(1)}`);
  }
}
console.log(bad ? `不合格 ${bad}` : "全部合格");
await browser.close(); server.close();
process.exit(bad ? 1 : 0);
