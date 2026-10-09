"""POP909(MIT,909 首華語流行歌的真人鋼琴伴奏)→ 一小節的鋼琴伴奏型庫(Steven 2026-10-09:「鋼琴節奏型態太單調」
「要真的聽起來像人在彈,不要只是換個和弦複製貼上一樣的節奏型態」)。
用法:python3 tools/feel/pop909_patterns.py /tmp/ds/pop909/POP909 > /tmp/ds/pop909_patterns.json

做法:
- 只用 4/4(每 4 拍一個強拍)的歌;每小節照 beat_midi.txt 的拍點把鋼琴的音對到 16 分格(拍與拍之間線性內插)
- 左右手:鋼琴軌沒有分手,用音域分:< 55(G3)算左手。左手的音標成 L(= 和弦低音)、l5 / l8 / l3(和弦低音上方五度 / 八度 / 三度、十度)、lx(其他)
- 右手:同一格兩個音以上 = B(柱式);一個音 = r1–r4(這小節右手出現過的音由低到高排第幾,四個以上算 4)
- 一小節 = 16 格,每格是一組記號;統計每種型出現幾次,依「這小節有幾格有音」分疏(≤4)、中(5–8)、密(≥9)
- 另外記它在 4 小節樂句裡是第幾小節(第 4 小節的型另外統計:句尾常常不一樣)
"""
import sys, os, bisect, json
from collections import Counter, defaultdict
import mido

ROOT = sys.argv[1]
PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
SPLIT = 55

def chord_at(chords, t):
    i = bisect.bisect_right([c[0] for c in chords], t) - 1
    return chords[i] if i >= 0 else None

def bass_pc(lbl):
    if lbl == "N": return None
    root, _, q = lbl.partition(":")
    r = PC.get(root)
    if r is None: return None
    if "/" in q:
        iv = q.split("/")[1]
        deg = {"3": 4, "b3": 3, "5": 7, "b7": 10, "7": 11, "2": 2, "4": 5, "6": 9}.get(iv)
        if deg is not None: return (r + deg) % 12
    return r

stats = {"low": Counter(), "standard": Counter(), "high": Counter()}
seqs = []   # 每首歌的小節序列:(密度, 16 格記號, 是樂句第幾小節)
end4 = {"low": Counter(), "standard": Counter(), "high": Counter()}
songs = bars_used = 0
for sid in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, sid)
    if not os.path.isdir(d): continue
    try:
        rows = [l.split() for l in open(os.path.join(d, "beat_midi.txt"))]
        chords = []
        for l in open(os.path.join(d, "chord_midi.txt")):
            a, b, lbl = l.rstrip("\n").split("\t"); chords.append((float(a), float(b), lbl))
        mid = mido.MidiFile(os.path.join(d, sid + ".mid"))
    except Exception:
        continue
    beats = [float(r[0]) for r in rows]
    downs = [i for i, r in enumerate(rows) if float(r[2]) == 1.0]
    gaps = Counter(b - a for a, b in zip(downs, downs[1:]))
    if not gaps or gaps.most_common(1)[0][0] != 4 or gaps[4] < 0.9 * sum(gaps.values()): continue   # 只要 4/4
    notes, t, tempo = [], 0.0, 500000
    for msg in mido.merge_tracks([mid.tracks[0]] + [tr for tr in mid.tracks if tr.name == "PIANO"]):
        t += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        if msg.type == "set_tempo": tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0: notes.append((t, msg.note))
    if not notes: continue
    songs += 1
    seq = []
    notes.sort()
    nt = [n[0] for n in notes]
    for k, (a, b) in enumerate(zip(downs, downs[1:])):
        if b - a != 4 or b >= len(beats): continue
        bt = beats[a:b + 1]
        t0, t1 = bt[0], bt[-1]
        i0, i1 = bisect.bisect_left(nt, t0 - 0.05), bisect.bisect_left(nt, t1 - 0.05)
        bar = notes[i0:i1]
        if not bar: continue
        ch = chord_at(chords, t0 + 0.05)
        bp = bass_pc(ch[2]) if ch else None
        if bp is None: continue
        cells = defaultdict(list)
        for tt, p in bar:
            j = min(3, max(0, bisect.bisect_right(bt, tt + 1e-6) - 1))
            frac = (tt - bt[j]) / max(1e-6, bt[j + 1] - bt[j])
            c = j * 4 + round(frac * 4)
            if c >= 16: continue          # 搶到下一小節的不算這一小節
            cells[max(0, c)].append(p)
        rh_pitches = sorted({p for ps in cells.values() for p in ps if p >= SPLIT})
        rank = {p: min(4, i + 1) for i, p in enumerate(rh_pitches)}
        pat = []
        for c in range(16):
            ps = cells.get(c, [])
            toks = set()
            for p in ps:
                if p < SPLIT:
                    iv = (p % 12 - bp) % 12
                    toks.add("L" if iv == 0 and p == min(q for q in ps if q < SPLIT) else {0: "l8", 7: "l5", 3: "l3", 4: "l3"}.get(iv, "lx"))
            rh = [p for p in ps if p >= SPLIT]
            if len(rh) >= 2: toks.add("B")
            elif len(rh) == 1: toks.add("r%d" % rank[rh[0]])
            pat.append("+".join(sorted(toks)) if toks else ".")
        n_on = sum(1 for x in pat if x != ".")
        dens = "low" if n_on <= 4 else "standard" if n_on <= 8 else "high"
        key = " ".join(pat)
        stats[dens][key] += 1
        seq.append((dens, pat, k % 4))
        if (k % 4) == 3: end4[dens][key] += 1
        bars_used += 1
    seqs.append(seq)

