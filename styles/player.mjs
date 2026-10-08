// 播放器:engine.render() 的事件 → Sampler。排程一律用 AudioContext.currentTime 提前約 0.2 秒排,
// setInterval 只負責「來看一下」。混音只做到「聽得清楚、不削波」,母帶之後再做。
import { render, resolveStyle, mulberry32, progressionBars } from "./engine.mjs";
import { Sampler } from "./sampler.mjs";

const LOOKAHEAD = 0.2, TICK_MS = 25, MIN_CHUNK = 64;
const BUTTER_Q_DB = -3.01; // Web Audio 的 highpass / lowpass Q 單位是 dB;Butterworth = −3.01
const gcd = (a, b) => (b ? gcd(b, a % b) : a);
/** 一段幾小節:進行長度與 16(A/B 段)的公倍數,至少 64;接縫才不會把進行或段落從頭開始 */
const chunkBarsFor = len => { const l = (len * 16) / gcd(len, 16); return l * Math.ceil(MIN_CHUNK / l); };

// 各樂器的電平校正:讓同一個力度在不同取樣庫大約一樣大(2026-10-08 分軌量 RMS 定的,見 README)
export const TRIMS = {
  piano: 0.75, rhodes: 0.45, electric_bass: 1.25, strings: 6.5, clean_guitar: 1.6,
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
 * 殘響 IR:固定種子的雜訊,指數衰減(RT60 = seconds),左右不同種子;
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
    // 母帶之前的保險:只防削波,不拿來加音量
    const master = this.master = ctx.createGain();
    master.gain.value = 0.8;
    const safety = ctx.createDynamicsCompressor();
    safety.threshold.value = -3; safety.knee.value = 0; safety.ratio.value = 20;
    safety.attack.value = 0.002; safety.release.value = 0.1;
    master.connect(safety).connect(ctx.destination);
    // 兩個空間:room(0.5 秒,讓乾的取樣像在同一個房間)與 plate(1.6 秒,鍵盤、弦樂)
    this.verbs = {};
    for (const [name, sec, seed, early, ret] of [["room", 0.5, 4321, true, 2.0], ["plate", 1.6, 1234, false, 1.8]]) {
      const cv = ctx.createConvolver(), lc = ctx.createBiquadFilter(), r = ctx.createGain();
      cv.buffer = impulse(ctx, sec, seed, early);
      lc.type = "highpass"; lc.frequency.value = 200; // 殘響不留低頻,不然會糊
      r.gain.value = ret;
      cv.connect(lc).connect(r).connect(master);
      this.verbs[name] = cv;
    }
  }

  /**
   * 每次播放一組新的匯流排:停止時整組拉掉,已經排進去的長音不會在下一次播放時冒出來。
   * lofi 的效果(低通、音高飄移)套在 keys 匯流排
   */
  buildBuses(st) {
    const ctx = this.ctx;
    const out = ctx.createGain();
    out.connect(this.master);
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
    for (const [name, b] of Object.entries(BUS)) {
      const g = ctx.createGain(), p = ctx.createStereoPanner();
      g.gain.value = b.gain * 10 ** ((mix[name === "kick" ? "drums" : name] ?? 0) / 20);
      p.pan.value = b.pan;
      let tail = g;
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
      tail.connect(p).connect(out);
      const so = st.sends?.[name === "kick" ? "drums" : name] ?? {}; // 曲風的殘響送出覆寫(例:808 是單聲道,多給房間)
      for (const v of ["room", "plate"]) if (so[v] ?? b[v]) {
        const s = ctx.createGain(); s.gain.value = so[v] ?? b[v];
        tail.connect(s).connect(sends[v]);
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
    return { out, wet, buses };
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
    this.session = this.buildBuses(st);
    this.buses = this.session.buses;
    this.chunk = 0;
    this.chunkEvents = first.events;
    this.meta = first.meta;
    this.t0 = this.ctx.currentTime + 0.25;
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
      setTimeout(() => { out.disconnect(); wet.forEach(w => w.disconnect()); if (lfo) lfo.stop(); }, 3000);
      this.session = null;
      this.lfo = null;
    }
    this.playing = false;
    this.onState("stopped");
  }

  instrOf(track) {
    return this.style.instruments[track === "keys2" ? "keys2" : track] ?? this.style.instruments.keys;
  }
  on(track) {
    const t = this.style.tracks[track];
    return !(t && t.optional && this.parts[track] === false);
  }

  needs(events) {
    const out = [];
    for (const e of events) {
      if (!this.on(e.track)) continue;
      if (e.track === "drums") out.push({ instr: this.style.instruments.drums, piece: e.piece, vel: e.vel });
      else for (const midi of e.notes) out.push({ instr: this.instrOf(e.track), midi, vel: e.vel });
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
        const instr = this.instrOf(e.track);
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
    const only = opt.only; // 只算某幾軌(分軌量測)
    await p.sampler.ensure(p.needs(r.events));
    await p.sampler.background;
    const { buses } = p.buildBuses(st);
    for (const e of r.events) {
      if (!p.on(e.track) || (only && !only.includes(e.track))) continue;
      const when = e.time + 0.05;
      if (e.track === "drums") p.sampler.hit(st.instruments.drums, e.piece, e.vel, when, (buses["drums:" + e.piece] ?? buses.drums).in);
      else e.notes.forEach((midi, i) => p.sampler.note(p.instrOf(e.track), midi, e.noteVel?.[i] ?? e.vel, when + (e.noteDt?.[i] ?? 0),
        e.dur, buses[e.track].in, e.track === "keys" && p.drift ? { detune: p.drift } : {}));
    }
    return { buffer: await ctx.startRendering(), meta: r.meta, failed: p.sampler.progress.failed };
  }
}
