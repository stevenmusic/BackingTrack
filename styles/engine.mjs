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
};

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
  return chordOf(root, bass, m[3].replace(/b/g, "♭").replace(/#/g, "♯"), sym);
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
  return prog[from].split("|").map(bar => bar.trim().split(/\s+/).map(tok =>
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
 * opt: { progression, key(0–11), bars, density: "auto"|"low"|"standard"|"high", bpm, swing, seed, humanize, countIn }
 * 回傳 { events, plans, meta };events 依時間排序,plans 是各軌每顆和弦的聲位(驗收 voice leading 用)
 */
export function render(data, styleId, opt = {}) {
  const st = resolveStyle(data, styleId);
  const o = {
    progression: st.progressions[0].id, key: 0, bars: 16, density: "auto",
    bpm: st.bpm.default, swing: st.swing, seed: 1, humanize: true, countIn: true, ...opt,
  };
  const prog = st.progressions.find(p => p.id === o.progression);
  if (!prog) throw new Error(`${st.id} 沒有這個和弦進行:${o.progression}`);
  const rules = st.rules ?? {};
  const pBars = progressionBars(prog, o.key);

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
      notes, vel: TRACK_VEL[track], ...extra });
  };
  const hit = (piece, bar, cell, vel, sub = 0) => {
    const t0 = gridAt(bar, cell + sub / 2);
    push({ track: "drums", piece, bar, cell, sub, gridTime: t0, dur: cellSec / (sub ? 2 : 1), vel });
  };

  // 預備拍:hi-hat 四下四分音符
  if (o.countIn) for (let c = 0; c < CELLS; c += 4) hit("hat", -1, c, DRUM_VEL.x);

  const fillOn = dens => !rules.fillDensities || rules.fillDensities.includes(dens);
  const carry = {}; // N 延到下一小節:carry[track] = 被吃掉的那一小節
  let lastBass = null;

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
      for (const [piece, s] of Object.entries(lanes))
        [...s].forEach((ch, c) => {
          if (ch === "r") DRUM_VEL.r.forEach((v, k) => hit(piece, b, c, v, k));
          else if (DRUM_VEL[ch]) hit(piece, b, c, DRUM_VEL[ch]);
        });
    }

    // 旋律軌
    for (const track of MELODIC) {
      const lane = laneOf(st, track, dens);
      if (!lane) continue;
      const s = cells(lane);
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
          note(track, b, c, held, plans.keys[si + 1].notes, { symbol: "N" });
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
          if (track === "guitar") notes = v.slice(-(st.tracks.guitar.topNotes ?? 2));
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

  // 人性化:時間高斯(上限 ±15ms)+ 固定偏移、力度均勻;順序固定,同 seed 同結果
  const rnd = mulberry32(o.seed);
  const gauss = () => {
    const u = 1 - rnd(), v = rnd();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  const hz = st.humanize ?? {};
  for (const e of events) {
    const ov = hz.overrides?.[e.piece ?? e.track] ?? {};
    const sigma = ov.timingSigmaMs ?? hz.timingSigmaMs ?? 6;
    const vr = ov.velocityRand ?? hz.velocityRand ?? 8;
    if (o.humanize) {
      const j = Math.max(-HUMANIZE_CAP_MS, Math.min(HUMANIZE_CAP_MS, gauss() * sigma)) + (ov.offsetMs ?? 0);
      e.time = Math.max(0, e.gridTime + j / 1000);
      e.vel = Math.max(1, Math.min(127, e.vel + Math.round((rnd() * 2 - 1) * vr)));
    } else e.time = e.gridTime;
  }
  events.sort((a, b) => a.gridTime - b.gridTime);

  return { events, plans, meta: { style: st.id, ...o, cellSec, barSec: cellSec * CELLS } };
}
