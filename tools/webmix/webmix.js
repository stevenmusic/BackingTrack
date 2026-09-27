/* webmix.js — 瀏覽器裡的完整混音 + 母帶鏈(Web Audio API,無相依、單檔)
   來源:BackingTrack(index.html)實際在用、量過的那一套。用法、每一站做什麼、數字怎麼挑:docs/WEB_MIXING.md

   用法:
     import { createWebMix } from "./webmix.js";      // ES module(<script type="module">);import 之後也掛在 window.WebMix
     const ctx = new AudioContext();
     const mix = await createWebMix(ctx, { lufs: -14, truePeak: true, monoBelow: 120 });
     const drums = mix.bus("drums", { hp: 45, comp: [-18, 3, 0.01, 0.12], par: [1, -30, 8], sat: 0.35, send: 0.05 });
     someSource.connect(drums.input);
     mix.set({ master: { multiband: { lo: [-18, 2, 0.03, 0.2], mid: [-20, 1.5, 0.02, 0.15], hi: [-24, 2, 0.005, 0.1] } } });
     mix.reset();                                       // 換歌 / 重新播放時:響度重新量

   **沒寫的欄位 = 透明**(那一站被繞過或是 0dB),所以可以一站一站開。
   注意:DynamicsCompressor 自帶 6ms 延遲——開了串聯壓縮的 bus 會晚 6ms(要對齊就把那一軌提早排 `COMP_LATENCY`)。 */
"use strict";

/* ─────────── 以下由 build.py 從 index.html 抽出來,不要直接改 ─────────── */

function mulberry32(seed){
  let a = seed | 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildImpulseResponse(ctx, seconds, decayPow){
  const rate = ctx.sampleRate;
  const len = Math.max(1, Math.floor(rate * seconds));
  const ir = ctx.createBuffer(2, len, rate);
  for (let ch = 0; ch < 2; ch++) {
    const d = ir.getChannelData(ch);
    /* **左右兩聲道要是不相關的兩份雜訊**(種子不一樣),那是殘響「有寬度」的來源;
       同一份給兩邊的話整片殘響會塌回正中間,聽起來是「加了效果」不是「在一個空間裡」 */
    const rnd = mulberry32(ch ? 0x5bf03635 : 0x9e3779b9);
    let lp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / len;
      const env = Math.pow(1 - t, decayPow);
      const noise = (rnd() * 2 - 1) * env;
      const a = 0.42 * (1 - t * 0.8) + 0.02;
      lp += a * (noise - lp);
      d[i] = lp;
    }
    const early = [0.011, 0.019, 0.031, 0.044, 0.058];
    for (let k = 0; k < early.length; k++) {
      const idx = Math.floor(rate * (early[k] + (ch ? 0.0031 : 0)));
      if (idx < len) d[idx] += (0.5 - k * 0.07) * (ch ? -1 : 1) * 0.6;
    }
  }
  return ir;
}

function softCurve(t, top){
  const n = 4096, c = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1, a = Math.abs(x);
    const y = a <= t ? a : t + (top - t) * Math.tanh((a - t) / (top - t));
    c[i] = x < 0 ? -y : y;
  }
  return c;
}

function shelf(c, type, hz){
  const f = c.createBiquadFilter();
  f.type = type; f.frequency.value = hz; f.gain.value = 0;
  return f;
}

function makeChorus(c){
  const input = c.createGain(), output = c.createGain(), wet = c.createGain();
  wet.gain.value = 0;
  input.connect(output);
  const lfo = c.createOscillator();
  lfo.frequency.value = 0.5;
  for (const side of [-1, 1]) {
    const d = c.createDelay(0.05);
    d.delayTime.value = side < 0 ? 0.0071 : 0.0093;   // 兩邊不一樣長,才不會對稱地塌回中間
    const depth = c.createGain();
    /* 深度決定**音高晃多少**:音高偏移 = 深度 × 2π × 速率。
       第一版 0.0017 s × 0.6Hz = **±11 音分**,那已經是走音(被回報「音色更奇怪了」);
       CE-1 / Dimension D 只晃 2–3 音分。0.0005 × 0.5Hz = ±2.7 音分 */
    depth.gain.value = 0.0005 * side;
    lfo.connect(depth); depth.connect(d.delayTime);
    const pan = c.createStereoPanner ? c.createStereoPanner() : null;
    input.connect(d);
    if (pan) { pan.pan.value = side * 0.9; d.connect(pan); pan.connect(wet); }
    else d.connect(wet);
  }
  wet.connect(output);
  lfo.start();
  return { input, output, wet };
}

