// 播放器:engine.render() 的事件 → Sampler。排程一律用 AudioContext.currentTime 提前約 0.2 秒排,
// setInterval 只負責「來看一下」。混音只做到「聽得清楚、不削波」,母帶之後再做。
import { render, resolveStyle, mulberry32, progressionBars } from "./engine.mjs";
import { Sampler } from "./sampler.mjs";
import { makeLimiter } from "./limiter.mjs";

const LOOKAHEAD = 0.2, TICK_MS = 25, MIN_CHUNK = 64;
const BUTTER_Q_DB = -3.01; // Web Audio 的 highpass / lowpass Q 單位是 dB;Butterworth = −3.01
const gcd = (a, b) => (b ? gcd(b, a % b) : a);
/** 一段幾小節:進行長度與 16(A/B 段)的公倍數,至少 64;接縫才不會把進行或段落從頭開始 */
const chunkBarsFor = len => { const l = (len * 16) / gcd(len, 16); return l * Math.ceil(MIN_CHUNK / l); };

// 各樂器的電平校正:讓同一個力度在不同取樣庫大約一樣大(2026-10-08 分軌量 RMS 定的,見 README)
export const TRIMS = {
  piano: 0.75, rhodes: 0.45, electric_bass: 1.25, strings: 6.5, clean_guitar: 1.6,
  // 2026-10-08 新增:替代樂器跟它取代的那件同響度(BS.1770 量的);破音吉他在鋼琴下面 4 LU
  slap_bass: 1.05, upright_bass: 0.66, nylon_guitar: 0.84, di_guitar: 1,
  acoustic_kit: 1, "acoustic_kit.hat": 0.55, "acoustic_kit.openhat": 0.45, "acoustic_kit.crash": 0.45,
  "acoustic_kit.rim": 0.8, "acoustic_kit.clap": 0.7,
  electronic_kit: 0.8, "electronic_kit.hat": 0.45, "electronic_kit.openhat": 0.4, "electronic_kit.crash": 0.35,
  "electronic_kit.clap": 0.55, "electronic_kit.snare": 0.6,
};
// 每一軌:音量、左右、EQ、兩種空間的送出(room = 同一個房間的短殘響,plate = 鍵盤與弦樂的長殘響)。
// EQ 與送出量是照 tools/mix/analyze.py 的量測定的(2026-10-08:80Hz 低 7–11dB、250–500Hz 多 7–11dB、
// 鍵盤與貝斯在 159–1600Hz 互相蓋住、左右相關 0.94–0.96、殘響比乾聲低 20dB 以上),理由見 styles/README.md
const BUS = {
  drums:  { gain: 0.8,  pan: 0,     room: 0.45, plate: 0,
            eq: [["peaking", 400, -3, 1.2]] },
  kick:   { gain: 0.8,  pan: 0,     room: 0.12, plate: 0,
            eq: [["lowshelf", 60, 8], ["peaking", 350, -4, 1.4]] },
  bass:   { gain: 0.85, pan: 0,     room: 0.05, plate: 0,
            eq: [["lowshelf", 100, 6], ["peaking", 55, 4, 0.9], ["peaking", 400, -3, 1]] },
  keys:   { gain: 0.62, pan: -0.2,  room: 0.3,  plate: 0.35,
            eq: [["highpass", 120, 0.7], ["peaking", 300, -7, 0.8], ["peaking", 520, -4, 1.2], ["peaking", 3200, -2, 0.8]] },
  keys2:  { gain: 0.42, pan: 0.2,   room: 0.3,  plate: 0.35,
            eq: [["highpass", 150, 0.7], ["peaking", 350, -3, 1]] },
  pad:    { gain: 0.45, pan: 0,     room: 0.25, plate: 0.6,
            eq: [["highpass", 180, 0.7], ["peaking", 3000, -3, 0.8]] },
  guitar: { gain: 0.9,  pan: 0.45,  room: 0.35, plate: 0.1,
            eq: [["highpass", 250, 0.7]] },
};
// 鼓件左右(鼓手視角的立體聲擺位;大鼓、小鼓在中間)
const DRUM_PAN = { hat: 0.25, openhat: 0.25, crash: -0.3, htom: 0.15, ltom: -0.2, rim: 0.05, clap: 0, snare: 0 };

