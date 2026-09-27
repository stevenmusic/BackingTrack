/* 用 GrooVAE(Magenta,Apache 2.0;Groove MIDI Dataset CC BY 4.0)**離線**算鼓的律動範本,印成 index.html 的 `GV_TEMPLATES`。
   網頁上直接跑模型會拖垮播放(程式庫含 Tone.js + TensorFlow,量到整首 −6dB、鼓少三分之一),所以只在這裡算一次。
   需要:npm i @magenta/music@1.23.1(在 /tmp/gv)、模型檔用 curl 抓到 /tmp/gv/ck(storage.googleapis.com/magentadata/js/checkpoints/music_vae/groovae_2bar_humanize)
     node tools/realism/gv_templates.mjs */
import { chromium } from 'playwright';
import fs from 'fs';
const b = await chromium.launch(); const pg = await b.newPage();
await pg.route('http://gv.local/ck/**', r => r.fulfill({ status: 200, body: fs.readFileSync('/tmp/gv/ck/' + r.request().url().split('/ck/')[1]) }));
await pg.route('http://gv.local/', r => r.fulfill({ status: 200, contentType: 'text/html', body: '<html></html>' }));
await pg.goto('http://gv.local/');
await pg.addScriptTag({ content: fs.readFileSync('/tmp/gv/node_modules/@magenta/music/dist/magentamusic.js', 'utf8') });
const T = await pg.evaluate(async () => {
  const m = new mm.MusicVAE('http://gv.local/ck'); await m.initialize();
  const qpm = 110, spq = 4, step = 60 / qpm / spq, out = [];
  // 大鼓四種型(City Pop 的 KICK_CELLS 常見的位置);hi-hat 一律十六分;小鼓 2、4
  for (const kicks of [[0, 7, 10], [0, 3, 8, 11, 14], [0, 6, 8, 14], [0, 10, 14]]) {
    const notes = [];
    for (let q = 0; q < 32; q++) {
      const s = q % 16, add = p => notes.push({ pitch: p, quantizedStartStep: q, quantizedEndStep: q + 1, isDrum: true, velocity: 80 });
      add(42); if (kicks.includes(s)) add(36); if (s === 4 || s === 12) add(38);
    }
    const seq = { notes, quantizationInfo: { stepsPerQuarter: spq }, totalQuantizedSteps: 32, tempos: [{ time: 0, qpm }] };
    const z = await m.encode([seq]);
    for (const temp of [0.01, 0.3]) {
      const r = (await m.decode(z, temp, undefined, spq, qpm))[0];
      const t = { k: {}, s: {}, h: {} };
      for (const n of r.notes) {
        const c = n.pitch === 36 ? 'k' : n.pitch === 38 ? 's' : n.pitch === 42 ? 'h' : null;
        const g = Math.round(n.startTime / step);
        if (c && g >= 0 && g < 32) t[c][g] = [Math.round((n.startTime - g * step) * 1000), n.velocity];
      }
      out.push(t);
    }
  }
  return out; });
await b.close();
console.log('const GV_TEMPLATES = ' + JSON.stringify(T) + ';');
