// BackingTrack 風格引擎(規格書 v1):styles.json → 音符事件。
// 只產生事件(時間、音高、力度),不發聲;瀏覽器與 Node 都能 import。
// 不用內建亂數:人性化走 mulberry32 固定種子,同一個 seed 一定產生同一組事件。

export const CELLS = 16;
export const FILL_CELLS = 8;
export const SYMBOLS = { drums: "Xxor.", bass: "R3578A-.", keys: "CSU123456NP-.", guitar: "x." };
export const DRUM_VEL = { X: 112, x: 88, o: 48, r: [70, 60] };
export const RANGE = { bass: [28, 48], bassRoot: [31, 43], keys: [48, 72], arp: [43, 67], pad: [52, 67], lowKeysMax: 69 };
export const TRACK_VEL = { bass: 100, keys: 84, keys2: 76, pad: 64, guitar: 70 };
const MELODIC = ["bass", "keys", "keys2", "pad", "guitar"];
const MAX_LEAP = 4;
const HUMANIZE_CAP_MS = 15;
const VARY_SCALE = 0.5;                           // 搶拍:POP909 的比例打五折(伴奏要穩)
const DENS_VARY = { low: 0.3, standard: 0.6, high: 1 }; // 密度越高變化越多


/** 去掉空白與 `|`,回傳有效字元 */
export const cells = s => s.replace(/[\s|]/g, "");

// ───────── 和弦 ─────────
const LETTER = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const accOf = s => (s === "♯" || s === "#" ? 1 : s === "♭" || s === "b" ? -1 : 0);
const mod12 = n => ((n % 12) + 12) % 12;

// 和弦性質 → 各級音距離根音幾個半音(3 的位置在 sus 和弦放四度)
export const QUALITY = {
  "":      { 3: 4, 5: 7 },
  m:       { 3: 3, 5: 7 },
  sus4:    { 3: 5, 5: 7 },
  "7":     { 3: 4, 5: 7, 7: 10 },
  maj7:    { 3: 4, 5: 7, 7: 11 },
  m7:      { 3: 3, 5: 7, 7: 10 },
  "m7♭5":  { 3: 3, 5: 6, 7: 10 },
  "7sus4": { 3: 5, 5: 7, 7: 10 },
  maj9:    { 3: 4, 5: 7, 7: 11, 9: 14 },
  m9:      { 3: 3, 5: 7, 7: 10, 9: 14 },
  "9":     { 3: 4, 5: 7, 7: 10, 9: 14 },
  "13":    { 3: 4, 5: 7, 7: 10, 9: 14, 13: 21 },
  "7♭9":   { 3: 4, 5: 7, 7: 10, 9: 13 },
  // 下面是讓使用者自己輸入和弦時用的常見性質(規格的進行用不到)
  "6":     { 3: 4, 5: 7, 13: 9 },
  m6:      { 3: 3, 5: 7, 13: 9 },
  add9:    { 3: 4, 5: 7, 9: 14 },
  madd9:   { 3: 3, 5: 7, 9: 14 },
  dim:     { 3: 3, 5: 6 },
  dim7:    { 3: 3, 5: 6, 7: 9 },
  aug:     { 3: 4, 5: 8 },
  "7♯9":   { 3: 4, 5: 7, 7: 10, 9: 15 },
  "7♯5":   { 3: 4, 5: 8, 7: 10 },
  "9sus4": { 3: 5, 5: 7, 7: 10, 9: 14 },
  m11:     { 3: 3, 5: 7, 7: 10, 9: 14 },
  maj13:   { 3: 4, 5: 7, 7: 11, 9: 14, 13: 21 },
  "mM7":   { 3: 3, 5: 7, 7: 11 },
};
// 常見寫法 → 上表的 key
const ALIAS = { min: "m", "-": "m", M7: "maj7", Δ: "maj7", "Δ7": "maj7", ma7: "maj7", "m7b5": "m7♭5", ø: "m7♭5", ø7: "m7♭5",
  "°": "dim", "°7": "dim7", "+": "aug", sus: "sus4", "7sus": "7sus4", "m(maj7)": "mM7", mmaj7: "mM7", "69": "6", "6/9": "6" };