/**
 * 備援殘響 IR(真實房間的 IR 檔載不到時才用):固定種子的雜訊,指數衰減(RT60 = seconds),左右不同種子;
 * room 有前 20ms 的稀疏早期反射。能量正規化
 */
function impulse(ctx, seconds, seed, early = false) {
  const sr = ctx.sampleRate, n = Math.floor(sr * seconds * 1.2);
  const ir = ctx.createBuffer(2, n, sr);
  let e = 0;
  for (let ch = 0; ch < 2; ch++) {
    const r = mulberry32(seed + ch * 777), d = ir.getChannelData(ch);
    const k = Math.log(1000) / (seconds * sr); // 60dB 衰減
    for (let i = 0; i < n; i++) d[i] = (r() * 2 - 1) * Math.exp(-k * i);
    if (early) {
      d.fill(0, 0, Math.floor(0.02 * sr));
      for (let j = 0; j < 8; j++) d[Math.floor((0.003 + r() * 0.017) * sr)] += (r() < 0.5 ? -1 : 1) * (0.6 + 0.4 * r()) * 4;
    }
    for (let i = 0; i < n; i++) e += d[i] * d[i];
  }
  const g = 1 / Math.sqrt(e / 2);
  for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); for (let i = 0; i < n; i++) d[i] *= g; }
  return ir;
}
/** 卷積 IR 一律能量正規化(左右平均能量 = 1),換 IR 不會換音量 */
function normalizeIR(ctx, b) {
  let e = 0;
  for (let c = 0; c < b.numberOfChannels; c++) for (const x of b.getChannelData(c)) e += x * x;
  const g = 1 / Math.sqrt(e / b.numberOfChannels);
  const out = ctx.createBuffer(2, b.length, b.sampleRate);
  for (let c = 0; c < 2; c++) {
    const s = b.getChannelData(Math.min(c, b.numberOfChannels - 1)), d = out.getChannelData(c);
    for (let i = 0; i < s.length; i++) d[i] = s[i] * g;
  }
  return out;
}
/** 真實空間的 IR 檔(styles/ir/,tools/mix/make_ir.py 從 MIT 授權的 IR 庫做的);整頁共用 */
const IR_CACHE = new Map();
function loadIR(ctx, file) {
  if (!IR_CACHE.has(file)) IR_CACHE.set(file, fetch(new URL("./" + file, import.meta.url))
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer(); })
    .then(ab => ctx.decodeAudioData(ab))
    .catch(e => { IR_CACHE.delete(file); throw e; }));
  return IR_CACHE.get(file).then(b => normalizeIR(ctx, b));
}
/**
 * Web Audio 的 DynamicsCompressor 會自己補增益:makeup = (1 / 0dBFS 進去的輸出)^0.6(規格與 Chromium 的實作)。
 * 照 Chromium 的 knee 曲線(線性域指數曲線,k 讓膝點斜率 = 1/ratio)算出來,補償回去:壓縮器不是拿來加音量的
 */
export function compAutoMakeupDb(T, K, R) {
  const lt = 10 ** (T / 20), kt = 10 ** ((T + K) / 20);
  const curve = (x, k) => lt + (1 - Math.exp(-k * (x - lt))) / k;
  const slope = k => { const e = 1e-6; return (20 * Math.log10(curve(kt * (1 + e), k)) - 20 * Math.log10(curve(kt, k))) / (20 * Math.log10(1 + e)); };
  let lo = 0.1, hi = 1e4;                     // slope 隨 k 遞減:二分法
  for (let i = 0; i < 80; i++) { const m = Math.sqrt(lo * hi); if (slope(m) > 1 / R) lo = m; else hi = m; }
  const out0 = 20 * Math.log10(curve(kt, Math.sqrt(lo * hi))) + (0 - (T + K)) / R;
  return -out0 * 0.6;
}
/** 飽和曲線:y = tanh(k·x)/k(小訊號增益 1、0dBFS 約 −0.7dB、奇次諧波),輸入範圍 ±2 */
function satCurve(k) {
  const n = 4096, c = new Float32Array(n);
  for (let i = 0; i < n; i++) { const u = (i / (n - 1)) * 2 - 1; c[i] = Math.tanh(k * 2 * u) / k; }
  return c;
}

