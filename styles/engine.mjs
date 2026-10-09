// BackingTrack 風格引擎(規格書 v1):styles.json → 音符事件。
// 只產生事件(時間、音高、力度),不發聲;瀏覽器與 Node 都能 import。
// 不用內建亂數:人性化走 mulberry32 固定種子,同一個 seed 一定產生同一組事件。

export const CELLS = 16;      // 4/4 一小節的格數(規格的節奏型)
export const FILL_CELLS = 8;
/**
 * 拍號:一小節幾格(十六分)、一拍幾格、兩顆和弦怎麼分。
 * 3/4 兩顆和弦 = 2 拍 + 1 拍(舊網頁 spansOf 的規則:前面拿多的);6/8 = 兩個附點四分各一顆;6/8 不搖擺
 */
export const METERS = {
  "4/4": { cells: 16, beat: 4, split: [8, 8] },
  "3/4": { cells: 12, beat: 4, split: [8, 4] },
  "6/8": { cells: 12, beat: 6, split: [6, 6], straight: true },
};
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

/**
 * 從音程集合建和弦(主網頁的解析器有 134 種拼法,轉過來用):intervals = 距根音的半音(可含 14、21 這種延伸音)
 * 三度:有 4 用 4、有 3 用 3,都沒有就是 sus(5 或 2);五度 7 / 6 / 8;七度 10 / 11 / 9(減七);九度 14 / 13 / 15;十三度 21(6 和弦的 9 也算)
 */
