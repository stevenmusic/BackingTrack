// 取樣樂器:samples.json(由 tools/samples/build_manifest.py 從實際檔案列表產生)→ Web Audio。
// 全部是錄音取樣,沒有即時合成的音色。round robin 用計數器輪,不用亂數。

const decodeQueue = { tail: Promise.resolve() };
// 解碼好的取樣整頁共用(AudioBuffer 不綁 AudioContext;離線算音檔時不用重抓)
const CACHE = new Map();

/** 依序試每個來源;解碼一顆一顆排隊(一起解會跟排程搶主執行緒) */
function fetchDecode(ctx, bases, path, onDone) {
  const url = encodeURI(path).replace(/#/g, "%23");
  let i = 0;
  const attempt = () => fetch(bases[i] + url)
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer(); })
    .catch(e => { if (++i < bases.length) return attempt(); throw e; });
  return attempt().then(ab => {
    const job = decodeQueue.tail.then(() => ctx.decodeAudioData(ab));
    decodeQueue.tail = job.catch(() => {});
    return job;
  }).finally(onDone);
}

const layerOf = (vel, edges) => {
  const i = edges.findIndex(([lo, hi]) => vel >= lo && vel <= hi);
  return i < 0 ? edges.length - 1 : i;
};

export class Sampler {
  /** trims:每件樂器的增益校正(量過取樣的電平才填) */
  constructor(ctx, manifest, trims = {}) {
    this.ctx = ctx;
    this.m = manifest;
    this.trims = trims;
    this.buf = CACHE;          // 網址 → AudioBuffer | Promise
    this.failed = new Set();
    this.rr = new Map();
    this.chokes = new Map();   // 開放 hi-hat 被下一顆閉合 hi-hat 掐掉
    this.progress = { total: 0, done: 0, failed: 0 };
    this.onProgress = () => {};
  }

  // ── 挑取樣 ──
  zoneFor(instr, midi, vel) {
    const I = this.m[instr];
    const layer = layerOf(vel, I.vel);
    let best = null, bd = Infinity;
    for (const z of I.zones) {
      const d = Math.abs(z.key - midi) * 10 + Math.abs(z.layer - layer); // 音高優先,力度層其次
      if (d < bd) { bd = d; best = z; }
    }
    return best;
  }
  pieceLayer(kit, piece, vel) {
    const P = this.m[kit].pieces[piece];
    return P ? P.layers[layerOf(vel, P.vel)] : null;
  }

  /** notes: [{ instr, midi, vel } | { instr, piece, vel }] → 要先載的檔(每組 round robin 先載一份)與背景補的 */
  plan(notes) {
    const first = new Map(), rest = new Map();
    const add = (instr, files) => {
      const src = this.m[instr].src;
      files.forEach((f, i) => (i === 0 ? first : rest).set(src[0] + f, [src, f]));
    };
    for (const n of notes) {
      if (n.piece) { const l = this.pieceLayer(n.instr, n.piece, n.vel); if (l) add(n.instr, l); }
      else add(n.instr, this.zoneFor(n.instr, n.midi, n.vel).files);
    }
    for (const k of first.keys()) rest.delete(k);
    return { first: [...first.values()], rest: [...rest.values()] };
  }

  loadFiles(list) {
    return Promise.all(list.map(([src, f]) => {
      const key = src[0] + f;
      if (this.buf.has(key) || this.failed.has(key)) return this.buf.get(key);
      this.progress.total++;
      this.onProgress(this.progress);
      const p = fetchDecode(this.ctx, src, f, () => { this.progress.done++; this.onProgress(this.progress); })
        .then(b => { this.buf.set(key, b); return b; })
        .catch(() => { this.buf.delete(key); this.failed.add(key); this.progress.failed++; });
      this.buf.set(key, p);
      return p;
    }));
  }

  /** 先載會擋播放的那一批,其餘背景補 */
  async ensure(notes) {
    const { first, rest } = this.plan(notes);
    await this.loadFiles(first);
    this.background = this.loadFiles(rest);
  }

  ready(instr, files) {
    const src = this.m[instr].src;
    const loaded = files.map(f => this.buf.get(src[0] + f)).filter(b => b instanceof AudioBuffer);
    if (!loaded.length) return null;
    const k = instr + files[0];
    const i = this.rr.get(k) ?? 0;
    this.rr.set(k, i + 1);
    return loaded[i % loaded.length];
  }

  // ── 發聲 ──
  /** 旋律樂器:midi、vel(1–127)、when、dur(秒)、dest */
  note(instr, midi, vel, when, dur, dest, opt = {}) {
    const I = this.m[instr];
    const z = this.zoneFor(instr, midi, vel);
    const b = z && this.ready(instr, z.files);
    if (!b) return false;
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = b;
    src.playbackRate.value = 2 ** ((midi - z.key + (I.tune ?? 0)) / 12);
    if (opt.detune) opt.detune.connect(src.detune);
    const g = ctx.createGain();
    const peak = (this.trims[instr] ?? 1) * (0.25 + 0.75 * (vel / 127) ** 1.6);
    const atk = I.attack ?? 0.002;
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(peak, when + atk);
    const rel = I.release ?? 0.2;
    const off = when + Math.max(dur, atk);
    g.gain.setValueAtTime(peak, off);
    g.gain.setTargetAtTime(0, off, rel / 3);
    src.connect(g).connect(dest);
    src.start(when);
    src.stop(Math.min(off + rel * 2.5, when + b.duration / src.playbackRate.value));
    return true;
  }

  /** 鼓:piece、vel、when;開放 hi-hat 會被下一顆 hi-hat 掐掉 */
  hit(kit, piece, vel, when, dest) {
    const files = this.pieceLayer(kit, piece, vel);
    const b = files && this.ready(kit, files);
    if (!b) return false;
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = b;
    const g = ctx.createGain();
    const trim = (this.trims[kit + "." + piece] ?? 1) * (this.trims[kit] ?? 1);
    g.gain.value = trim * (0.3 + 0.7 * (vel / 127) ** 1.4);
    src.connect(g).connect(dest);
    if (piece === "hat" || piece === "openhat") {
      const prev = this.chokes.get(kit);
      if (prev && prev.until > when) {
        prev.g.gain.setValueAtTime(prev.g.gain.value, when);
        prev.g.gain.setTargetAtTime(0, when, 0.012);
      }
      this.chokes.set(kit, piece === "openhat" ? { g, until: when + b.duration } : null);
    }
    src.start(when);
    return true;
  }
}