export class Player {
  constructor(data, manifest) {
    this.data = data;
    this.manifest = manifest;
    this.ctx = null;
    this.playing = false;
    this.onState = () => {};
    this.onProgress = () => {};
    this.onBar = () => {};
  }

  setupAudio(given) {
    if (this.ctx) return;
    const ctx = this.ctx = given ?? new (window.AudioContext || window.webkitAudioContext)({ latencyHint: "playback" });
    this.sampler = new Sampler(ctx, this.manifest, TRIMS);
    this.sampler.onProgress = p => this.onProgress(p);
    // 母帶:黏著壓縮(2:1,慢起音,只壓 1–2dB)→ 各曲風響度校正到 −14 LUFS(styles.json 的 master.gainDb)
    // → 預讀限幅器(−1 dBTP,AudioWorklet);worklet 不能用時退回 DynamicsCompressor
    const master = this.master = ctx.createGain();
    master.gain.value = 0.8;
    const glue = ctx.createDynamicsCompressor();
    glue.threshold.value = -18; glue.knee.value = 6; glue.ratio.value = 2;
    glue.attack.value = 0.03; glue.release.value = 0.25;
    const loud = this.loud = ctx.createGain();
    const fallback = this.fallback = ctx.createDynamicsCompressor();
    fallback.threshold.value = -2; fallback.knee.value = 0; fallback.ratio.value = 20;
    fallback.attack.value = 0.002; fallback.release.value = 0.1;
    // 總線飽和(類比磁帶 / 母帶機那一點點諧波,讓各軌的波形「黏」在一起):k 0.5,4 倍超取樣
    const sp = this.data.space ?? {};
    const satIn = ctx.createGain(), sat = ctx.createWaveShaper();
    satIn.gain.value = 0.5;
    sat.curve = satCurve(sp.saturation ?? 0.5); sat.oversample = "4x";
    master.connect(glue).connect(loud).connect(satIn).connect(sat).connect(fallback).connect(ctx.destination);
    this.glue = glue;
    const limiterReady = makeLimiter(ctx, -1).then(lim => {
      if (!lim) return false;
      sat.disconnect(); sat.connect(lim).connect(ctx.destination);
      this.limiter = lim;
      return true;
    });
    // 兩個空間,都是真的錄音:room = 真實房間(RT60 0.6 秒,跟鼓的房間麥同樣長),plate = 真實的板式殘響(1.8 秒)。
    // IR 檔載不到才退回固定種子的雜訊 IR(殘響是效果,不是音色)
    this.verbs = {};
    const irs = [];
    for (const [name, sec, seed, early, ret] of [["room", 0.6, 4321, true, 2.0], ["plate", 1.8, 1234, false, 1.8]]) {
      const cv = ctx.createConvolver(), lc = ctx.createBiquadFilter(), r = ctx.createGain();
      lc.type = "highpass"; lc.frequency.value = 200; // 殘響不留低頻,不然會糊
      r.gain.value = ret;
      cv.connect(lc).connect(r).connect(master);
      this.verbs[name] = cv;
      const file = sp.ir?.[name];
      irs.push((file ? loadIR(ctx, file) : Promise.reject(new Error("no IR")))
        .catch(() => impulse(ctx, sec, seed, early))
        .then(b => { cv.buffer = b; }));
    }
    // 主網頁只等 limiterReady:IR 也算在裡面
    this.limiterReady = Promise.all([limiterReady, ...irs]).then(([ok]) => ok);
  }

