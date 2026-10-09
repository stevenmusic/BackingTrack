// 用無頭 Chromium 把 styles/ 的風格離線算成 WAV,並量 peak / RMS。
// CDN 的取樣請求導到本機 blobless clone(/tmp/smp,git show 現抓)。
// 用法:node tools/samples/render_styles.mjs <輸出資料夾> [style[:progression[:density[:bars[:only[:flag]]]]]] ...]
// flag 用 / 串:dry(不加空間)、raw(跳過母帶鏈)、wet(只要殘響)、probe(印出鼓組 / 黏著壓縮在壓的時候壓幾 dB:95 百分位)、grid(不加人性化,量取樣本身的起音)、on=a+b / off=a+b(開 / 關可選聲部,例:off=vinyl)
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
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
const out = process.argv[2] ?? "/tmp/render";
mkdirSync(out, { recursive: true });
const jobs = process.argv.slice(3);

const server = createServer((req, res) => {
  const p = join(ROOT, decodeURIComponent(req.url.split("?")[0]));
  try {
    const body = readFileSync(p);
    const type = { ".html": "text/html", ".mjs": "text/javascript", ".js": "text/javascript", ".json": "application/json" }[extname(p)] ?? "application/octet-stream";
    res.writeHead(200, { "content-type": type }); res.end(body);
  } catch { res.writeHead(404); res.end(); }
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
const page = await browser.newPage();
let missing = 0;
await page.route(/cdn\.jsdelivr\.net\/gh\/|raw\.githubusercontent\.com\//, route => {
  const u = new URL(route.request().url());
  let repo, path;
  if (u.host === "cdn.jsdelivr.net") {
    const m = u.pathname.match(/^\/gh\/([^/]+\/[^@]+)@[^/]+\/(.*)$/); repo = m[1]; path = m[2];
  } else {
    const m = u.pathname.match(/^\/([^/]+\/[^/]+)\/[^/]+\/(.*)$/); repo = m[1]; path = m[2];
  }
  try {
    const body = execFileSync("git", ["-C", REPO_DIR[repo].startsWith("/") ? REPO_DIR[repo] : join(SMP, REPO_DIR[repo]), "show", "HEAD:" + decodeURIComponent(path)], { maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "ignore"] });
    route.fulfill({ status: 200, body, headers: { "access-control-allow-origin": "*" } });
  } catch { missing++; route.fulfill({ status: 404 }); }
});
page.on("pageerror", e => console.log("pageerror", e.message));
await page.goto(`http://localhost:${port}/styles/index.html`);
await page.waitForFunction(() => window.__player);

function wav(chs, sr) {
  const n = chs[0].length, b = Buffer.alloc(44 + n * 4);
  b.write("RIFF", 0); b.writeUInt32LE(36 + n * 4, 4); b.write("WAVEfmt ", 8); b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20); b.writeUInt16LE(2, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 4, 28);
  b.writeUInt16LE(4, 32); b.writeUInt16LE(16, 34); b.write("data", 36); b.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) for (let c = 0; c < 2; c++)
    b.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(chs[c][i] * 32767))), 44 + i * 4 + c * 2);
  return b;
}

for (const job of jobs) {
  const [style, progression, density = "auto", bars = "16", only, flag] = job.split(":");
  const r = await page.evaluate(async ({ style, progression, density, bars, only, flag }) => {
    const p = window.__player;
    const fl = (flag ?? "").split("/"), on = fl.find(f => f.startsWith("on=")), off = fl.find(f => f.startsWith("off="));
    const o = { density, seed: 7, ...(progression ? { progression } : {}), ...(only ? { only: only.split(",") } : {}),
      noReverb: fl.includes("dry"), raw: fl.includes("raw"), ...(fl.includes("grid") ? { humanize: false } : {}), wetOnly: fl.includes("wet"), probe: fl.includes("probe"),
      parts: { ...(on ? Object.fromEntries(on.slice(3).split("+").map(k => [k, true])) : {}),
        ...(off ? Object.fromEntries(off.slice(4).split("+").map(k => [k, false])) : {}) } };
    const { buffer, meta, failed, gr } = await p.renderOffline(style, o, +bars);
    // 壓縮量看「有在壓的時候」:95 百分位(平均會被鼓聲之間的空檔稀釋)
    const avg = a => { if (!a.length) return 0; const b = [...a].sort((x, y) => x - y); return b[Math.floor(0.05 * (b.length - 1))]; };
    const chs = [buffer.getChannelData(0), buffer.getChannelData(1)];
    let peak = 0, ss = 0, clip = 0;
    for (const c of chs) for (const x of c) { const a = Math.abs(x); if (a > peak) peak = a; ss += x * x; if (a >= 0.999) clip++; }
    return { peak, rms: Math.sqrt(ss / (2 * chs[0].length)), clip, failed, sr: buffer.sampleRate, grD: avg(gr.drums), grG: avg(gr.glue), probe: o.probe,
      bpm: meta.bpm, l: Array.from(chs[0]), r: Array.from(chs[1]) };
  }, { style, progression, density, bars, only, flag });
  const name = job.replace(/[:,/=+]/g, "_");
  writeFileSync(join(out, name + ".wav"), wav([r.l, r.r], r.sr));
  console.log(`${name.padEnd(36)} bpm ${r.bpm}  peak ${r.peak.toFixed(3)}  rms ${(20 * Math.log10(r.rms)).toFixed(1)} dBFS  clip ${r.clip}  載不到 ${r.failed}` + (r.probe ? `  鼓組壓 ${(-r.grD).toFixed(1)} dB  黏著壓 ${(-r.grG).toFixed(1)} dB` : ""));
}
console.log("route 404:", missing);
await browser.close();
server.close();
