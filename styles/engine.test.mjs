// 規格書第 6 節的驗收測試:node --test styles/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  cells, SYMBOLS, CELLS, FILL_CELLS, RANGE, render, resolveStyle, progressionBars,
} from "./engine.mjs";

const data = JSON.parse(readFileSync(new URL("./styles.json", import.meta.url), "utf8"));
const ids = data.styles.map(s => s.id);
const DENS = ["low", "standard", "high"];

// 每一條節奏型字串:[位置, 軌別, 字串]
function* lanes(st) {
  for (const d of [...DENS, "fill"]) {
    const kit = st.tracks.drums?.[d];
    if (kit) for (const [p, s] of Object.entries(kit)) yield [`${st.id}.drums.${d}.${p}`, "drums", s, d === "fill"];
  }
  for (const t of ["bass", "keys", "keys2", "pad", "guitar"])
    for (const d of DENS) {
      const s = st.tracks[t]?.[d];
      if (s) yield [`${st.id}.${t}.${d}`, t === "bass" ? "bass" : t === "guitar" ? "guitar" : "keys", s, false];
    }
}

test("有 9 個風格,kpop_ballad 繼承 mandopop_ballad", () => {
  assert.deepEqual(ids, ["pop", "mandopop_ballad", "jpop", "citypop", "kpop_dance", "kpop_ballad", "rnb_neosoul", "lofi", "reggaeton"]);
  const kb = resolveStyle(data, "kpop_ballad"), mb = resolveStyle(data, "mandopop_ballad");
  assert.deepEqual(kb.tracks, mb.tracks);
  assert.equal(kb.bpm.default, 70);
});

test("1. 節奏型去空白後長度 16(fill 8)", () => {
  for (const id of ids) for (const [where, , s, fill] of lanes(resolveStyle(data, id)))
    assert.equal(cells(s).length, fill ? FILL_CELLS : CELLS, where);
});

test("2. 所有字元都在符號表內", () => {
  for (const id of ids) for (const [where, kind, s] of lanes(resolveStyle(data, id)))
    for (const ch of cells(s)) assert.ok(SYMBOLS[kind].includes(ch), `${where} 有不認得的「${ch}」`);
});

test("級數與 C 調範例是同一串和弦", () => {
  for (const id of ids) for (const p of resolveStyle(data, id).progressions) {
    const a = progressionBars(p, 0, "roman"), b = progressionBars(p, 0, "example");
    assert.equal(a.length, b.length, p.id);
    a.forEach((bar, i) => bar.forEach((c, j) => {
      const e = b[i][j];
      assert.deepEqual([c.root, c.bass, c.quality], [e.root, e.bass, e.quality], `${p.id} 第 ${i + 1} 小節 ${c.sym} ≠ ${e.sym}`);
    }));
  }
});

// 每個風格 × 每組進行 × 12 調 × 四種密度設定
function* allRenders(extra = {}) {
  for (const id of ids) {
    const st = resolveStyle(data, id);
    for (const p of st.progressions) for (let key = 0; key < 12; key++)
      for (const density of ["auto", ...DENS])
        yield [`${id}/${p.id}/key${key}/${density}`, st, render(data, id, { progression: p.id, key, density, bars: 16, ...extra })];
  }
}

test("3. 音域:bass 28–48、keys ≤ 72(low ≤ 69)、pad ≤ 67", () => {
  for (const [where, st, r] of allRenders({ humanize: false })) {
    const densOf = bar => r.meta.density === "auto" ? (Math.floor(bar / 8) % 2 ? "high" : "standard") : r.meta.density;
    for (const e of r.events) {
      if (!e.notes) continue;
      const lo = Math.min(...e.notes), hi = Math.max(...e.notes);
      if (e.track === "bass") assert.ok(lo >= RANGE.bass[0] && hi <= RANGE.bass[1], `${where} bass ${e.notes} @${e.bar}:${e.cell}`);
      if (["keys", "keys2", "guitar"].includes(e.track)) {
        const max = densOf(e.bar) === "low" ? RANGE.lowKeysMax : RANGE.keys[1];
        assert.ok(hi <= max, `${where} ${e.track} ${e.notes} > ${max} @${e.bar}:${e.cell}`);
      }
      if (e.track === "keys" && st.voicing.keys === "arp5") assert.ok(lo >= RANGE.arp[0] - 3 && hi <= RANGE.arp[1], `${where} arp ${e.notes}`);
      if (e.track === "pad") assert.ok(hi <= RANGE.pad[1] && lo >= RANGE.pad[0], `${where} pad ${e.notes}`);
    }
  }
});