const LIMITER_SRC = `
class LookaheadLimiter extends AudioWorkletProcessor {
  /* \`tp\` = 1:偵測**取樣與取樣之間的真實峰值**(True Peak,ITU-R BS.1770 的做法:4× 內插)。
     數位峰值 0.85 的兩個取樣之間,類比重建後可能衝到 0.9 以上(手機喇叭 / 藍牙轉碼時會破)。
     這裡用 Lanczos-4(視窗 sinc,8 個取樣)在每一對取樣之間內插 3 個點(= 4× 升取樣),取最大值當那一格的峰值。
     比真正的輸出晚 4 個取樣才看到,限幅器本來就看前 5ms(240 取樣),來得及 */
  static get parameterDescriptors(){ return [{ name: "tp", defaultValue: 0, minValue: 0, maxValue: 1, automationRate: "k-rate" }]; }
  constructor(o){
    super();
    const p = (o && o.processorOptions) || {};
    this.N = Math.max(8, Math.round((p.lookahead || 0.005) * sampleRate));
    this.ceil = p.ceiling || 0.7;
    this.rel = Math.exp(-1 / ((p.release || 0.08) * sampleRate));
    this.r = new Float32Array(this.N + 1).fill(1); this.ri = 0;
    this.box = new Float32Array(this.N).fill(1); this.bi = 0; this.bsum = this.N;
    this.dl = [new Float32Array(this.N), new Float32Array(this.N)]; this.di = 0;
    this.g = 1; this.minG = 1; this.cnt = 0;
    this.h = [new Float32Array(8), new Float32Array(8)];
    const L = x => x === 0 ? 1 : Math.abs(x) >= 4 ? 0 : 4 * Math.sin(Math.PI * x) * Math.sin(Math.PI * x / 4) / (Math.PI * Math.PI * x * x);
    this.w = [0.25, 0.5, 0.75].map(t => Array.from({ length: 8 }, (_, j) => L(t + 3 - j)));
  }
  process(inputs, outputs, params){
    const inp = inputs[0], out = outputs[0];
    const tp = params && params.tp && params.tp[0] > 0.5;
    if (!out || !out.length) return true;
    const L = inp && inp[0], R = inp && (inp[1] || inp[0]);
    const n = out[0].length, N = this.N;
    for (let i = 0; i < n; i++) {
      const xl = L ? L[i] : 0, xr = R ? R[i] : 0;
      let a = Math.max(Math.abs(xl), Math.abs(xr));
      if (tp) for (let c = 0; c < 2; c++) {
        const h = this.h[c]; h.copyWithin(0, 1); h[7] = c ? xr : xl;
        for (let k = 0; k < 3; k++) {
          const w = this.w[k]; let v = 0;
          for (let j = 0; j < 8; j++) v += w[j] * h[j];
          if (Math.abs(v) > a) a = Math.abs(v);
        }
      }
      this.r[this.ri] = a > this.ceil ? this.ceil / a : 1;
      this.ri = (this.ri + 1) % (N + 1);
      let m = 1; const rr = this.r;
      for (let k = 0; k <= N; k++) if (rr[k] < m) m = rr[k];
      this.bsum += m - this.box[this.bi]; this.box[this.bi] = m; this.bi = (this.bi + 1) % N;
      const gb = Math.min(1, this.bsum / N);
      this.g = gb < this.g ? gb : gb - (gb - this.g) * this.rel;
      const ol = this.dl[0][this.di], or = this.dl[1][this.di];
      this.dl[0][this.di] = xl; this.dl[1][this.di] = xr; this.di = (this.di + 1) % N;
      out[0][i] = ol * this.g;
      if (out[1]) out[1][i] = or * this.g;
      if (this.g < this.minG) this.minG = this.g;
    }
    if ((this.cnt += n) >= sampleRate / 2) {
      this.bsum = 0; for (let k = 0; k < N; k++) this.bsum += this.box[k];   // 浮點累加誤差歸零
      this.port.postMessage(this.minG); this.minG = 1; this.cnt = 0;
    }
    return true;
  }
}
registerProcessor("lookahead-limiter", LookaheadLimiter);

/* ── 響度對齊(Loudness Normalization,ITU-R BS.1770-4 / EBU R128)──────────────
   串流平台(Spotify / YouTube / Apple)的做法:量**整首的整合響度**(LUFS),整首乘一個固定增益到目標。
   這裡是播放中做,照標準一步一步:
   1. K 加權:高頻架子(+4dB,1.5k 起)→ 高通 38Hz
   2. 400ms 一塊、每 100ms 一塊(75% 重疊),每塊算 ΣL,R 均方
   3. 絕對門檻 −70 LUFS;相對門檻 = 過了絕對門檻的平均 −10 LU(安靜的段落不算,所以 pad 段不會被拉大)
   4. 整合響度 = −0.691 + 10·log10(剩下那些塊的平均)
   增益**慢慢**往 目標 − 整合響度 走(每秒最多 \`rate\` dB),量到 2 秒以上才開始動,上下限 \`maxUp\` / \`maxDown\`。
   量的是**進來的**訊號(不是自己調過的),不會自己追自己。
   port 收 { reset, gdb }:換歌(按播放)時清掉量過的塊,增益從 gdb 出發 */
class LoudnessNorm extends AudioWorkletProcessor {
  static get parameterDescriptors(){ return [
    { name: "on", defaultValue: 0, automationRate: "k-rate" },
    { name: "target", defaultValue: -20, automationRate: "k-rate" },
    { name: "rate", defaultValue: 1, automationRate: "k-rate" },
    { name: "maxUp", defaultValue: 6, automationRate: "k-rate" },
    { name: "maxDown", defaultValue: 12, automationRate: "k-rate" }]; }
  constructor(){
    super();
    const fs = sampleRate;
    const shelf = (() => { const A = Math.pow(10, 4 / 40), w = 2 * Math.PI * 1500 / fs, cs = Math.cos(w), al = Math.sin(w) / (2 * Math.SQRT1_2), sa = 2 * Math.sqrt(A) * al;
      const a0 = (A + 1) - (A - 1) * cs + sa;
      return [A * ((A + 1) + (A - 1) * cs + sa) / a0, -2 * A * ((A - 1) + (A + 1) * cs) / a0, A * ((A + 1) + (A - 1) * cs - sa) / a0,
              2 * ((A - 1) - (A + 1) * cs) / a0, ((A + 1) - (A - 1) * cs - sa) / a0]; })();
    const hp = (() => { const w = 2 * Math.PI * 38 / fs, cs = Math.cos(w), al = Math.sin(w) / (2 * 0.5), a0 = 1 + al;
      return [(1 + cs) / 2 / a0, -(1 + cs) / a0, (1 + cs) / 2 / a0, -2 * cs / a0, (1 - al) / a0]; })();
    this.f = [shelf, hp];
    this.z = [0, 1].map(() => [new Float64Array(4), new Float64Array(4)]);   // [聲道][級]:x1 x2 y1 y2
    this.hop = Math.round(fs * 0.1); this.sub = new Float64Array(4); this.si = 0; this.acc = 0; this.n = 0;
    this.blocks = []; this.gdb = 0; this.cnt = 0;
    this.port.onmessage = e => { const d = e.data || {};
      if (d.reset) { this.blocks = []; this.sub.fill(0); this.si = 0; this.acc = 0; this.n = 0; this.gdb = d.gdb || 0; } };
  }
  bq(c, s, x){ const b = this.f[s], z = this.z[c][s];
    const y = b[0] * x + b[1] * z[0] + b[2] * z[1] - b[3] * z[2] - b[4] * z[3];
    z[1] = z[0]; z[0] = x; z[3] = z[2]; z[2] = y; return y; }
  integrated(){
    const B = this.blocks.filter(e => e > 1.17e-7);                 // −70 LUFS
    if (B.length < 20) return null;                                   // 量不到 2 秒不算
    const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
    const rel = mean(B) * 0.1;                                        // −10 LU
    const G = B.filter(e => e > rel);
    return G.length ? -0.691 + 10 * Math.log10(mean(G)) : null;
  }
  process(inputs, outputs, P){
    const inp = inputs[0], out = outputs[0];
    if (!out || !out.length) return true;
    const L = inp && inp[0], R = inp && (inp[1] || inp[0]), n = out[0].length;
    const on = P.on[0] > 0.5;
    let done = false;
    for (let i = 0; i < n; i++) {
      const kl = this.bq(0, 1, this.bq(0, 0, L ? L[i] : 0)), kr = this.bq(1, 1, this.bq(1, 0, R ? R[i] : 0));
      this.acc += kl * kl + kr * kr;
      if (++this.n >= this.hop) {
        this.sub[this.si++ % 4] = this.acc / this.hop; this.acc = 0; this.n = 0;
        if (this.si >= 4) { this.blocks.push((this.sub[0] + this.sub[1] + this.sub[2] + this.sub[3]) / 4); done = true; }
        if (this.blocks.length > 6000) this.blocks.shift();          // 最多記 10 分鐘
      }
    }
    const g0 = Math.pow(10, this.gdb / 20);
    if (on && done) {
      const lufs = this.integrated();
      if (lufs != null) {
        const want = Math.max(-P.maxDown[0], Math.min(P.maxUp[0], P.target[0] - lufs));
        const step = P.rate[0] * 0.1;
        this.gdb += Math.max(-step, Math.min(step, want - this.gdb));
      }
    } else if (!on && this.gdb !== 0) {                               // 關掉:每秒 6dB 慢慢回 0,不要一下跳
      const step = 6 * n / sampleRate; this.gdb = Math.abs(this.gdb) <= step ? 0 : this.gdb - Math.sign(this.gdb) * step;
    }
    const g1 = Math.pow(10, this.gdb / 20);
    for (let i = 0; i < n; i++) {
      const g = g0 + (g1 - g0) * (i + 1) / n;
      out[0][i] = (L ? L[i] : 0) * g;
      if (out[1]) out[1][i] = (R ? R[i] : 0) * g;
    }
    if ((this.cnt += n) >= sampleRate / 2) { this.port.postMessage(this.gdb); this.cnt = 0; }
    return true;
  }
}
registerProcessor("loudness-norm", LoudnessNorm);`;

