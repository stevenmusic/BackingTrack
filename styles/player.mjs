// 播放器:engine.render() 的事件 → Sampler。排程一律用 AudioContext.currentTime 提前約 0.2 秒排,
// setInterval 只負責「來看一下」。混音只做到「聽得清楚、不削波」,母帶之後再做。
import { render, resolveStyle, mulberry32, progressionBars } from "./engine.mjs";
import { Sampler } from "./sampler.mjs";

const LOOKAHEAD = 0.2, TICK_MS = 25, MIN_CHUNK = 64;
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
// 每一軌的音量、左右、殘響送出
const BUS = {
  drums:  { gain: 0.8,  pan: 0,     rev: 0.10 },
  bass:   { gain: 0.85, pan: 0,     rev: 0 },
  keys:   { gain: 0.62, pan: -0.08, rev: 0.22 },
  keys2:  { gain: 0.42, pan: 0.15,  rev: 0.25 },
  pad:    { gain: 0.45, pan: 0.2,   rev: 0.35 },
  guitar: { gain: 0.5,  pan: 0.35,  rev: 0.15 },
};

/** 殘響 IR:固定種子的衰減雜訊,左右不同種子,能量正規化 */
function impulse(ctx, seconds = 1.8, decay = 3) {
  const n = Math.floor(ctx.sampleRate * seconds);
  const ir = ctx.createBuffer(2, n, ctx.sampleRate);
  let e = 0;
  for (let ch = 0; ch < 2; ch++) {
    const r = mulberry32(1234 + ch * 777), d = ir.getChannelData(ch);
    for (let i = 0; i < n; i++) { d[i] = (r() * 2 - 1) * (1 - i / n) ** decay; e += d[i] * d[i]; }
  }
  const k = 1 / Math.sqrt(e / 2);
  for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); for (let i = 0; i < n; i++) d[i] *= k; }
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
    this.reverb = ctx.createConvolver();
    this.reverb.buffer = impulse(ctx);
    const revRet = ctx.createGain();
    revRet.gain.value = 0.6;
    this.reverb.connect(revRet).connect(master);
  }

  /**
   * 每次播放一組新的匯流排:停止時整組拉掉,已經排進去的長音不會在下一次播放時冒出來。
   * lofi 的效果(低通、音高飄移)套在 keys 匯流排
   */
  buildBuses(st) {
    const ctx = this.ctx;
    const out = ctx.createGain(), wet = ctx.createGain();
    out.connect(this.master);
    wet.connect(this.reverb);
    const buses = {};
    this.drift = null;
    for (const [name, b] of Object.entries(BUS)) {
      const g = ctx.createGain(), p = ctx.createStereoPanner(), s = ctx.createGain();
      g.gain.value = b.gain; p.pan.value = b.pan; s.gain.value = b.rev;
      let tail = g;
      for (const fx of name === "keys" ? st.effects ?? [] : []) {
        if (fx.type === "lowpass") {
          const f = ctx.createBiquadFilter();
          f.type = "lowpass"; f.frequency.value = fx.hz; f.Q.value = 0.5;
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
      tail.connect(s).connect(wet);
      buses[name] = { in: g };
    }
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
      for (const g of [out.gain, wet.gain]) { g.setValueAtTime(g.value, t); g.linearRampToValueAtTime(0, t + 0.06); }
      setTimeout(() => { out.disconnect(); wet.disconnect(); if (lfo) lfo.stop(); }, 3000);
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
      const bus = this.buses[e.track].in;
      if (e.track === "drums") this.sampler.hit(this.style.instruments.drums, e.piece, e.vel, Math.max(when, now), bus);
      else {
        const instr = this.instrOf(e.track);
        const opt = e.track === "keys" && this.drift ? { detune: this.drift } : {};
        for (const midi of e.notes) this.sampler.note(instr, midi, e.vel, Math.max(when, now), e.dur, bus, opt);
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
    const only = opt.only; // 只算某幾軌(分軌量測)
    await p.sampler.ensure(p.needs(r.events));
    await p.sampler.background;
    const { buses } = p.buildBuses(st);
    for (const e of r.events) {
      if (!p.on(e.track) || (only && !only.includes(e.track))) continue;
      const when = e.time + 0.05;
      if (e.track === "drums") p.sampler.hit(st.instruments.drums, e.piece, e.vel, when, buses.drums.in);
      else for (const midi of e.notes)
        p.sampler.note(p.instrOf(e.track), midi, e.vel, when, e.dur, buses[e.track].in, e.track === "keys" && p.drift ? { detune: p.drift } : {});
    }
    return { buffer: await ctx.startRendering(), meta: r.meta, failed: p.sampler.progress.failed };
  }
}