  /**
   * 每次播放一組新的匯流排:停止時整組拉掉,已經排進去的長音不會在下一次播放時冒出來。
   * lofi 的效果(低通、音高飄移)套在 keys 匯流排
   */
  buildBuses(st) {
    const ctx = this.ctx;
    const out = ctx.createGain();
    out.connect(this.master);
    if (this.wetOnly) out.gain.value = 0; // 量測用:只聽殘響
    // 每個空間一條送出;停止時跟 out 一起拉掉
    const sends = {}, wet = [];
    for (const [name, cv] of Object.entries(this.verbs)) {
      sends[name] = ctx.createGain();
      sends[name].gain.value = this.noReverb ? 0 : 1; // 量測用:看乾的取樣直接相加是什麼樣子
      sends[name].connect(cv);
      wet.push(sends[name]);
    }
    const mix = st.mix ?? {}; // 各曲風的音量校正(dB),由 tools/mix/analyze.py 量完定的
    const buses = {};
    this.drift = null;
    // 鼓組(各鼓件、大鼓、房間麥)先進同一台壓縮(鼓組黏在一起),再進混音
    const SP = this.data.space ?? {}, DC = SP.drumComp ?? {};
    const drumGroup = ctx.createDynamicsCompressor();
    drumGroup.threshold.value = DC.threshold ?? -24; drumGroup.knee.value = DC.knee ?? 6; drumGroup.ratio.value = DC.ratio ?? 4;
    drumGroup.attack.value = DC.attack ?? 0.01; drumGroup.release.value = DC.release ?? 0.12;
    const drumMakeup = ctx.createGain(); // 扣掉壓縮器自己補的增益
    drumMakeup.gain.value = 10 ** (-compAutoMakeupDb(drumGroup.threshold.value, drumGroup.knee.value, drumGroup.ratio.value) / 20);
    drumGroup.connect(drumMakeup).connect(out);
    this.drumGroup = drumGroup;
    for (const [name, b] of Object.entries(BUS)) {
      const g = ctx.createGain(), p = ctx.createStereoPanner();
      g.gain.value = b.gain * 10 ** ((mix[name === "kick" ? "drums" : name] ?? 0) / 20);
      p.pan.value = b.pan;
      let tail = g;
      if (name === "guitar" && st.instruments.guitar === "di_guitar") tail = this.amp(tail); // 乾聲吉他 → 音箱模擬
      const eqo = st.eq?.[name] ?? {}; // 曲風的 EQ 覆寫(例:分解和弦的鋼琴本身就在低音區,低切要放低)
      for (const [type, f0, x, q] of b.eq) {
        const f = eqo[type] ?? f0;
        const bq = ctx.createBiquadFilter();
        bq.type = type; bq.frequency.value = f;
        if (type === "highpass") bq.Q.value = BUTTER_Q_DB;
        else { bq.gain.value = x; if (q) bq.Q.value = q; }
        tail.connect(bq); tail = bq;
      }
      for (const fx of name === "keys" ? st.effects ?? [] : []) {
        if (fx.type === "lowpass") {
          const f = ctx.createBiquadFilter();
          f.type = "lowpass"; f.frequency.value = fx.hz; f.Q.value = BUTTER_Q_DB;
          tail.connect(f); tail = f;
        }
        if (fx.type === "pitchDrift") {
          // 調變訊號(不是音色):接到每一顆取樣的 detune
          const lfo = ctx.createOscillator(), depth = ctx.createGain();
          lfo.frequency.value = fx.rateHz; depth.gain.value = fx.cents;
          lfo.connect(depth); lfo.start();
          this.drift = depth;
          this.lfo = lfo;
        }
      }
      tail.connect(p).connect(name === "drums" || name === "kick" ? drumGroup : out);
      // 殘響送出:tools/mix/space.py 照舞台位置(styles.json 的 space.stage)解出來的量;
      // pre-delay 越長越近(直達聲跟反射分得越開),越短越遠
      const so = st.space?.sends?.[name] ?? {};
      const pre = SP.stage?.[name]?.predelay ?? 0;
      let sendSrc = tail;
      if (pre > 0) { const d = ctx.createDelay(0.1); d.delayTime.value = pre; tail.connect(d); sendSrc = d; }
      for (const v of ["room", "plate"]) if (so[v] ?? b[v]) {
        const s = ctx.createGain(); s.gain.value = so[v] ?? b[v];
        sendSrc.connect(s).connect(sends[v]);
      }
      buses[name] = { in: g };
    }
    // 鼓件各自的左右,接進鼓的匯流排(大鼓走自己的 EQ)
    for (const [pc, pan] of Object.entries(DRUM_PAN)) {
      const p = ctx.createStereoPanner();
      p.pan.value = pan;
      p.connect(buses.drums.in);
      buses["drums:" + pc] = { in: p };
    }
    buses["drums:kick"] = buses.kick;
    // 鼓的房間麥:立體聲原樣進鼓組(它本身就是空間,不再送人工殘響);低切 60Hz 免得大鼓的房間低頻糊掉
    const room = ctx.createGain(), roomHp = ctx.createBiquadFilter();
    room.gain.value = 10 ** ((mix.drums ?? 0) / 20) * BUS.drums.gain;
    roomHp.type = "highpass"; roomHp.frequency.value = 60; roomHp.Q.value = BUTTER_Q_DB;
    room.connect(roomHp).connect(drumGroup);
    this.sampler.roomGain = this.noReverb || !this.manifest[st.instruments.drums]?.room ? 0 : 10 ** ((st.space?.drumRoomDb ?? -12) / 20);
    for (const [k, v] of Object.entries(buses)) if (k === "drums" || k.startsWith("drums:")) this.sampler.roomOf.set(v.in, room);
    buses["drums:room"] = { in: room };
    return { out, wet, buses };
  }