test("4. voice leading:相鄰和弦最高音差 ≤ 4(段落開頭除外;arp5 是固定指型不算)", () => {
  for (const [where, st, r] of allRenders({ humanize: false, bars: 16 })) {
    for (const [track, plan] of Object.entries(r.plans)) {
      if (track === "keysShell") continue;
      if (track === "keys" && st.voicing.keys === "arp5") continue;
      for (let i = 1; i < plan.length - 1; i++) {
        if (plan[i].fresh) continue;
        const d = Math.abs(plan[i].notes.at(-1) - plan[i - 1].notes.at(-1));
        assert.ok(d <= 4, `${where} ${track} 第 ${plan[i].bar} 小節 ${plan[i - 1].notes}→${plan[i].notes}`);
      }
    }
  }
});

test("5. N 提前切分:下一小節第 0 格不再攻擊", () => {
  let seen = 0;
  for (const [where, , r] of allRenders({ humanize: false })) {
    const atk = new Set(r.events.filter(e => e.track === "keys").map(e => `${e.bar}:${e.cell}`));
    for (const e of r.events.filter(e => e.symbol === "N")) {
      seen++;
      if (e.bar + 1 < r.meta.bars) assert.ok(!atk.has(`${e.bar + 1}:0`), `${where} 第 ${e.bar + 1} 小節第 0 格重彈`);
    }
  }
  assert.ok(seen > 0, "沒有任何 N 被測到");
});

test("6. 同一個 seed 兩次完全相同,換 seed 會變", () => {
  for (const id of ids) {
    const a = render(data, id, { seed: 42 }), b = render(data, id, { seed: 42 }), c = render(data, id, { seed: 43 });
    assert.deepEqual(a.events, b.events, id);
    assert.notDeepEqual(a.events, c.events, id);
  }
});

test("6b. 人性化時間偏移 ≤ ±15ms(加上風格的固定偏移)", () => {
  for (const id of ids) {
    const st = resolveStyle(data, id);
    for (const e of render(data, id, { seed: 7 }).events) {
      const off = st.humanize.overrides?.[e.piece ?? e.track]?.offsetMs ?? 0;
      if (e.gridTime === 0 && e.time === 0) continue;
      assert.ok(Math.abs((e.time - e.gridTime) * 1000 - off) <= 15 + 1e-9, `${id} ${e.track}`);
    }
  }
});

test("7. swing 50 全在格線上;66.7 奇數格位移 = 八分音符的 2/3", () => {
  for (const id of ids) {
    for (const [swing, frac] of [[50, 0.5], [66.7, 0.667]]) {
      const r = render(data, id, { swing, humanize: false });
      const cs = r.meta.cellSec;
      for (const e of r.events) {
        if (e.sub) continue; // 32 分音符連擊的第二下在半格
        const absCell = (e.bar + 1) * CELLS + e.cell;
        if (absCell % 2 === 0) assert.ok(Math.abs(e.gridTime - absCell * cs) < 1e-9, `${id} 偶數格`);
        else {
          const eighthStart = (absCell - 1) * cs;
          assert.ok(Math.abs((e.gridTime - eighthStart) / (2 * cs) - frac) < 1e-9, `${id} swing ${swing}`);
        }
      }
    }
  }
});

test("規則:低密度華語抒情 bass 靜音、fill 只在 high;City Pop keys ≤ 3 格", () => {
  const m = render(data, "mandopop_ballad", { density: "low" });
  assert.equal(m.events.filter(e => e.track === "bass" || e.track === "drums" && e.bar >= 0).length, 0);
  const s = render(data, "mandopop_ballad", { density: "standard", humanize: false });
  assert.equal(s.events.filter(e => e.piece === "snare").length, 0);
  for (const d of DENS)
    for (const e of render(data, "citypop", { density: d }).events.filter(e => e.track === "keys"))
      assert.ok(e.cells <= 3);
});

test("第 2.5 節:每 8 小節最後一小節換 fill、新段落 crash(kpop_dance、lofi 除外)", () => {
  const r = render(data, "pop", { humanize: false });
  assert.deepEqual(r.events.filter(e => e.piece === "crash").map(e => e.bar), [0, 8]);
  const sn = r.events.filter(e => e.piece === "snare" && e.bar === 7 && e.cell >= 8).map(e => e.cell);
  assert.deepEqual(sn, [8, 9, 10, 11, 12, 13, 14, 15]);
  for (const id of ["kpop_dance", "lofi"])
    assert.equal(render(data, id).events.filter(e => e.piece === "crash").length, 0, id);
  assert.equal(r.events.filter(e => e.bar === -1).length, 4, "預備拍四下");
});

test("自己輸入和弦:常見寫法都吃得下,看不懂的要講出是哪一個", () => {
  for (const c of ["Cmaj7 | A7 | Dm7 G7 | C6", "Am7b5 | D7#9 | Gm(maj7) | C°7", "F/A | G7sus | Em7 | Bbmaj7"])
    for (const id of ids) assert.ok(render(data, id, { chords: c, bars: 8 }).events.length > 0, `${id} ${c}`);
  assert.throws(() => render(data, "pop", { chords: "C | Hm" }), /Hm/);
  assert.throws(() => render(data, "pop", { chords: "C | Cxyz" }), /Cxyz/);
});