/* ══ 混音 / 母帶的積木(每一顆都是 { input, output, set(…) },沒開 = 一條線直接過)══════════
   這幾顆沒有用到這個 app 的任何東西,整段可以直接搬到別的 Web Audio 專案(`docs/WEB_MIXING.md`)。
   **瀏覽器的 DynamicsCompressor 自帶 6ms 的 lookahead 延遲**:
   - 「串聯」(整條換成壓過的)→ 用開關切,不開就繞過;開了的那一條在 `pocket` 扣回來
   - 「並聯」(乾的 + 壓過的混在一起)→ 乾的那一路**一定要補同樣的 6ms**,不然兩路差 6ms 會梳狀濾波 / 變兩下 */
const COMP_LATENCY = 0.006;
/* **瀏覽器的 DynamicsCompressor 會自己偷補增益**(WebKit / Chromium / Firefox 同一份程式碼:
   補 (1 / 0dBFS 過壓縮曲線後的增益)^0.6)。−30dB、2:1 會自己大 8dB——門檻越低、比例越高,
   沒被壓到的小聲音反而越大聲。三段壓縮的高頻段因此被推亮 3–4dB(踩過)。
   這裡照原始碼(DynamicsCompressorKernel 的 kneeCurve / kAtSlope / saturate)算出那個 dB,積木裡扣掉,
   讓 makeup 只剩自己寫的那個數字。在 OfflineAudioContext 量過 8 組(門檻、比例、knee),誤差 < 0.01dB */