  /**
   * 吉他音箱模擬(re-amp):錄音室的破音吉他就是把乾聲(DI)送進音箱。
   * 前級 EQ → 失真(tanh 曲線,4 倍超取樣)→ 音箱喇叭的頻寬(80Hz–5kHz)與中頻
   */
  amp(input) {
    const ctx = this.ctx, chain = [];
    const pre = ctx.createBiquadFilter(); pre.type = "peaking"; pre.frequency.value = 800; pre.gain.value = 6; pre.Q.value = 0.7;
    const drive = ctx.createGain(); drive.gain.value = 18;
    const ws = ctx.createWaveShaper();
    const n = 2048, curve = new Float32Array(n), k = 2.5;
    for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; curve[i] = Math.tanh(k * x) / Math.tanh(k); }
    ws.curve = curve; ws.oversample = "4x";
    const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 80; hp.Q.value = BUTTER_Q_DB;
    const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 5000; lp.Q.value = BUTTER_Q_DB;
    const mid = ctx.createBiquadFilter(); mid.type = "peaking"; mid.frequency.value = 2500; mid.gain.value = -3; mid.Q.value = 1;
    const post = ctx.createGain(); post.gain.value = 0.055;
    for (const nd of [pre, drive, ws, hp, lp, mid, post]) chain.push(nd);
    input.connect(chain[0]);
    for (let i = 0; i < chain.length - 1; i++) chain[i].connect(chain[i + 1]);
    return post;
  }

  /** opt 同 engine.render;另外 parts: { pad: bool, guitar: bool } 控制可選聲部 */
  async start(styleId, opt) {
    this.setupAudio();
    await this.ctx.resume();
    this.stop();
    const st = this.style = resolveStyle(this.data, styleId);
    this.opt = { ...opt };
    this.parts = opt.parts ?? {};
    // 先算第一段,錯誤(看不懂的和弦)在這裡丟出去,不出聲
    const prog = opt.chords ? { example: opt.chords } : st.progressions.find(p => p.id === opt.progression) ?? st.progressions[0];
    this.chunkBars = chunkBarsFor(progressionBars(prog, 0, opt.chords ? "example" : "roman").length);
    const first = render(this.data, styleId, { ...this.opt, bars: this.chunkBars, seed: (opt.seed ?? 1), countIn: true });
    this.onState("loading");
    await this.sampler.ensure(this.needs(first.events));
    await this.limiterReady;
    this.loud.gain.value = 10 ** ((st.master?.gainDb ?? 0) / 20);
    this.session = this.buildBuses(st);
    this.buses = this.session.buses;
    this.chunk = 0;
    this.chunkEvents = first.events;
    this.meta = first.meta;
    this.t0 = this.ctx.currentTime + 0.25;
    this.session.vinyl = await this.vinyl(this.t0, this.session.out);
    this.idx = 0;
    this.lastBar = -1;
    this.pending = null;
    this.playing = true;
    this.onState("playing");
    this.timer = setInterval(() => this.tick(), TICK_MS);
    this.tick();
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (this.session) {
      const t = this.ctx.currentTime, { out, wet } = this.session, lfo = this.lfo;
      for (const g of [out.gain, ...wet.map(w => w.gain)]) { g.setValueAtTime(g.value, t); g.linearRampToValueAtTime(0, t + 0.06); }
      const vinyl = this.session.vinyl;
      setTimeout(() => { out.disconnect(); wet.forEach(w => w.disconnect()); if (lfo) lfo.stop(); if (vinyl) vinyl.stop(); }, 3000);
      this.session = null;
      this.lfo = null;
    }
    this.playing = false;
    this.onState("stopped");
  }

  /** 這一下用哪一件樂器:勾了替代樂器(slap 貝斯、低音提琴、尼龍吉他…)而且密度符合就換 */
  instrOf(track, e) {
    for (const a of this.style.alternatives ?? [])
      if (a.track === track && this.partOn(a.id, a.default) && (!a.densities || !e || a.densities.includes(e.dens))) return a.instr;
    return this.style.instruments[track === "keys2" ? "keys2" : track] ?? this.style.instruments.keys;
  }
  partOn(id, dflt = true) { return this.parts[id] ?? dflt; }
  on(track) {
    const t = this.style.tracks[track];
    return !(t && t.optional) || this.partOn(track, t.default ?? true);
  }
  /** lofi 的黑膠底噪:CC0 的唱片底噪錄音循環播放,−30dB,不進殘響 */
  async vinyl(when, dest) {
    const fx = (this.style.effects ?? []).find(f => f.type === "vinylNoise");
    if (!fx || !this.partOn("vinyl", true)) return null;
    const b = await this.sampler.loopBuffer("vinyl_noise");
    if (!b) return null;
    const src = this.ctx.createBufferSource(), g = this.ctx.createGain();
    src.buffer = b; src.loop = true;
    g.gain.value = 10 ** (fx.db / 20) / Math.max(1e-6, this.sampler.rms(b));
    src.connect(g).connect(dest);
    src.start(when);
    return src;
  }

  needs(events) {
    const out = [];
    for (const e of events) {
      if (!this.on(e.track)) continue;
      if (e.track === "drums") out.push({ instr: this.style.instruments.drums, piece: e.piece, vel: e.vel });
      else for (const midi of e.notes) out.push({ instr: this.instrOf(e.track, e), midi, vel: e.vel });
    }
    return out;
  }

  nextChunk() {
    const r = render(this.data, this.style.id, { ...this.opt, bars: this.chunkBars, seed: (this.opt.seed ?? 1) + this.chunk + 1, countIn: false });
    this.sampler.ensure(this.needs(r.events)); // 播到一半就先載下一段要用的取樣
    return r.events;
  }

  tick() {
    // 分頁在背景時 setInterval 會被放慢到一秒一次,排遠一點才不會斷
    const ahead = typeof document !== "undefined" && document.hidden ? 1.5 : LOOKAHEAD;
    const now = this.ctx.currentTime, horizon = now + ahead;
    const barSec = this.meta.barSec;
    if (!this.pending && this.idx > this.chunkEvents.length / 2) this.pending = this.nextChunk();
    while (true) {
      if (this.idx >= this.chunkEvents.length) {
        // 下一段:換種子,不再有預備拍;時間接在上一段後面
        this.t0 += (this.chunkBars + (this.chunk === 0 ? 1 : 0)) * barSec;
        this.chunkEvents = this.pending ?? this.nextChunk();
        this.pending = null;
        this.chunk++;
        this.idx = 0;
        this.lastBar = -1;
      }
      const e = this.chunkEvents[this.idx];
      const when = this.t0 + e.time;
      if (when > horizon) break;
      this.idx++;
      if (when < now - 0.05 || !this.on(e.track)) continue;
      const bus = (this.buses["drums:" + e.piece] ?? this.buses[e.track]).in;
      if (e.track === "drums") this.sampler.hit(this.style.instruments.drums, e.piece, e.vel, Math.max(when, now), bus);
      else {
        const instr = this.instrOf(e.track, e);
        const opt = e.track === "keys" && this.drift ? { detune: this.drift } : {};
        e.notes.forEach((midi, i) => this.sampler.note(instr, midi, e.noteVel?.[i] ?? e.vel,
          Math.max(when + (e.noteDt?.[i] ?? 0), now), e.dur, bus, opt));
      }
      if (e.bar >= 0 && e.bar !== this.lastBar) { this.lastBar = e.bar; this.onBar(e.bar, when); }
    }
  }

  /** 離線算成 AudioBuffer(量測與之後的「下載音檔」用);跟即時播放走同一套取樣與匯流排 */
  async renderOffline(styleId, opt, bars = 8, sampleRate = 44100) {
    const st = resolveStyle(this.data, styleId);
    const r = render(this.data, styleId, { ...opt, bars });
    const len = Math.ceil((r.meta.barSec * (bars + 1) + 3) * sampleRate);
    const ctx = new OfflineAudioContext(2, len, sampleRate);
    const p = new Player(this.data, this.manifest);
    p.setupAudio(ctx);
    p.style = st;
    p.parts = opt.parts ?? {};
    p.noReverb = !!opt.noReverb;
    p.wetOnly = !!opt.wetOnly; // 量測用:只要殘響(tools/mix/space.py)
    const only = opt.only; // 只算某幾軌(分軌量測)
    await p.sampler.ensure(p.needs(r.events));
    await p.sampler.background;
    await p.limiterReady;
    p.loud.gain.value = opt.noMaster ? 1 : 10 ** ((st.master?.gainDb ?? 0) / 20);
    if (opt.raw) { p.master.disconnect(); p.master.connect(ctx.destination); } // 量測用:跳過母帶鏈,分軌才能線性相加
    const session = p.buildBuses(st), { buses } = session;
    // 量測用:每 10ms 讀一次鼓組壓縮與黏著壓縮壓了幾 dB
    const gr = { drums: [], glue: [] };
    if (opt.probe) for (let t = 0.5; t < len / sampleRate - 0.1; t += 0.01)
      ctx.suspend(t).then(() => { gr.drums.push(p.drumGroup.reduction); gr.glue.push(p.glue.reduction); ctx.resume(); });
    if (!only) await p.vinyl(0, session.out);
    for (const e of r.events) {
      if (!p.on(e.track) || (only && !only.includes(e.track))) continue;
      const when = e.time + 0.05;
      if (e.track === "drums") p.sampler.hit(st.instruments.drums, e.piece, e.vel, when, (buses["drums:" + e.piece] ?? buses.drums).in);
      else e.notes.forEach((midi, i) => p.sampler.note(p.instrOf(e.track, e), midi, e.noteVel?.[i] ?? e.vel, when + (e.noteDt?.[i] ?? 0),
        e.dur, buses[e.track].in, e.track === "keys" && p.drift ? { detune: p.drift } : {}));
    }
    return { buffer: await ctx.startRendering(), meta: r.meta, failed: p.sampler.progress.failed, gr };
  }
}