function chordOf(root, bass, quality, sym) {
  const iv = QUALITY[quality];
  if (!iv) throw new Error(`不支援的和弦性質:「${sym}」(${quality || "大三"})`);
  return { sym, root: mod12(root), bass: mod12(bass), quality, iv };
}

/** 音名和弦:C、Am7、Bm7♭5、G/B、C7/B♭ */
export function parseChord(sym) {
  const m = /^([A-G])([♯♭#b]?)([^/]*)(?:\/([A-G])([♯♭#b]?))?$/.exec(sym.trim());
  if (!m) throw new Error(`看不懂的和弦:「${sym}」`);
  const root = LETTER[m[1]] + accOf(m[2]);
  const bass = m[4] ? LETTER[m[4]] + accOf(m[5]) : root;
  const q = m[3];
  return chordOf(root, bass, ALIAS[q] ?? q.replace(/b/g, "♭").replace(/#/g, "♯"), sym);
}

const SCALE = { major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10] };
const NUMERAL = ["I", "II", "III", "IV", "V", "VI", "VII"];

/** 級數和弦(相對 C 大調 / A 小調的主音 0):vi7、♭VII7、viiø7、V/7、I7/♭7 */
export function parseRoman(tok, mode) {
  const m = /^([♯♭]?)(VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)([^/]*)(?:\/([♯♭]?)([1-7]))?$/.exec(tok.trim());
  if (!m || !SCALE[mode]) throw new Error(`看不懂的級數:「${tok}」(${mode})`);
  const sc = SCALE[mode];
  const lower = m[2] === m[2].toLowerCase();
  let q = m[3].replace("ø7", "m7♭5");
  if (lower && !q.startsWith("m")) q = "m" + q; // 小寫 = 小和弦:vi7 → m7、ii9 → m9
  const root = sc[NUMERAL.indexOf(m[2].toUpperCase())] + accOf(m[1]);
  const bass = m[5] ? sc[+m[5] - 1] + accOf(m[4]) : root;
  return chordOf(root, bass, q, tok);
}

const transpose = (c, k) => ({ ...c, root: mod12(c.root + k), bass: mod12(c.bass + k) });
const tonicOf = mode => (mode === "minor" ? 9 : 0); // 範例用 C 大調 / A 小調寫

/** 進行 → 每小節的和弦陣列;key = 主音往上移幾個半音(0–11) */
export function progressionBars(prog, key = 0, from = "roman") {
  const bars = prog[from].split("|").map(b => b.trim()).filter(Boolean);
  if (!bars.length) throw new Error("沒有和弦");
  return bars.map(bar => bar.split(/\s+/).map(tok =>
    from === "roman"
      ? transpose(parseRoman(tok, prog.mode), tonicOf(prog.mode) + key)
      : transpose(parseChord(tok), key)));
}

// ───────── 風格 ─────────
export function resolveStyle(data, id) {
  const s = data.styles.find(x => x.id === id);
  if (!s) throw new Error(`沒有這個風格:${id}`);
  if (!s.inherits) return s;
  const { inherits, ...own } = s;
  return { ...resolveStyle(data, inherits), ...own };
}

// ───────── 聲位 ─────────
const top = v => v[v.length - 1];
const isDom = c => c.iv[3] === 4 && c.iv[7] === 10;

/** 各聲位類型的排列(距根音的半音,由低到高疊);tiers[0] 是規格寫的,後面是守不住跳進限制時的備案 */
function shapesFor(type, c, next) {
  const t = c.iv, sev = t[7];
  switch (type) {
    case "triad":
      return [[[0, t[3], t[5]], [t[3], t[5], 0], [t[5], 0, t[3]]]];
    case "triad_add9": {
      if (c.quality === "m7♭5") return shapesFor("triad", c, next);
      const n9 = t[9] === 13 ? 13 : 14;
      return [[[t[3], t[5], n9], [t[5], n9, t[3]]], [[n9, t[3], t[5]]]];
    }
    case "shell":
      return [sev != null ? [[t[3], sev], [sev, t[3]]] : [[0, t[3]], [t[3], 0]]];
    case "rootless4": {
      const five = t[13] ?? t[5];
      const seven = sev ?? 0;
      // 九度:有寫照寫;半減和弦不加九度改放根音(自然九度在調外,11 度會把 B 型撐到 20 半音);
      // 屬七往下五度解決到小和弦用 ♭9;其餘自然九度
      const nine = t[9] ?? (c.quality === "m7♭5" ? 12
        : isDom(c) && next && next.root === mod12(c.root + 5) && next.iv[3] === 3 ? 13 : 14);
      const A = [t[3], five, seven, nine], B = [seven, nine, t[3], five];
      return [[A, B], [[five, seven, nine, t[3]], [nine, t[3], five, seven]]];
    }
    default:
      throw new Error(`不支援的聲位類型:${type}`);
  }
}

function stack(shape, root, lo, hi) {
  const out = [], pc0 = mod12(root + shape[0]);
  for (let p = lo; p <= hi; p++) {
    if (mod12(p) !== pc0) continue;
    const v = [p];
    for (let i = 1; i < shape.length; i++) {
      const pc = mod12(root + shape[i]);
      let q = v[i - 1] + 1;
      while (mod12(q) !== pc) q++;
      v.push(q);
    }
    if (top(v) <= hi) out.push(v);
  }
  return out;
}

function movement(a, b) {
  if (a.length === b.length) return a.reduce((s, x, i) => s + Math.abs(x - b[i]), 0);
  const near = (x, ys) => Math.min(...ys.map(y => Math.abs(x - y)));
  return a.reduce((s, x) => s + near(x, b), 0) + b.reduce((s, y) => s + near(y, a), 0);
}

/** 一顆和弦在音域內所有可行的排列;規格寫的排列 pen 0,備案排列 pen 6 */
function candidates(type, c, next, [lo, hi]) {
  return shapesFor(type, c, next).flatMap((shapes, tier) =>
    shapes.flatMap(s => stack(s, c.root, lo, hi)).map(v => ({ v, pen: tier * 6 })));
}

/**
 * 規則 2.2:整串和弦一起挑(Viterbi),總移動最少;
 * 頂音跳進 > 4 半音(段落開頭除外)每多一個半音罰 1000,所以只有真的排不出來才會跳。
 * items: [{ chord, next, range, fresh }]
 */
export function planVoicings(type, items) {
  if (type === "arp5") {
    let prev = null;
    return items.map(it => (prev = arp5(it.chord, prev)));
  }
  const layers = items.map(it => {
    const cs = candidates(type, it.chord, it.next, it.range);
    if (!cs.length) throw new Error(`音域 ${it.range.join("–")} 放不下 ${it.chord.sym}`);
    return cs;
  });
  const leapCost = (a, b, fresh) => {
    const d = Math.abs(top(a) - top(b));
    return fresh || d <= MAX_LEAP ? 0 : 1000 * (d - MAX_LEAP);
  };
  let cost = layers[0].map(x => Math.abs(top(x.v) - (items[0].range[1] - 5)) + x.pen);
  const back = [];
  for (let i = 1; i < layers.length; i++) {
    const from = [];
    cost = layers[i].map(x => {
      let best = Infinity, arg = 0;
      layers[i - 1].forEach((p, j) => {
        const k = cost[j] + movement(x.v, p.v) + x.pen + leapCost(x.v, p.v, items[i].fresh);
        if (k < best) { best = k; arg = j; }
      });
      from.push(arg);
      return best;
    });
    back.push(from);
  }
  let j = cost.indexOf(Math.min(...cost));
  const out = [layers.at(-1)[j].v];
  for (let i = layers.length - 1; i > 0; i--) {
    j = back[i - 1][j];
    out.unshift(layers[i - 1][j].v);
  }
  return out;
}

/**
 * arp5:低音(分割和弦用斜線低音)、5、8、9、10,由低到高。
 * 指型跨 16 半音,43–67 只放得下第一音在 43–51(9 個音);E、F、F♯ 放不進去,
 * 第一音往下借到 40–42(不往上借,上面是旋律區)
 */
function arp5(c, prev) {
  const [lo] = RANGE.arp;
  const cands = [];
  for (let p = lo - 3; p <= lo + 8; p++) if (mod12(p) === c.bass) cands.push(p);
  const want = prev ? prev[0] : lo + 4;
  const n1 = cands.sort((a, b) => Math.abs(a - want) - Math.abs(b - want) || a - b)[0];
  const t = c.iv;
  // 根音參考點:斜線低音下面最近的根音;如果這樣五度會落在低音底下,改用上面那個根音(Am/G → G、E、A、B、C)
  let r0 = n1 - mod12(n1 - c.root);
  if (r0 + t[5] <= n1) r0 += 12;
  const rest = [t[5], 12, t[9] ?? 14, t[3] + 12].map(i => {
    let p = r0 + i;
    while (p <= n1) p += 12;
    while (p > RANGE.arp[1] && p - 12 > n1) p -= 12; // sus 的「10」是 11 度,會頂到 67 以上
    return p;
  });
  return [n1, ...rest.sort((a, b) => a - b)];
}

// ───────── 亂數 ─────────
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ───────── 產生事件 ─────────
const foldBass = p => {
  const [lo, hi] = RANGE.bass;
  while (p > hi) p -= 12;
  while (p < lo) p += 12;
  return p;
};

function densityAt(o, bar) {
  if (o.density !== "auto") return o.density;
  return Math.floor(bar / 8) % 2 === 0 ? "standard" : "high"; // A 段 standard 8 小節 → B 段 high 8 小節
}

/** 一條旋律軌在某個密度的節奏型(沒有就 null) */
const laneOf = (st, track, dens) => st.tracks[track]?.[dens] ?? null;

/**
 * 產生一段伴奏的事件。
 * opt: { progression | chords("C | G/B | Am7 | F G"), key(0–11), bars, density: "auto"|"low"|"standard"|"high",
 *        bpm, swing, seed, humanize, countIn }
 * 回傳 { events, plans, meta };events 依時間排序,plans 是各軌每顆和弦的聲位(驗收 voice leading 用)
 */
export function render(data, styleId, opt = {}) {
  const st = resolveStyle(data, styleId);
  const o = {
    progression: st.progressions[0].id, key: 0, bars: 16, density: "auto",
    bpm: st.bpm.default, swing: st.swing, seed: 1, humanize: true, countIn: true, ...opt,
  };
  const rules = st.rules ?? {};
  let pBars;
  if (o.chords) pBars = progressionBars({ example: o.chords }, o.key, "example"); // 使用者自己輸入(音名)
  else {
    const prog = st.progressions.find(p => p.id === o.progression);
    if (!prog) throw new Error(`${st.id} 沒有這個和弦進行:${o.progression}`);
    pBars = progressionBars(prog, o.key);
  }

  // 和弦格:每小節 1 顆佔滿,2 顆各佔半小節;多排一小節給「下一顆和弦」看
  const slots = [];
  for (let b = 0; b <= o.bars; b++) {
    const chords = pBars[b % pBars.length];
    if (chords.length > 2) throw new Error(`一小節最多兩顆和弦:${chords.map(c => c.sym).join(" ")}`);
    const w = CELLS / chords.length;
    chords.forEach((c, i) => slots.push({ bar: b, from: i * w, to: (i + 1) * w, chord: c }));
  }
  const slotAt = (bar, cell) => slots.findIndex(s => s.bar === bar && cell >= s.from && cell < s.to);
  const nextOf = i => slots[Math.min(i + 1, slots.length - 1)];

  // 各軌聲位計畫
  const plans = {};
  const plan = (type, range, lowCap) => {
    const items = slots.map((s, i) => ({
      chord: s.chord, next: nextOf(i).chord,
      range: lowCap && densityAt(o, s.bar) === "low" ? [range[0], Math.min(range[1], RANGE.lowKeysMax)] : range,
      fresh: s.from === 0 && s.bar % 8 === 0,
    }));
    return planVoicings(type, items).map((notes, i) => ({ bar: slots[i].bar, from: slots[i].from, notes, fresh: items[i].fresh }));
  };
  const kType = st.voicing.keys;
  const kRange = st.ranges?.keys ?? (kType === "arp5" ? RANGE.arp : RANGE.keys);
  if (st.tracks.keys || st.tracks.guitar) {
    plans.keys = plan(kType, kRange, true);
    plans.keysShell = plan("shell", kRange, true);
  }
  if (st.tracks.keys2) plans.keys2 = plan(st.voicing.keys2, RANGE.keys, true);
  if (st.tracks.pad) plans.pad = plan(st.voicing.pad, st.ranges?.pad ?? RANGE.pad, false);

  // 貝斯根音:優先 31–43、離上一顆近;這小節要彈 8 就挑彈得到高八度的那個八度
  let prevR = null;
  const bassR = slots.map(s => {
    const lane = laneOf(st, "bass", densityAt(o, s.bar));
    const needs8 = lane ? cells(lane).includes("8") : false;
    const cands = [];
    for (let p = RANGE.bass[0]; p <= RANGE.bass[1]; p++) if (mod12(p) === s.chord.bass) cands.push(p);
    const cost = p => (needs8 && p + 12 > RANGE.bass[1] ? 100 : 0)
      + (p < RANGE.bassRoot[0] || p > RANGE.bassRoot[1] ? 10 : 0)
      + Math.abs(p - (prevR ?? 36)) * 0.1;
    prevR = cands.sort((a, b) => cost(a) - cost(b) || a - b)[0];
    return prevR;
  });

  // 時間:第幾格 → 秒;swing 只動奇數格
  const cellSec = 60 / o.bpm / 4;
  const offsetBars = o.countIn ? 1 : 0;
  const gridAt = (bar, cell) => {
    const abs = (bar + offsetBars) * CELLS + cell;
    const whole = Math.floor(abs), frac = abs - whole;
    const at = n => (n % 2 ? (n - 1) * cellSec + 2 * cellSec * o.swing / 100 : n * cellSec);
    return at(whole) + frac * (at(whole + 1) - at(whole));
  };

  const events = [];
  const push = e => events.push(e);
  const note = (track, bar, cell, len, notes, extra = {}) => {
    const t0 = gridAt(bar, cell);
    push({ track, bar, cell, gridTime: t0, dur: gridAt(bar, cell + len) - t0, cells: len,
      notes, vel: TRACK_VEL[track], dens: densityAt(o, bar), ...extra });
  };
  const hit = (piece, bar, cell, vel, sub = 0, acc = 1) => {
    const t0 = gridAt(bar, cell + sub / 2);
    push({ track: "drums", piece, bar, cell, sub, gridTime: t0, dur: cellSec / (sub ? 2 : 1), vel, acc });
  };

  // 預備拍:hi-hat 四下四分音符
  if (o.countIn) for (let c = 0; c < CELLS; c += 4) hit("hat", -1, c, DRUM_VEL.x);

  const fillOn = dens => !rules.fillDensities || rules.fillDensities.includes(dens);
  const carry = {}; // N 延到下一小節:carry[track] = 被吃掉的那一小節
  let lastBass = null;

  // 每小節的變化(資料:styles/feel.json,由 Groove MIDI / POP909 統計而來)
  const hz = st.humanize ?? {};
  const F = o.feel ?? data.feel?.styles?.[st.id] ?? null;
  const vary = o.vary !== false && F;
  const vrng = mulberry32((o.seed ^ 0x5bd1e995) >>> 0);
  const progScale = Math.min(1, (hz.timingSigmaMs ?? 6) / 6); // 程式打的曲風(K-pop 舞曲)變化少
  const kickAdds = {};
  const pushAt = {};
  if (vary && F.keys?.anticipation && st.voicing.keys !== "arp5") {
    const A = F.keys.anticipation, at = CELLS - Math.max(1, Math.round(A.beatsEarly * 4 / 2) * 2);
    for (let b = 0; b + 1 < o.bars; b++) {
      if (b % 8 === 7) continue; // 過門小節不搶
      const cur = laneOf(st, "keys", densityAt(o, b)), nx = laneOf(st, "keys", densityAt(o, b + 1));
      if (!cur || !nx || !"CSU".includes(cells(nx)[0])) continue;
      const tail = cells(cur).slice(at);
      if (![...tail].every(ch => ch === "." || ch === "-")) continue;
      // 樂句加權:Groove MIDI 鼓手在第幾小節最常變化(各鼓件平均),第 4 小節最常推進下一句
      const ph = Object.values(F.drums.phrase).reduce((a, w) => a + w[b % 4], 0) / Object.keys(F.drums.phrase).length;
      if (vrng() < A.rate * VARY_SCALE * DENS_VARY[densityAt(o, b)] * ph) pushAt[b] = at;
    }
  }

  for (let b = 0; b < o.bars; b++) {
    const dens = densityAt(o, b);

    // 鼓
    const kit = st.tracks.drums?.[dens];
    if (kit) {
      const lanes = Object.fromEntries(Object.entries(kit).map(([k, v]) => [k, cells(v)]));
      if (b % 8 === 7 && st.tracks.drums.fill && fillOn(dens))
        for (const [piece, f] of Object.entries(st.tracks.drums.fill))
          lanes[piece] = (lanes[piece] ?? ".".repeat(CELLS)).slice(0, FILL_CELLS) + cells(f);
      if (b % 8 === 0 && rules.crashOnSection !== false) hit("crash", b, 0, DRUM_VEL.X);
      if (vary && b % 8 !== 7) kickAdds[b] = varyDrums(lanes, b, dens);
      for (const [piece, s] of Object.entries(lanes)) {
        // 資料的強弱只在「同一種符號」之間分(規格的 X / x / o 層級保留,不重複壓)
        const A = F?.drums.accent[piece === "clap" ? "snare" : piece];
        const mean = {};
        if (A) for (const sym of new Set(s)) {
          const cs = [...s].map((ch, c) => (ch === sym ? A[c] : null)).filter(x => x != null);
          mean[sym] = cs.reduce((a, x) => a + x, 0) / cs.length;
        }
        [...s].forEach((ch, c) => {
          const acc = A ? A[c] / mean[ch] : 1;
          if (ch === "r") DRUM_VEL.r.forEach((v, k) => hit(piece, b, c, v, k, acc));
          else if (DRUM_VEL[ch]) hit(piece, b, c, DRUM_VEL[ch], 0, acc);
        });
      }
    }

    // 旋律軌
    for (const track of MELODIC) {
      const lane = laneOf(st, track, dens);
      if (!lane) continue;
      let s = cells(lane);
      if (track === "keys" && pushAt[b] != null) // 搶拍:下一顆和弦提早一個八分音符進來
        s = s.slice(0, pushAt[b]) + "N" + "-".repeat(CELLS - pushAt[b] - 1);
      if (track === "bass" && kickAdds[b]?.length) { // 鼓手多踩的大鼓,貝斯跟著彈根音
        const arr = [...s];
        for (const c of kickAdds[b]) if (arr[c] === ".") arr[c] = "R";
        s = arr.join("");
      }
      for (let c = 0; c < CELLS; c++) {
        const ch = s[c];
        if (ch === "-" || ch === ".") continue;
        let len = 1;
        while (c + len < CELLS && s[c + len] === "-") len++;
        if (c === 0 && carry[track] === b) continue; // 被上一小節的 N 吃掉
        const si = slotAt(b, c);

        if (track === "bass") {
          const emit = (cell, n, idx) => {
            const R = bassR[idx], chd = slots[idx].chord;
            let p;
            if (ch === "R") p = R;
            else if (ch === "8") p = R + 12;
            else if (ch === "A") {
              const nr = bassR[idx + 1] ?? R, from = lastBass ?? R;
              p = [nr - 1, nr + 1].sort((x, y) => Math.abs(x - from) - Math.abs(y - from) || x - y)[0];
            } else {
              const iv = ch === "7" ? (chd.iv[7] ?? 10) : chd.iv[+ch];
              p = R + mod12(chd.root + iv - R);
            }
            p = foldBass(p);
            lastBass = p;
            note("bass", b, cell, n, [p]);
          };
          if (ch === "A") emit(c, len, si);
          else splitBySlot(b, c, len, emit);
          continue;
        }

        if (ch === "N") {
          let n = CELLS - c;
          const nx = b + 1 < o.bars ? laneOf(st, track, densityAt(o, b + 1)) : null;
          if (nx && !"-.".includes(cells(nx)[0])) {
            let k = 1;
            while (k < CELLS && cells(nx)[k] === "-") k++;
            n += k;
          }
          const held = capKeys(track, n);
          if (held > CELLS - c) carry[track] = b + 1; // 真的延進下一小節才吃掉那一下
          note(track, b, c, held, plans.keys[si + 1].notes, { symbol: pushAt[b] === c && track === "keys" ? "push" : "N" });
          continue;
        }
        if (ch === "P") {
          const nv = plans[track === "keys2" ? "keys2" : "keys"][si + 1].notes;
          const hi = dens === "low" ? RANGE.lowKeysMax : kRange[1];
          const d = top(nv) + 1 <= hi ? 1 : -1;
          note(track, b, c, 1, nv.map(p => p + d), { symbol: "P" });
          continue;
        }
        splitBySlot(b, c, len, (cell, n, idx) => {
          const pl = track === "guitar" ? plans.keys : plans[track];
          const v = pl[idx].notes;
          let notes;
          if (track === "guitar" && st.tracks.guitar.voicing === "power") {
            // power chord:根音、五度、八度,根音放在吉他低音區 40–51(E2–D♯3)
            const c = slots[idx].chord, r = 40 + mod12(c.root - 40);
            notes = [r, r + 7, r + 12];
          } else if (track === "guitar") notes = v.slice(-(st.tracks.guitar.topNotes ?? 2));
          else if (ch === "C") notes = v;
          else if (ch === "S") notes = plans.keysShell[idx].notes;
          else if (ch === "U") notes = v.slice(-3);
          else notes = [v[Math.min(+ch, v.length) - 1]];
          note(track, b, cell, capKeys(track, n), notes, { symbol: ch });
        });
      }
    }
  }

  // 延音碰到換和弦就斷開,新和弦在換的那一格重新彈
  function splitBySlot(bar, c, len, emit) {
    let start = c, idx = slotAt(bar, c);
    for (let k = c + 1; k <= c + len; k++) {
      const j = k < c + len ? slotAt(bar, k) : -1;
      if (j !== idx) {
        emit(start, k - start, idx);
        start = k;
        idx = j;
      }
    }
  }
  function capKeys(track, n) {
    return track === "keys" && rules.keysMaxCells ? Math.min(n, rules.keysMaxCells) : n;
  }

  /**
   * 鼓的每小節變化:照 Groove MIDI 同曲風的真人鼓手,在哪些位置常多打、常省略(feel.drums.add / drop),
   * 依樂句第幾小節加權(phrase)。大鼓第一拍、小鼓 2 4 拍、重音 X 不動。回傳多踩的大鼓位置(貝斯跟著彈)
   */
  function varyDrums(lanes, b, dens) {
    const D = F.drums, scale = DENS_VARY[dens] * progScale, adds = [];
    const keep = (pc, c, ch) => ch === "X" || ch === "r" || (pc === "kick" && c === 0) ||
      (["snare", "clap", "rim"].includes(pc) && (c === 4 || c === 12));
    for (const [pc, s0] of Object.entries(lanes)) {
      const key = pc === "clap" ? "snare" : pc;
      if (!D.add[key] || pc === "openhat") continue;
      const ph = D.phrase[key]?.[b % 4] ?? 1, arr = [...s0];
      for (let c = 0; c < CELLS; c++) {
        const r = vrng();
        if (arr[c] === ".") {
          if (r < D.add[key][c] * scale * ph) {
            arr[c] = key === "snare" ? "o" : D.accent[key][c] >= 0.8 ? "x" : "o";
            if (pc === "kick") adds.push(c);
          }
        } else if (!keep(pc, c, arr[c]) && r < D.drop[key][c] * scale * ph) arr[c] = ".";
      }
      lanes[pc] = arr.join("");
    }
    // 開放 hi-hat:換掉那一下閉合的(只在有 hi-hat 的段落)
    if (lanes.hat && D.add.openhat) {
      const oh = [...(lanes.openhat ?? ".".repeat(CELLS))], hh = [...lanes.hat];
      const ph = D.phrase.openhat?.[b % 4] ?? 1;
      for (let c = 0; c < CELLS; c++)
        if (hh[c] !== "." && oh[c] === "." && vrng() < D.add.openhat[c] * scale * ph) { oh[c] = "x"; hh[c] = "."; }
      lanes.openhat = oh.join(""); lanes.hat = hh.join("");
    }
    return adds;
  }

  /*
   * 人性化(取代規格 2.6 的「每一下獨立高斯 + 力度均勻亂數」):
   * - 整團一起飄:每小節一個共同偏移,AR(1)(feel.drums.drift),所有樂器共用,不會彼此打架
   * - 每個位置的系統偏差與強弱:鼓照 Groove MIDI(sysRel / accent),鍵盤照 POP909,貝斯跟大鼓
   * - 每一下自己的抖動:各鼓件的比例照資料,整體大小錨在規格的 σ(timingSigmaMs)
   * - 和弦不同時落下(POP909 spread),頂音較大聲;吉他照 GuitarSet 下刷 / 上刷的先後
   * 有 swing 的曲風,奇數格的系統偏差交給 swing,不重複加
   */
  const rnd = mulberry32(o.seed);
  const gauss = () => {
    const u = 1 - rnd(), v = rnd();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  const clampMs = (x, cap = HUMANIZE_CAP_MS) => Math.max(-cap, Math.min(cap, x));
  const K0 = hz.timingSigmaMs ?? 6;
  const DR = F?.drums;
  const drift = new Map();
  {
    const phi = DR?.drift.phi ?? 0, sd = (DR?.drift.sdRel ?? 0) * K0;
    let d = 0;
    for (let b = -1; b <= o.bars; b++) {
      d = phi * d + Math.sqrt(1 - phi * phi) * gauss() * sd;
      drift.set(b, clampMs(d));
    }
  }
  const KEYS_LIKE = ["keys", "keys2", "pad", "guitar"];
  for (const e of events) {
    const ov = hz.overrides?.[e.piece ?? e.track] ?? {};
    const vr = ov.velocityRand ?? hz.velocityRand ?? 8;
    if (!o.humanize) { e.time = e.gridTime; continue; }
    const k = ov.timingSigmaMs ?? K0;
    const odd = e.cell % 2 === 1 && o.swing > 50;
    let sys = 0, jit = 1, acc = 1;
    const dk = e.track === "drums" ? (e.piece === "clap" ? "snare" : e.piece) : e.track === "bass" ? "kick" : null;
    if (DR && dk && DR.jitterRel[dk] != null) {
      jit = DR.jitterRel[dk];
      sys = odd ? 0 : DR.sysRel[dk][e.cell] * K0;
      acc = e.track === "drums" ? e.acc ?? 1 : DR.accent.hat ? DR.accent.hat[e.cell] ** 0.5 : 1;
    } else if (F?.keys && KEYS_LIKE.includes(e.track)) {
      sys = odd ? 0 : F.keys.sysRel[e.cell] * K0;
      acc = e.track === "pad" ? 1 : F.keys.accent[e.cell] ** 0.6;
    }
    const j = drift.get(e.bar) + sys + clampMs(gauss() * jit * k) + (ov.offsetMs ?? 0);
    e.time = Math.max(0, e.gridTime + j / 1000);
    e.vel = Math.max(1, Math.min(127, Math.round(e.vel * acc + clampMs(gauss() * vr / 2, vr))));
    // 和弦裡各音的先後與頂音
    if (e.notes && e.notes.length > 1 && F) {
      const n = e.notes.length;
      let dt, lowFirst;
      if (e.track === "guitar" && F.guitar) {
        lowFirst = e.cell % 2 === 0; // 偶數格下刷(低弦先)、奇數格上刷
        dt = (F.guitar.spreadMs.median / 5) * (0.6 + 0.8 * rnd());
      } else if (e.track !== "pad" && F.keys) {
        lowFirst = rnd() < F.keys.lowFirstShare;
        dt = (F.keys.spreadMs.median / (n - 1)) * (0.5 + rnd());
      } else continue;
      const order = e.notes.map((p, i) => i).sort((a, b) => (lowFirst ? e.notes[a] - e.notes[b] : e.notes[b] - e.notes[a]));
      e.noteDt = e.notes.map(() => 0);
      order.forEach((i, r) => { e.noteDt[i] = (r * dt) / 1000; });
      const topI = e.notes.indexOf(Math.max(...e.notes));
      e.noteVel = e.notes.map((p, i) => Math.max(1, Math.min(127, e.vel + (i === topI ? (F.keys?.topVel ?? 0) : 0))));
    }
  }
  events.sort((a, b) => a.gridTime - b.gridTime);

  return { events, plans, meta: { style: st.id, ...o, cellSec, barSec: cellSec * CELLS } };
}