function compAutoMakeupDb(T, R, knee){
  if (!(R > 1) || T >= 0) return 0;
  const db2 = d => Math.pow(10, d / 20), l2d = x => 20 * Math.log10(x);
  const lt = db2(T);
  const curve = (x, k) => x < lt ? x : lt + (1 - Math.exp(-k * (x - lt))) / k;
  const slopeAt = (x, k) => { if (x < lt) return 1; const x2 = x * 1.001;
    return (l2d(curve(x2, k)) - l2d(curve(x, k))) / (l2d(x2) - l2d(x)); };
  const kx = db2(T + knee);
  let lo = 0.1, hi = 10000, k = 5;
  for (let i = 0; i < 15; i++) { if (slopeAt(kx, k) < 1 / R) hi = k; else lo = k; k = Math.sqrt(lo * hi); }
  const yk = l2d(curve(kx, k));
  const sat = x => x < kx ? curve(x, k) : db2(yk + (l2d(x) - (T + knee)) / R);
  return -0.6 * l2d(sat(1));
}
/* 壓縮器的延遲是 preDelay × 取樣率**截成整數**(44.1k = 264 個取樣,不是 264.6)。
   DelayNode 遇到小數延遲會線性內插 = 多過一顆低通(44.1k 時 10kHz −2.3dB),所以補償一律用整數取樣 */
const compLatency = (c) => Math.floor(COMP_LATENCY * c.sampleRate) / c.sampleRate;
const unMakeup = (T, R, knee) => Math.pow(10, -compAutoMakeupDb(T, R, knee) / 20);
function mkSwitch(ctx){                     // 乾 / 處理過 二選一(交叉淡化 20ms,不會爆音)
  const input = ctx.createGain(), output = ctx.createGain(), dry = ctx.createGain(), wet = ctx.createGain();
  wet.gain.value = 0; input.connect(dry); dry.connect(output); wet.connect(output);
  const set = (on) => { const t = ctx.currentTime;
    dry.gain.cancelScheduledValues(t); wet.gain.cancelScheduledValues(t);
    if (t < 0.05) { dry.gain.setValueAtTime(on ? 0 : 1, t); wet.gain.setValueAtTime(on ? 1 : 0, t); return; }   // 剛建好還沒出聲:直接切
    dry.gain.setTargetAtTime(on ? 0 : 1, t, 0.02); wet.gain.setTargetAtTime(on ? 1 : 0, t, 0.02); };
  return { input, output, wet, set };
}
/* 串聯壓縮(補償增益自己補):set(門檻 dB, 比例, 起音秒, 放開秒, 補償倍數);門檻 undefined = 繞過 */
function mkComp(ctx, knee){
  const sw = mkSwitch(ctx), c = ctx.createDynamicsCompressor(), mk = ctx.createGain();
  c.knee.value = knee == null ? 6 : knee;
  sw.input.connect(c); c.connect(mk); mk.connect(sw.wet);
  return { input: sw.input, output: sw.output, node: c,
    set(thr, ratio, att, rel, makeup){
      const on = thr != null; sw.set(on);
      c.threshold.value = on ? thr : 0; c.ratio.value = ratio || 3;
      c.attack.value = att || 0.01; c.release.value = rel || 0.15;
      mk.gain.value = on ? (makeup || 1) * unMakeup(thr, ratio || 3, c.knee.value) : 1; } };
}
/* 飽和(類比磁帶 / 變壓器的那種圓):y = tanh(k·x)/k,原點斜率 = 1(小聲的地方音量不變,大聲的地方才被磨圓)。
   WaveShaper 的曲線只管 −1～1,超出去會被硬削——所以前面先 ÷R、後面再 ×R,讓它撐到 ±R(R = 4 → +12dBFS)。
   **不開超取樣**:WaveShaper 的 2× 超取樣自帶 128 個取樣(2.7ms)延遲,鼓與貝斯會比別人晚;
   k 這麼小的時候泛音很低,折疊失真聽不到。k = 0 → 曲線設 null(WaveShaper 沒曲線 = 原封不動) */