out = {"_說明": "POP909 鋼琴伴奏一小節的型(16 格,每格是記號組;L = 和弦低音、l5/l8/l3 = 左手五度/八度/三度、B = 右手柱式、r1–r4 = 右手第幾個音);"
       "由 tools/feel/pop909_patterns.py 產生", "songs": songs, "bars": bars_used, "patterns": {}, "phraseEnd": {}}
for dens in stats:
    tot = sum(stats[dens].values())
    out["patterns"][dens] = [{"cells": k, "n": v, "share": round(v / tot, 4)} for k, v in stats[dens].most_common(40)]
    t4 = sum(end4[dens].values()) or 1
    out["phraseEnd"][dens] = [{"cells": k, "n": v, "share": round(v / t4, 4)} for k, v in end4[dens].most_common(15)]
    out[f"total_{dens}"] = tot
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)

# ── 給引擎用的庫(feel.json 的 keys.lib):節奏型(16 格有沒有音)→ 那個節奏底下真人的內容 ──
# 量到(878 首、68838 小節):下一小節整個一樣 2.4%、節奏一樣 28.1%、密度一樣 79.4%
def lib():
    res = {"repeatRhythm": 0.281, "stayDensity": 0.794, "dens": {}}
    for dens in ("low", "standard", "high"):
        by_mask = defaultdict(Counter)
        end_mask = Counter()
        for seq in seqs:
            for dd, pat, pos in seq:
                if dd != dens: continue
                m = "".join("x" if x != "." else "." for x in pat)
                by_mask[m][" ".join(pat)] += 1
                if pos == 3: end_mask[m] += 1
        masks = sorted(by_mask.items(), key=lambda kv: -sum(kv[1].values()))[:40]
        tot = sum(sum(c.values()) for _, c in masks)
        res["dens"][dens] = {
            "masks": [{"m": m, "w": round(sum(c.values()) / tot, 4),
                       "pats": [[p, n] for p, n in c.most_common(8)]} for m, c in masks],
            "end": [[m, n] for m, n in end_mask.most_common(12) if m in dict(masks)],
        }
    return res
json.dump(lib(), open(os.path.join(os.path.dirname(sys.argv[1].rstrip("/")), "..", "pop909_lib.json"), "w"), ensure_ascii=False)
