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

/** 起音前的空白:第一個超過峰值 1%(−40dB)的位置往前 1ms;每個 buffer 算一次 */
const LEAD = new WeakMap();
export function leadOf(b) {
  if (LEAD.has(b)) return LEAD.get(b);
  const d = b.getChannelData(0);
  let peak = 0;
  for (let i = 0; i < d.length; i++) peak = Math.max(peak, Math.abs(d[i]));
  let i = 0;
  while (i < d.length && Math.abs(d[i]) < peak * 0.01) i++;
  const lead = Math.max(0, i / b.sampleRate - 0.001);
  LEAD.set(b, lead);
  return lead;
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
    this.roomOf = new WeakMap(); // 鼓件的匯流排 → 房間麥的匯流排(Player.buildBuses 登記;沒登記就不播房間麥)
    this.roomGain = 0;         // 房間麥相對中距離麥的大小(線性;Player 照 styles.json 的 space 設)
    this.progress = { total: 0, done: 0, failed: 0 };
    this.onProgress = () => {};
  }

  // ── 挑取樣 ──
  zoneFor(instr, midi, vel, zones) {
    const I = this.m[instr];
    const layer = layerOf(vel, I.vel ?? [[1, 127]]);
    let best = null, bd = Infinity;
    for (const z of zones ?? I.zones) {
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
      if (n.piece) {
        const l = this.pieceLayer(n.instr, n.piece, n.vel);
        if (l) add(n.instr, l);
        // 房間麥全部背景補:開頭幾拍沒有房間麥只是比較乾,不擋播放
        const R = this.m[n.instr].room;
        if (l && R) l.forEach(f => rest.set(R.src[0] + this.roomFile(R, f), [R.src, this.roomFile(R, f)]));
      }
      else {
        add(n.instr, this.zoneFor(n.instr, n.midi, n.vel).files);
        const RN = this.m[n.instr].releaseNoise;
        if (RN) add(n.instr, this.zoneFor(n.instr, n.midi, n.vel, RN.zones).files);
      }
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
    const loaded = files.filter(f => this.buf.get(src[0] + f) instanceof AudioBuffer);
    if (!loaded.length) return null;
    const k = instr + files[0];
    const i = this.rr.get(k) ?? 0;
    this.rr.set(k, i + 1);
    this.lastFile = loaded[i % loaded.length]; // 房間麥要對到同一顆 round robin
    return this.buf.get(src[0] + this.lastFile);
  }
  roomFile(R, f) { return f.replace(R.from, R.to); }

  /** 循環用的長取樣(例:黑膠底噪) */
  async loopBuffer(instr) {
    const I = this.m[instr];
    if (!I?.loop) return null;
    await this.loadFiles([[I.src, I.loop]]);
    const b = this.buf.get(I.src[0] + I.loop);
    return b instanceof AudioBuffer ? b : null;
  }
  rms(b) {
    let s = 0, n = 0;
    for (let c = 0; c < b.numberOfChannels; c++) { const d = b.getChannelData(c); for (let i = 0; i < d.length; i += 4) { s += d[i] * d[i]; n++; } }
    return Math.sqrt(s / n);
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
    src.playbackRate.value = 2 ** ((midi - z.key + (z.tune ?? 0) + (I.tune ?? 0)) / 12); // z.tune:那一個取樣量到的音準偏差
    if (opt.detune) opt.detune.connect(src.detune);
    const g = ctx.createGain();
    const v = vel / 127;
    // 力度對音量:有原作者的 amp_veltrack 就照它(sfz 預設曲線 = 力度平方),否則用通用曲線
    const vt = I.veltrack;
    const peak = (this.trims[instr] ?? 1) * (vt != null ? 1 - vt + vt * v * v : 0.25 + 0.75 * v ** 1.6);
    const atk = I.attack ?? 0.002;
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(peak, when + atk);
    const rel = I.release ?? 0.2;
    const off = when + Math.max(dur, atk);
    g.gain.setValueAtTime(peak, off);
    g.gain.setTargetAtTime(0, off, rel / 3);
    src.connect(g).connect(dest);
    const lead = leadOf(b);
    src.start(when, lead);
    src.stop(Math.min(off + rel * 2.5, when + (b.duration - lead) / src.playbackRate.value));
    // 放鍵的制音聲(Salamander 的 rel 取樣,照 hammer.txt:−37dB、amp_veltrack 82、按越久越小聲 2dB/秒)
    const RN = I.releaseNoise;
    if (RN) {
      const rz = this.zoneFor(instr, midi, vel, RN.zones);
      const rb = rz && rz.key === midi && this.ready(instr, rz.files);
      if (rb) {
        const rs = ctx.createBufferSource(), rg = ctx.createGain();
        rs.buffer = rb;
        rg.gain.value = (this.trims[instr] ?? 1) * 10 ** ((RN.db - 2 * Math.max(dur, 0)) / 20) * (1 - RN.veltrack + RN.veltrack * v * v);
        rs.connect(rg).connect(dest);
        rs.start(off);
      }
    }
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
    const lead = leadOf(b), gs = [g];
    // 房間麥:同一次敲擊的另一對麥克風。兩對麥是同步錄的,用中距離麥的起音位置一起跳,
    // 房間麥比較晚到的那幾毫秒(真的距離)就留著
    const R = this.m[kit].room, roomDest = this.roomOf.get(dest);
    if (R && roomDest && this.roomGain > 0) {
      const rb = this.buf.get(R.src[0] + this.roomFile(R, this.lastFile));
      if (rb instanceof AudioBuffer) {
        const rs = ctx.createBufferSource(), rg = ctx.createGain();
        rs.buffer = rb;
        rg.gain.value = g.gain.value * this.roomGain;
        rs.connect(rg).connect(roomDest);
        rs.start(when, lead);
        gs.push(rg);
      }
    }
    if (piece === "hat" || piece === "openhat") {
      const prev = this.chokes.get(kit);
      if (prev && prev.until > when) for (const pg of prev.gs) {
        pg.gain.setValueAtTime(pg.gain.value, when);
        pg.gain.setTargetAtTime(0, when, 0.012);
      }
      this.chokes.set(kit, piece === "openhat" ? { gs, until: when + b.duration } : null);
    }
    src.start(when, lead);
    return true;
  }
}