function mkSat(ctx, R){
  R = R || 4;
  const input = ctx.createGain(), sh = ctx.createWaveShaper(), output = ctx.createGain();
  input.gain.value = 1 / R; output.gain.value = R; sh.oversample = "none";
  input.connect(sh); sh.connect(output);
  let last = -1;
  return { input, output, set(k){
    k = k || 0; if (k === last) return; last = k;
    if (!k) { sh.curve = null; return; }
    const n = 4096, c = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = (i / (n - 1) * 2 - 1) * R; c[i] = Math.tanh(k * x) / k / R; }
    sh.curve = c; } };
}
/* 並聯壓縮(紐約壓縮):乾的原樣 + 壓得很重的那一份墊在下面 → 音頭不變、尾巴與房間變厚。
   壓扁的那份可以過一顆低通(`lp` Hz,沒寫 = 不過):鈸被壓扁之後尾巴一直在,2–5k 會變多(backing track 要讓出來),
   只拿它的鼓身。set(量, 門檻, 比例, 低通);量 0 = 關(乾的也不延遲) */
function mkParallel(ctx){
  const input = ctx.createGain(), output = ctx.createGain();
  const direct = ctx.createGain(), dly = ctx.createDelay(0.05), dlyG = ctx.createGain();
  const c = ctx.createDynamicsCompressor(), send = ctx.createGain(), lpSw = mkSwitch(ctx), lpF = ctx.createBiquadFilter();
  lpF.type = "lowpass"; lpF.Q.value = BUTTER_Q_DB; lpSw.input.connect(lpF); lpF.connect(lpSw.wet);
  dly.delayTime.value = compLatency(ctx); dlyG.gain.value = 0; send.gain.value = 0;
  c.knee.value = 0; c.attack.value = 0.003; c.release.value = 0.08;
  input.connect(direct); direct.connect(output);
  input.connect(dly); dly.connect(dlyG); dlyG.connect(output);
  input.connect(c); c.connect(lpSw.input); lpSw.output.connect(send); send.connect(output);
  return { input, output, set(amt, thr, ratio, lp){
    lpSw.set(lp > 0); if (lp > 0) lpF.frequency.value = lp;
    const on = amt > 0;
    thr = thr == null ? -30 : thr; ratio = ratio || 8;
    direct.gain.value = on ? 0 : 1; dlyG.gain.value = on ? 1 : 0; send.gain.value = on ? amt * unMakeup(thr, ratio, 0) : 0;
    c.threshold.value = thr; c.ratio.value = ratio; } };
}
/* Linkwitz-Riley 四階(兩顆二階 Butterworth 串起來):低 + 高 加起來相位平的,切點不會凹也不會凸。
   **Web Audio 的 lowpass / highpass 的 Q 單位是 dB**(不是線性):Butterworth 的 0.707 要寫 −3.01dB,
   寫成 0.707 會變成線性 1.085,兩段加回來在切點凸 6dB(踩過:三段壓縮 250Hz、4kHz 各多 6dB) */
const BUTTER_Q_DB = 20 * Math.log10(Math.SQRT1_2);
function lr4(ctx, type, hz){
  const a = ctx.createBiquadFilter(), b = ctx.createBiquadFilter();
  [a, b].forEach(f => { f.type = type; f.frequency.value = hz; f.Q.value = BUTTER_Q_DB; });
  a.connect(b); return { input: a, output: b };
}
/* 母帶三段壓縮(200Hz / 3kHz 切,LR4):低頻、中頻、高頻各自一顆壓縮器,
   一段太滿時只壓那一段(大鼓一下不會把 hi-hat 一起壓下去)。
   低頻那一段要多過一顆 3k 的全通(LR4 的低 + 高 = 同頻的二階全通,Q 0.707),三段加回來相位才對得上。
   三段都經過壓縮器 → 延遲一樣,整條晚 6ms(整首一起晚,聽不出來)。
   set(null) = 繞過;set({ lo: [門檻, 比例, 起音, 放開], mid: …, hi: … }) */