export function chordFromIntervals(root, bass, intervals, sym = "") {
  const has = i => intervals.some(x => mod12(x) === mod12(i));
  const iv = {};
  iv[3] = has(4) ? 4 : has(3) ? 3 : has(5) ? 5 : has(2) ? 2 : 7; // 沒有三度(C5、no3):維持空五度,不要自己補大三度
  iv[5] = has(7) ? 7 : has(6) && !has(4) ? 6 : has(8) ? 8 : has(6) ? 6 : 7;
  if (has(10)) iv[7] = 10; else if (has(11)) iv[7] = 11; else if (has(9) && iv[3] === 3 && iv[5] === 6) iv[7] = 9;
  if (intervals.some(x => x >= 12)) {
    if (has(13)) iv[9] = 13; else if (has(15) && iv[3] === 4) iv[9] = 15; else if (has(2) && iv[3] !== 2) iv[9] = 14;
  }
  if (has(9) && iv[7] !== 9) iv[13] = 9 + (intervals.some(x => x === 21) ? 12 : 0);
  const quality = iv[3] === 3 && iv[5] === 6 && iv[7] === 10 ? "m7♭5" : sym;
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
      // 九度留在中間當色彩,頂音一定是和弦音(Steven 2026-10-09:「思考 9 音在上面的必要性,拿掉可能更好」)
      // 備案:沒有九度的三和弦第一轉位(頂音根音)
      return [[[n9, t[3], t[5]], [t[5], n9, t[3]]], [[t[3], t[5], 12]]];
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
      // 頂音不放九度(九度留在中間):B 型頂音五度、另一個轉位頂音七度;備案頂音三度
      const B = [seven, nine, t[3], five];
      return [[B, [nine, t[3], five, seven]], [[five, seven, nine, t[3]]]];
    }
    case "arp_rh": {
      // 分解和弦的右手:和弦音(有七度用 3、5、7,沒有用 1、3、5)的三個轉位,只用和弦音
      const tri = sev != null ? [t[3], t[5], sev] : [0, t[3], t[5]]; // 不用十三度(旋律只用和弦音那條還待 Steven 決定)
      return [[tri, [tri[1], tri[2], tri[0]], [tri[2], tri[0], tri[1]]]];
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
  if (type === "arp_inv") return arpInv(items);
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

/**
 * arp_inv(Steven 2026-10-08:「分解和弦應該找近的位置(轉位,而不是跟著和弦名稱彈原位),而且有 bass 撐住彈低音」):
 *   [左手低音, 低音高八度 + 右手三個和弦音(由低到高)]
 * 左手:和弦的低音(斜線和弦就是斜線那個音,和弦名稱不變),36–47 裡離上一顆最近,換和弦時重彈、踩著撐到換和弦
 * 右手:跟方塊和弦同一套 Viterbi,挑離上一顆最近的轉位(55–69),只用和弦音
 * 指型的 1–5 = 這五個音
 */
const RH_OF = new WeakMap();
function arpInv(items) {
  const rh = planVoicings("arp_rh", items.map(it => ({ ...it, range: [55, 69] })));
  let prevL = 40;
  return items.map((it, i) => {
    const cands = [];
    for (let p = 36; p <= 47; p++) if (mod12(p) === it.chord.bass) cands.push(p);
    const lh = cands.sort((a, b) => Math.abs(a - prevL) - Math.abs(b - prevL) || a - b)[0];
    prevL = lh;
    const r = [...rh[i]].sort((a, b) => a - b);
    RH_OF.set(it, r);
    // 第五個音:左手低音的高八度(抒情鋼琴常見的 1–8–和弦音);右手的頂音就一直是那三個和弦音裡最高的,走向穩
    // 跟右手撞同一個音(指型會原地重敲)就改用左手低音與右手最低音之間、最高的那個和弦音
    let oct = lh + 12;
    if (r.includes(oct)) {
      const pcs = new Set(r.map(mod12).concat(mod12(lh)));
      oct = null;
      for (let p = r[0] - 1; p > lh; p--) if (pcs.has(mod12(p)) && !r.includes(p)) { oct = p; break; }
      oct ??= lh + 7; // 左手與右手之間放不下和弦音(實際不會發生:兩手至少差 8 半音)
    }
    return [lh, ...[...r, oct].sort((a, b) => a - b)];
  });
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
  if (o.densities) return o.densities[Math.min(bar, o.densities.length - 1)] ?? "standard"; // 每小節自己指定(主網頁的鋪 / 伴 / 推)
  if (o.density !== "auto") return o.density;
  return Math.floor(bar / 8) % 2 === 0 ? "standard" : "high"; // A 段 standard 8 小節 → B 段 high 8 小節
}

/** 一條旋律軌在某個密度的節奏型(沒有就 null) */
const laneOf = (T, track, dens) => T[track]?.[dens] ?? null;

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
  const meterKey = o.meter ?? "4/4";
  const base = o.barBase ?? 0; // 這一段第一小節是整首的第幾小節(過門、段落、樂句位置用)
  const MT = METERS[meterKey];
  if (!MT) throw new Error(`不支援的拍號:${meterKey}`);
  const BAR = MT.cells;
  // 這個拍號的節奏型:4/4 在 tracks,其他拍號在 meters[拍號].tracks;沒寫就是這個曲風不打這個拍號
  const T = meterKey === "4/4" ? st.tracks : st.meters?.[meterKey]?.tracks;
  if (!T) throw new Error(`${st.name?.zh ?? st.id} 沒有 ${meterKey} 拍`);
  if (MT.straight) o.swing = 50;
  const rules = st.rules ?? {};
  let pBars;
  if (o.barSpans) pBars = null; // 主網頁:每小節的和弦與位置(格)直接給
  else if (o.chords) pBars = progressionBars({ example: o.chords }, o.key, "example"); // 使用者自己輸入(音名)
  else {
    const prog = st.progressions.find(p => p.id === o.progression);
    if (!prog) throw new Error(`${st.id} 沒有這個和弦進行:${o.progression}`);
    pBars = progressionBars(prog, o.key);
  }

  // 和弦格:每小節 1 顆佔滿,2 顆依拍號分;多排一小節給「下一顆和弦」看
  const slots = [];
  for (let b = 0; b <= o.bars; b++) {
    if (o.barSpans) {
      const bar = o.barSpans[b % o.barSpans.length];
      for (const sp of bar) slots.push({ bar: b, from: sp.from, to: sp.to, chord: sp.chord });
      continue;
    }
    const chords = pBars[b % pBars.length];
    if (chords.length > 2) throw new Error(`一小節最多兩顆和弦:${chords.map(c => c.sym).join(" ")}`);
    const ws = chords.length === 1 ? [BAR] : MT.split;
    let at = 0;
    chords.forEach((c, i) => { slots.push({ bar: b, from: at, to: at + ws[i], chord: c }); at += ws[i]; });
  }
  const slotAt = (bar, cell) => slots.findIndex(s => s.bar === bar && cell >= s.from && cell < s.to);
  const nextOf = i => slots[Math.min(i + 1, slots.length - 1)];

  // 各軌聲位計畫
  const plans = {};
  const plan = (type, range, lowCap) => {
    const items = slots.map((s, i) => ({
      chord: s.chord, next: nextOf(i).chord,
      range: lowCap && densityAt(o, s.bar) === "low" ? [range[0], Math.min(range[1], RANGE.lowKeysMax)] : range,
      fresh: s.from === 0 && (s.bar + base) % 8 === 0,
    }));
    return planVoicings(type, items).map((notes, i) => ({ bar: slots[i].bar, from: slots[i].from, notes, fresh: items[i].fresh, chord: slots[i].chord,
      ...(RH_OF.has(items[i]) ? { rh: RH_OF.get(items[i]) } : {}) }));
  };
  const kType = st.voicing.keys;
  // 分解和弦(arp_inv)一律踩延音踏板(Steven 2026-10-08:「音跟音之間斷掉了」)
  const PEDAL = kType === "arp_inv";
  const kRange = st.ranges?.keys ?? (kType === "arp5" || kType === "arp_inv" ? RANGE.arp : RANGE.keys);
  if (T.keys || T.guitar) {
    plans.keys = plan(kType, kRange, true);
    plans.keysShell = plan("shell", kRange, true);
  }
  if (T.keys2) plans.keys2 = plan(st.voicing.keys2, RANGE.keys, true);
  if (T.pad) plans.pad = plan(st.voicing.pad, st.ranges?.pad ?? RANGE.pad, false);

  // 貝斯根音:優先 31–43、離上一顆近;這小節要彈 8 就挑彈得到高八度的那個八度
  let prevR = null;
  const bassR = slots.map(s => {
    const lane = laneOf(T, "bass", densityAt(o, s.bar));
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
    const abs = (bar + offsetBars) * BAR + cell;
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
  if (o.countIn) for (let c = 0; c < BAR; c += MT.beat) hit("hat", -1, c, DRUM_VEL.x);

  const fillOn = dens => !rules.fillDensities || rules.fillDensities.includes(dens);
  const carry = {}; // N 延到下一小節:carry[track] = 被吃掉的那一小節
  let lastBass = null;

  // 每小節的變化(資料:styles/feel.json,由 Groove MIDI / POP909 統計而來)
  const hz = st.humanize ?? {};
  // 彈法資料:4/4 用曲風自己的;3/4、6/8 用 Groove MIDI 三拍段落的統計(資料少,鍵盤沒有三拍資料就不分強弱、不搶拍)
  const F0 = o.feel ?? data.feel?.styles?.[st.id] ?? null;
  const F = !F0 || meterKey === "4/4" ? F0
    : F0.meters?.[meterKey] ? { ...F0, drums: F0.meters[meterKey].drums, keys: { ...F0.keys, accent: null, anticipation: null } } : null;
  const vary = o.vary !== false && F;
  const vrng = mulberry32((o.seed ^ 0x5bd1e995) >>> 0);
  const progScale = Math.min(1, (hz.timingSigmaMs ?? 6) / 6); // 程式打的曲風(K-pop 舞曲)變化少
  /*
   * 真人鋼琴伴奏庫(feel.json 的 keys.lib,tools/feel/pop909_patterns.py 從 POP909 878 首、68838 小節萃取;
   * Steven 2026-10-09:「鋼琴節奏型態太單調」「不要只是換個和弦複製貼上一樣的節奏型態」):
   * 真人下一小節整個一樣只有 2.4%、節奏(哪幾格有音)一樣 28%。所以每小節:
   *   節奏:28% 沿用上一小節的節奏,否則照資料的權重重抽;樂句第 4 小節照句尾的統計抽
   *   內容:同一個節奏底下真人彈過的組合裡抽(左手 L 低音 / l5 五度 / l8 八度 / l3 十度、右手 B 柱式 / r1–r4 第幾個音)
   *   音高:左手照 arp_inv 的低音,右手照 Viterbi 挑好的最近轉位;一律踩踏板(PEDAL)
   * 只用在 4/4、聲位是 arp_inv 的曲風(POP909 是華語流行,只有 4/4)
   */
  const LIB = kType === "arp_inv" && meterKey === "4/4" && F?.keys?.lib ? F.keys.lib : null;
  const libRng = mulberry32(((o.seed ?? 1) * 2654435761 + base * 97) >>> 0);
  let libPrev = null;
  const pickW = (arr, w) => { let t = arr.reduce((a, x) => a + w(x), 0) * libRng(); for (const x of arr) { t -= w(x); if (t <= 0) return x; } return arr[arr.length - 1]; };
  function libBar(b, dens) {
    const D = LIB.dens[dens] ?? LIB.dens.standard;
    const phraseEnd = (b + base) % 4 === 3;
    let mask;
    if (phraseEnd && D.end?.length && libRng() < 0.6) mask = pickW(D.end, x => x[1])[0];
    else if (libPrev && libPrev.dens === dens && libRng() < LIB.repeatRhythm) mask = libPrev.mask;
    else mask = pickW(D.masks, x => x.w).m;
    const M = D.masks.find(x => x.m === mask) ?? D.masks[0];
    const pat = pickW(M.pats, x => x[1])[0].split(" ");
    libPrev = { dens, mask: M.m };
    for (let c = 0; c < BAR; c++) {
      const idx = slotAt(b, c);
      if (idx < 0) continue;
      const pl = plans.keys[idx], sl = slots[idx];
      const lh = pl.notes[0], rh = pl.rh ?? pl.notes.slice(1, 4);
      const rhs = [...rh].sort((x, y) => x - y);
      const third = (() => { const t3 = sl.chord.iv[3]; if (t3 == null) return lh + 12; let p = lh + 12; while (mod12(p) !== mod12(sl.chord.root + t3)) p++; return p; })();
      const toks = pat[c] === "." ? [] : pat[c].split("+");
      if (c === sl.from && !toks.includes("L")) toks.push("L");       // 換和弦那一格一定有左手低音
      const notes = new Set();
      for (const tk of toks) {
        if (tk === "L") notes.add(lh);
        else if (tk === "l5") notes.add(lh + 7);
        else if (tk === "l8" || tk === "lx") notes.add(lh + 12);
        else if (tk === "l3") notes.add(third);
        else if (tk === "B") rhs.forEach(p => notes.add(p));
        else if (tk[0] === "r") { const k = +tk.slice(1); notes.add(k <= rhs.length ? rhs[k - 1] : rhs[0] + 12 <= 69 ? rhs[0] + 12 : rhs[rhs.length - 1]); }
      }
      for (const p of notes) note("keys", b, c, sl.to - c, [p], { symbol: "lib", pedal: true });
    }
  }

  const kickAdds = {};
  const pushAt = {};
  if (vary && F.keys?.anticipation && !st.voicing.keys.startsWith("arp")) {
    const A = F.keys.anticipation, at = BAR - Math.max(1, Math.round(A.beatsEarly * 4 / 2) * 2);
    for (let b = 0; b + 1 < o.bars; b++) {
      if ((b + base) % 8 === 7) continue; // 過門小節不搶
      const cur = laneOf(T, "keys", densityAt(o, b)), nx = laneOf(T, "keys", densityAt(o, b + 1));
      if (!cur || !nx || !"CSU".includes(cells(nx)[0])) continue;
      const tail = cells(cur).slice(at);
      if (![...tail].every(ch => ch === "." || ch === "-")) continue;
      // 樂句加權:Groove MIDI 鼓手在第幾小節最常變化(各鼓件平均),第 4 小節最常推進下一句
      const ph = Object.values(F.drums.phrase).reduce((a, w) => a + w[(b + base) % 4], 0) / Object.keys(F.drums.phrase).length;
      if (vrng() < A.rate * VARY_SCALE * DENS_VARY[densityAt(o, b)] * ph) pushAt[b] = at;
    }
  }

  for (let b = 0; b < o.bars; b++) {
    const dens = densityAt(o, b);

    // 鼓
    const kit = T.drums?.[dens];
    if (kit) {
      const lanes = Object.fromEntries(Object.entries(kit).map(([k, v]) => [k, cells(v)]));
      if ((b + base) % 8 === 7 && T.drums.fill && fillOn(dens))
        for (const [piece, f] of Object.entries(T.drums.fill))
          lanes[piece] = (lanes[piece] ?? ".".repeat(BAR)).slice(0, BAR / 2) + cells(f);
      if ((b + base) % 8 === 0 && rules.crashOnSection !== false) hit("crash", b, 0, DRUM_VEL.X);
      if (vary && (b + base) % 8 !== 7) kickAdds[b] = varyDrums(lanes, b, dens);
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
      const lane = laneOf(T, track, dens);
      if (!lane) continue;
      if (track === "keys" && LIB) { libBar(b, dens); continue; }
      let s = cells(lane);
      if (track === "keys" && pushAt[b] != null) // 搶拍:下一顆和弦提早一個八分音符進來
        s = s.slice(0, pushAt[b]) + "N" + "-".repeat(BAR - pushAt[b] - 1);
      if (track === "bass" && kickAdds[b]?.length) { // 鼓手多踩的大鼓,貝斯跟著彈根音
        const arr = [...s];
        for (const c of kickAdds[b]) if (arr[c] === ".") arr[c] = "R";
        s = arr.join("");
      }
      for (let c = 0; c < BAR; c++) {
        const ch = s[c];
        if (ch === "-" || ch === ".") continue;
        let len = 1;
        while (c + len < BAR && s[c + len] === "-") len++;
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
          let n = BAR - c;
          const nx = b + 1 < o.bars ? laneOf(T, track, densityAt(o, b + 1)) : null;
          if (nx && !"-.".includes(cells(nx)[0])) {
            let k = 1;
            while (k < BAR && cells(nx)[k] === "-") k++;
            n += k;
          }
          const held = capKeys(track, n);
          if (held > BAR - c) carry[track] = b + 1; // 真的延進下一小節才吃掉那一下
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
          if (track === "guitar" && T.guitar.voicing === "power") {
            // power chord:根音、五度、八度,根音放在吉他低音區 40–51(E2–D♯3)
            const c = slots[idx].chord, r = 40 + mod12(c.root - 40);
            notes = [r, r + 7, r + 12];
          } else if (track === "guitar") notes = v.slice(-(T.guitar.topNotes ?? 2));
          else if (ch === "C") notes = v;
          else if (ch === "S") notes = plans.keysShell[idx].notes;
          else if (ch === "U") notes = v.slice(-3);
          else notes = [v[Math.min(+ch, v.length) - 1]];
          if (PEDAL && track === "keys") {
            // 踩著延音踏板:每個音撐到換和弦;換和弦的那一格左手低音一定要彈(指型那一格不是 1 也補上)
            const sl = slots[idx];
            if (cell === sl.from && !notes.includes(v[0])) notes = [v[0], ...notes];
            // 每個音各自一個事件:同音重彈時只停那一個音(左手低音不會被右手重彈連帶停掉)
            for (const p of notes) note(track, b, cell, sl.to - cell, [p], { symbol: ch, pedal: true });
          } else note(track, b, cell, capKeys(track, n), notes, { symbol: ch });
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
      const ph = D.phrase[key]?.[(b + base) % 4] ?? 1, arr = [...s0];
      for (let c = 0; c < BAR; c++) {
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
      const oh = [...(lanes.openhat ?? ".".repeat(BAR))], hh = [...lanes.hat];
      const ph = D.phrase.openhat?.[(b + base) % 4] ?? 1;
      for (let c = 0; c < BAR; c++)
        if (hh[c] !== "." && oh[c] === "." && vrng() < D.add.openhat[c] * scale * ph) { oh[c] = "x"; hh[c] = "."; }
      lanes.openhat = oh.join(""); lanes.hat = hh.join("");
    }
    return adds;
  }

  // 踏板下同一個音再彈:前一顆在新的那一下停(真的鋼琴是同一根弦重敲,不會兩顆疊在一起越來越大聲)
  if (PEDAL) {
    const ks = events.filter(e => e.pedal).sort((a, b) => a.gridTime - b.gridTime);
    for (let i = 0; i < ks.length; i++) {
      const e = ks[i], end = e.gridTime + e.dur;
      for (let j = i + 1; j < ks.length && ks[j].gridTime < end; j++)
        if (ks[j].notes.some(p => e.notes.includes(p))) {
          // dur(秒)與 cells(格)都要改:主網頁照 cells × 現在的拍長算音長(可以中途換速度),只改 dur 的話主網頁會疊音
          // 前提:slot 一定在同一小節裡(slots 是每小節各自切的),所以重彈的那一顆一定同小節;
          // 萬一以後 slot 可以跨小節,這裡寧可不截(多響一點),也不要丟錯讓主網頁整圈停掉
          if (ks[j].bar !== e.bar) break;
          e.dur = ks[j].gridTime - e.gridTime;
          e.cells = ks[j].cell - e.cell;
          break;
        }
    }
  }

  /*
   * 人性化(取代規格 2.6 的「每一下獨立高斯 + 力度均勻亂數」):
   * - 整團一起飄:每小節一個共同偏移,AR(1)(feel.drums.drift),所有樂器共用,不會彼此打架
   * - 每個位置的系統偏差與強弱:鼓照 Groove MIDI(sysRel / accent),鍵盤照 POP909,貝斯跟大鼓
   * - 每一下自己的抖動:各鼓件的比例照資料,整體大小錨在規格的 σ(timingSigmaMs)
   * - 和弦不同時落下(POP909 spread),頂音較大聲;吉他照 GuitarSet 下刷 / 上刷的先後
   * 有 swing 的曲風,奇數格的系統偏差交給 swing,不重複加
   *
   * **總量錨在規格的 σ**(2026-10-08 修正,Steven:「拍子不準確」):以前三層各自用滿 σ 再疊起來,
   * 總偏差變成 1.4–2σ,樂器之間差到 20–33ms(tools/feel/timing_check.mjs 量的)。現在
   * 整團一起飄 0.8σ,每一下自己的部分(位置偏差 + 抖動)0.6σ,照資料的比例分(0.8² + 0.6² = 1);
   * 所以離格子的總量 = σ、兩件樂器之間的差 ≈ 0.85σ(合奏的人彼此跟得比跟節拍器緊)。貝斯落在大鼓同一格時用大鼓的時間(同一條);
   * 和弦裡各音以落點為中心散開(不是全部往後),總寬 ≤ 10ms
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
  const SHARED = 0.8, OWN = 0.6;
  const rms = a => (a?.length ? Math.sqrt(a.reduce((x, y) => x + y * y, 0) / a.length) : 0);
  {
    const phi = DR?.drift.phi ?? 0, sd = DR ? K0 * SHARED : 0;
    let d = 0;
    for (let b = -1; b <= o.bars; b++) {
      d = phi * d + Math.sqrt(1 - phi * phi) * gauss() * sd;
      drift.set(b, clampMs(d));
    }
  }
  const KEYS_LIKE = ["keys", "keys2", "pad", "guitar"];
  const kickAt = new Map(); // 大鼓的時間:貝斯落在同一格就用它
  events.sort((a, b) => (a.track === "drums" ? 0 : 1) - (b.track === "drums" ? 0 : 1));
  for (const e of events) {
    const ov = hz.overrides?.[e.piece ?? e.track] ?? {};
    const vr = ov.velocityRand ?? hz.velocityRand ?? 8;
    if (!o.humanize) { e.time = e.gridTime; continue; }
    const k = ov.timingSigmaMs ?? K0;
    const odd = e.cell % 2 === 1 && o.swing > 50;
    let sys = 0, jit = 1, acc = 1, sysArr = null;
    const dk = e.track === "drums" ? (e.piece === "clap" ? "snare" : e.piece) : e.track === "bass" ? "kick" : null;
    if (DR && dk && DR.jitterRel[dk] != null) {
      jit = DR.jitterRel[dk];
      sysArr = DR.sysRel[dk];
      sys = odd ? 0 : sysArr[e.cell];
      acc = e.track === "drums" ? e.acc ?? 1 : DR.accent.hat ? DR.accent.hat[e.cell] ** 0.5 : 1;
    } else if (F?.keys && KEYS_LIKE.includes(e.track)) {
      sysArr = F.keys.sysRel;
      sys = odd ? 0 : sysArr[e.cell];
      acc = e.track === "pad" || !F.keys.accent ? 1 : F.keys.accent[e.cell] ** 0.6;
    }
    // 每一下自己的部分(位置偏差 + 抖動)的總量 = 0.6k,位置偏差與抖動照資料的比例分
    const own = (DR || F?.keys) ? (k * OWN) / Math.max(1e-6, Math.hypot(rms(sysArr), jit)) : k;
    let j = drift.get(e.bar) + clampMs(sys * own + gauss() * jit * own) + (ov.offsetMs ?? 0);
    const gk = e.gridTime.toFixed(4);
    if (e.track === "drums" && e.piece === "kick") kickAt.set(gk, j);
    else if (e.track === "bass" && kickAt.has(gk)) j = kickAt.get(gk); // 貝斯跟大鼓同一格:同一個時間
    else if (e.pedal) {                     // 踏板音是一個音一個事件:同一格的(同一下按下去的)共用一個時間
      const pk = "p" + gk;
      if (kickAt.has(pk)) j = kickAt.get(pk); else kickAt.set(pk, j);
    }
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
      dt = Math.min(dt, 10 / (n - 1)) * Math.min(1, K0 / 6); // 和弦總寬 ≤ 10ms;程式打的曲風(K-pop 舞曲 σ 2ms)跟著縮
      const order = e.notes.map((p, i) => i).sort((a, b) => (lowFirst ? e.notes[a] - e.notes[b] : e.notes[b] - e.notes[a]));
      e.noteDt = e.notes.map(() => 0);
      order.forEach((i, r) => { e.noteDt[i] = ((r - (n - 1) / 2) * dt) / 1000; }); // 以落點為中心散開
      const topI = e.notes.indexOf(Math.max(...e.notes));
      e.noteVel = e.notes.map((p, i) => Math.max(1, Math.min(127, e.vel + (i === topI ? (F.keys?.topVel ?? 0) : 0))));
    }
  }
  events.sort((a, b) => a.gridTime - b.gridTime);

  return { events, plans, meta: { style: st.id, ...o, cellSec, barSec: cellSec * BAR } };
}