function mkMultiband(ctx, f1, f2){
  f1 = f1 || 200; f2 = f2 || 3000;
  const sw = mkSwitch(ctx), sum = ctx.createGain();
  const lo = lr4(ctx, "lowpass", f1), rest = lr4(ctx, "highpass", f1);
  const mid = lr4(ctx, "lowpass", f2), hi = lr4(ctx, "highpass", f2);
  const ap = ctx.createBiquadFilter(); ap.type = "allpass"; ap.frequency.value = f2; ap.Q.value = Math.SQRT1_2;
  const comps = [0, 1, 2].map(() => { const c = ctx.createDynamicsCompressor(); c.knee.value = 6; c.threshold.value = 0; return c; });
  const trims = comps.map(c => { const g = ctx.createGain(); c.connect(g); g.connect(sum); return g; });
  sw.input.connect(lo.input); lo.output.connect(ap); ap.connect(comps[0]);
  sw.input.connect(rest.input); rest.output.connect(mid.input); rest.output.connect(hi.input);
  mid.output.connect(comps[1]); hi.output.connect(comps[2]);
  sum.connect(sw.wet);
  return { input: sw.input, output: sw.output, set(cfg){
    sw.set(!!cfg);
    ["lo", "mid", "hi"].forEach((k, i) => { const v = (cfg && cfg[k]) || [0, 1, 0.01, 0.15], c = comps[i];
      c.threshold.value = v[0]; c.ratio.value = v[1]; c.attack.value = v[2]; c.release.value = v[3];
      trims[i].gain.value = unMakeup(v[0], v[1], 6); });
    sum.gain.value = cfg && cfg.makeup || 1; } };
}
/* 低頻收成單聲道(M/S):Side 只留 hz 以上(LR4 高通),Mid 過同頻的全通讓相位跟 Side 對齊。
   超低頻左右不一樣 = 喇叭互相抵、黑膠刻不出來、手機單聲道一加就少一截 */
function mkMonoLow(ctx){
  const sw = mkSwitch(ctx);
  const sp = ctx.createChannelSplitter(2), mg = ctx.createChannelMerger(2);
  const mono = () => { const g = ctx.createGain(); g.channelCount = 1; g.channelCountMode = "explicit"; g.channelInterpretation = "discrete"; return g; };
  const M = mono(), S = mono(), lM = mono(), rM = mono(), lS = mono(), rS = mono(), Sneg = mono();
  lM.gain.value = rM.gain.value = lS.gain.value = 0.5; rS.gain.value = -0.5; Sneg.gain.value = -1;
  const inp = ctx.createGain(); inp.channelCount = 2; inp.channelCountMode = "explicit";
  sw.input.connect(inp); inp.connect(sp);
  sp.connect(lM, 0); sp.connect(rM, 1); lM.connect(M); rM.connect(M);
  sp.connect(lS, 0); sp.connect(rS, 1); lS.connect(S); rS.connect(S);
  const ap = ctx.createBiquadFilter(); ap.type = "allpass"; ap.Q.value = Math.SQRT1_2; ap.channelCount = 1; ap.channelCountMode = "explicit";
  const hp = lr4(ctx, "highpass", 120);
  [hp.input, hp.output].forEach(f => { f.channelCount = 1; f.channelCountMode = "explicit"; });
  M.connect(ap); S.connect(hp.input);
  ap.connect(mg, 0, 0); ap.connect(mg, 0, 1);           // L = M + S、R = M − S
  hp.output.connect(mg, 0, 0); hp.output.connect(Sneg); Sneg.connect(mg, 0, 1);
  mg.connect(sw.wet);
  return { input: sw.input, output: sw.output, set(hz){
    sw.set(hz > 0);
    if (hz > 0) { ap.frequency.value = hz; hp.input.frequency.value = hp.output.frequency.value = hz; } } };
}

/* ─────────── 抽出來的到這裡 ─────────── */

/* ══ 組裝:bus 與母帶 ══════════════════════════════════════════════════════
   訊號流(跟 BackingTrack 一樣):
   每條 bus:輸入 → 高通 → EQ(鐘形)→ 串聯壓縮 → 並聯壓縮 → 飽和 → 高頻架子 → chorus → 寬度 →(母帶)
                                    └ 殘響送(post-EQ)→ 殘響(預延遲 18ms → 卷積 → 低通 → 高通)→ 母帶
   母帶:輸入 → 高通 24Hz → 中頻鐘形 → 高頻架子 → 三段壓縮 → 低頻單聲道 → 黏著壓縮 → 飽和
         → 響度對齊(LUFS)→ 輸出增益 → True Peak 限幅器(看前 5ms)→ 軟削波(保險)→ 喇叭 */
async function createWebMix(ctx, opts){
  opts = opts || {};
  const IN = opts.inGain || 0.75, OUT = opts.outGain || 2.35, CEIL = opts.ceiling || 0.85;
  const input = ctx.createGain(); input.gain.value = IN;
  const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 24; hp.Q.value = 0.5;
  const mid = ctx.createBiquadFilter(); mid.type = "peaking"; mid.Q.value = 0.6; mid.frequency.value = 400; mid.gain.value = 0;
  const air = shelf(ctx, "highshelf", 5000);
  const mb = mkMultiband(ctx, 200, 3000), mono = mkMonoLow(ctx);
  const glue = ctx.createDynamicsCompressor();
  glue.threshold.value = -16; glue.knee.value = 8; glue.ratio.value = 2; glue.attack.value = 0.03; glue.release.value = 0.25;
  const glueTrim = ctx.createGain(); glueTrim.gain.value = 1;
  const sat = ctx.createWaveShaper();
  sat.curve = (() => { const n = 4096, c = new Float32Array(n), drive = 1.25, norm = 1 / (1 - 1 / 3);
    for (let i = 0; i < n; i++) { let x = ((i / (n - 1)) * 2 - 1) * drive; if (x > 1) x = 1; else if (x < -1) x = -1;
      c[i] = (x - x * x * x / 3) * norm / drive; } return c; })();
  const out = ctx.createGain(); out.gain.value = OUT;
  const clip = ctx.createWaveShaper(); clip.curve = softCurve(0.9, 0.98);
  input.connect(hp); hp.connect(mid); mid.connect(air); air.connect(mb.input); mb.output.connect(mono.input);
  mono.output.connect(glue); glue.connect(glueTrim); glueTrim.connect(sat);
  clip.connect(opts.destination || ctx.destination);

  /* 殘響(共用一個空間:所有 bus 送同一顆,才像同一個房間) */
  const rev = ctx.createGain(), pre = ctx.createDelay(0.2), conv = ctx.createConvolver(), revLp = ctx.createBiquadFilter(), revHp = ctx.createBiquadFilter(), revWet = ctx.createGain();
  pre.delayTime.value = 0.018; conv.buffer = buildImpulseResponse(ctx, opts.reverbSeconds || 2.0, 2.4);
  revLp.type = "lowpass"; revLp.frequency.value = 20000; revLp.Q.value = 0.5;
  revHp.type = "highpass"; revHp.frequency.value = 10; revHp.Q.value = BUTTER_Q_DB; revWet.gain.value = 0.26;
  const revHpSw = mkSwitch(ctx); revHpSw.input.connect(revHp); revHp.connect(revHpSw.wet);
  rev.connect(pre); pre.connect(conv); conv.connect(revLp); revLp.connect(revHpSw.input); revHpSw.output.connect(revWet); revWet.connect(input);

  /* worklet(True Peak 限幅 + 響度對齊);載不到就退回內建壓縮器當限幅(沒有響度對齊) */
  let limiter = null, agc = null, agcDb = 0, grDb = 0;
  try {
    const url = URL.createObjectURL(new Blob([LIMITER_SRC], { type: "application/javascript" }));
    await ctx.audioWorklet.addModule(url); URL.revokeObjectURL(url);
    agc = new AudioWorkletNode(ctx, "loudness-norm", { outputChannelCount: [2] });
    limiter = new AudioWorkletNode(ctx, "lookahead-limiter", { outputChannelCount: [2],
      processorOptions: { lookahead: 0.005, ceiling: CEIL, release: 0.08 } });
    agc.port.onmessage = e => { agcDb = e.data; };
    limiter.port.onmessage = e => { grDb = 20 * Math.log10(e.data || 1); };   // 限幅器回報的是這半秒最小的增益(倍數)
    sat.connect(agc); agc.connect(out); out.connect(limiter); limiter.connect(clip);
  } catch (e) {
    try { sat.disconnect(); out.disconnect(); } catch (_) {}
    limiter = agc = null; console.warn("webmix: AudioWorklet 載不到,退回內建壓縮器當限幅(沒有響度對齊 / True Peak)", e);
    const lim = ctx.createDynamicsCompressor();
    lim.threshold.value = -1; lim.knee.value = 0; lim.ratio.value = 20; lim.attack.value = 0.001; lim.release.value = 0.1;
    sat.connect(out); out.connect(lim); lim.connect(clip);
  }

  const buses = {};
  function bus(name, b){
    const x = {};
    x.input = ctx.createGain();
    x.hp = ctx.createBiquadFilter(); x.hp.type = "highpass"; x.hp.Q.value = 0.7;
    x.eq = ctx.createBiquadFilter(); x.eq.type = "peaking";
    x.comp = mkComp(ctx, 6); x.par = mkParallel(ctx); x.sat = mkSat(ctx, 4);
    x.air = shelf(ctx, "highshelf", 6500); x.chorus = makeChorus(ctx); x.send = ctx.createGain();
    x.width = (() => { const sp = ctx.createChannelSplitter(2), mg = ctx.createChannelMerger(2), inp = ctx.createGain(), g = [0, 1, 2, 3].map(() => ctx.createGain());
      inp.channelCountMode = "explicit"; inp.channelCount = 2; inp.connect(sp);
      sp.connect(g[0], 0); g[0].connect(mg, 0, 0); sp.connect(g[1], 1); g[1].connect(mg, 0, 0);
      sp.connect(g[2], 1); g[2].connect(mg, 0, 1); sp.connect(g[3], 0); g[3].connect(mg, 0, 1);
      return { input: inp, output: mg, set(w){ g[0].gain.value = g[2].gain.value = (1 + w) / 2; g[1].gain.value = g[3].gain.value = (1 - w) / 2; } }; })();
    x.input.connect(x.hp); x.hp.connect(x.eq); x.eq.connect(x.comp.input); x.comp.output.connect(x.par.input);
    x.par.output.connect(x.sat.input); x.sat.output.connect(x.air); x.air.connect(x.chorus.input);
    x.chorus.output.connect(x.width.input); x.width.output.connect(input);
    x.eq.connect(x.send); x.send.connect(rev);
    /* 欄位(全部可省略 = 透明):
       level 倍數、hp Hz、eq [Hz, dB, Q]、comp [門檻, 比例, 起音, 放開, 補償倍數]、par [量, 門檻, 比例, 低通 Hz]、
       sat k(0.2–0.6 = 輕)、air [Hz, dB]、chorus 0–1、width 0(單聲道)–1(原樣)、send 殘響送 */
    x.set = (c) => { c = c || {};
      x.input.gain.value = c.level == null ? 1 : c.level;
      x.hp.frequency.value = c.hp || 20;
      const eq = c.eq || [1000, 0, 1]; x.eq.frequency.value = eq[0]; x.eq.gain.value = eq[1]; x.eq.Q.value = eq[2] || 1;
      const cp = c.comp || []; x.comp.set(cp[0], cp[1], cp[2], cp[3], cp[4]);
      const pr = c.par || [0]; x.par.set(pr[0], pr[1], pr[2], pr[3]);
      x.sat.set(c.sat || 0);
      const a = c.air || [6500, 0]; x.air.frequency.value = a[0]; x.air.gain.value = a[1];
      x.chorus.wet.gain.value = c.chorus || 0; x.width.set(c.width == null ? 1 : c.width);
      x.send.gain.value = c.send || 0; };
    x.set(b); buses[name] = x; return x;
  }

  /* 母帶欄位(全部可省略 = 透明 / 預設):
     midEq [Hz, dB]、airEq [Hz, dB]、multiband { lo, mid, hi: [門檻, 比例, 起音, 放開], makeup }、monoBelow Hz、
     lufs 目標(例:−14)、truePeak true/false、reverb { lp, hp, level } */
  function set(cfg){
    cfg = cfg || {}; const m = cfg.master || cfg;
    const me = m.midEq || [400, 0]; mid.frequency.value = me[0]; mid.gain.value = me[1];
    const ae = m.airEq || [5000, 0]; air.frequency.value = ae[0]; air.gain.value = ae[1];
    mb.set(m.multiband || null); mono.set(m.monoBelow || 0);
    const r = m.reverb || {}; revLp.frequency.value = r.lp || 20000; revHpSw.set(r.hp > 0); if (r.hp > 0) revHp.frequency.value = r.hp; revWet.gain.value = r.level == null ? 0.26 : r.level;
    if (limiter) limiter.parameters.get("tp").value = m.truePeak ? 1 : 0;
    if (agc) { const P = agc.parameters; P.get("on").value = m.lufs != null ? 1 : 0;
      if (m.lufs != null) P.get("target").value = m.lufs - 20 * Math.log10(out.gain.value); }
    if (cfg.buses) for (const k in cfg.buses) (buses[k] || bus(k)).set(cfg.buses[k]);
  }
  set(opts);
  return { input, reverb: rev, bus, buses, set,
    reset(startDb){ if (agc) agc.port.postMessage({ reset: true, gdb: startDb || 0 }); },
    meter(){ return { worklet: !!limiter, agcGainDb: agcDb, limiterReductionDb: grDb }; },
    COMP_LATENCY: compLatency(ctx) };
}

const WebMix = { createWebMix, mkComp, mkSat, mkParallel, mkMultiband, mkMonoLow, lr4, compAutoMakeupDb, compLatency, makeChorus, buildImpulseResponse, COMP_LATENCY, LIMITER_SRC };
if (typeof window !== "undefined") window.WebMix = WebMix;
export { createWebMix, mkComp, mkSat, mkParallel, mkMultiband, mkMonoLow, lr4, compAutoMakeupDb, compLatency, makeChorus, buildImpulseResponse, COMP_LATENCY, LIMITER_SRC };
export default WebMix;
