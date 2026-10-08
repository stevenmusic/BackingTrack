"""Groove MIDI(CC BY 4.0):
1. 時間偏差拆成三層:整個檔的固定偏移(錄音延遲,丟掉)、小節漂移(慢慢飄)、每一下的抖動
2. 每小節偏離「這個檔的基本律動」的機率,依鼓件、位置、樂句位置(第幾小節)
用法:python3 tools/feel/gmd_vary.py /tmp/ds/groove > /tmp/ds/gmd_vary.json
"""
import csv, json, sys, os, statistics as stt
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gmd_stats import notes

ROOT = sys.argv[1]
# 第二個參數:拍號(4-4 / 3-4 / 6-8);三拍的一小節是 12 個十六分(6/8 = 六個八分 = 12 格)
TS = sys.argv[2] if len(sys.argv) > 2 else "4-4"
BAR = {"4-4": 16, "3-4": 12, "6-8": 12}[TS]
MAIN = ["kick", "snare", "hat", "openhat", "rim"]
acc = defaultdict(lambda: {"drift": [], "driftLag1": [], "jit": defaultdict(list), "sys": defaultdict(list),
                           "vel": defaultdict(list), "add": defaultdict(lambda: [0, 0]), "drop": defaultdict(lambda: [0, 0]),
                           "phrase": defaultdict(lambda: [0, 0]), "bars": 0})

def lag1(xs):
    if len(xs) < 4: return None
    m = stt.mean(xs); v = sum((x - m) ** 2 for x in xs)
    return sum((xs[i] - m) * (xs[i + 1] - m) for i in range(len(xs) - 1)) / v if v else None

for row in csv.DictReader(open(os.path.join(ROOT, "info.csv"))):
    if row["beat_type"] != "beat" or row["time_signature"] != TS:
        continue
    g = acc[row["style"].split("/")[0] if TS == "4-4" else TS]  # 三拍資料少,所有曲風併在一起
    bpm = float(row["bpm"]); ms16 = 60000 / bpm / 4
    ns = notes(os.path.join(ROOT, row["midi_filename"]), bpm)
    if len(ns) < 20: continue
    hits = []
    for beat, piece, vel in ns:
        x = beat * 4; slot = round(x)
        hits.append((slot // BAR, slot % BAR, piece, vel, (x - slot) * ms16))
    fmean = stt.mean(h[4] for h in hits)
    nb = max(h[0] for h in hits) + 1
    if nb < 4: continue
    # 小節漂移
    by_bar = defaultdict(list)
    for h in hits: by_bar[h[0]].append(h[4] - fmean)
    bm = [stt.mean(by_bar[b]) if by_bar[b] else 0 for b in range(nb)]
    g["drift"] += bm
    c = lag1(bm)
    if c is not None: g["driftLag1"].append(c)
    # 位置的系統偏差(扣掉小節漂移之後)與抖動
    res = defaultdict(list)
    for b, pos, pc, vel, off in hits:
        res[(pc, pos)].append(off - fmean - bm[b])
    for (pc, pos), xs in res.items():
        m = stt.mean(xs)
        g["sys"][f"{pc}:{pos}"] += xs
        g["jit"][pc] += [x - m for x in xs]
    for b, pos, pc, vel, off in hits: g["vel"][f"{pc}:{pos}"].append(vel)
    # 基本律動 = 這個檔裡每一顆鼓最常出現的一小節(16 格 bitmask)
    pat = defaultdict(lambda: [0] * nb)
    for b, pos, pc, vel, off in hits:
        if pc in MAIN: pat[pc][b] |= 1 << pos
    g["bars"] += nb
    for pc, masks in pat.items():
        mode = Counter(masks).most_common(1)[0][0]
        for b, m in enumerate(masks):
            diff = m != mode
            g["phrase"][f"{pc}:{b % 4}"][0] += diff; g["phrase"][f"{pc}:{b % 4}"][1] += 1
            for pos in range(BAR):
                inmode = mode >> pos & 1; on = m >> pos & 1
                if inmode: g["drop"][f"{pc}:{pos}"][0] += (not on); g["drop"][f"{pc}:{pos}"][1] += 1
                else: g["add"][f"{pc}:{pos}"][0] += on; g["add"][f"{pc}:{pos}"][1] += 1

def rsd(xs):
    """穩健標準差:1.4826 × 中位數絕對偏差(32 分音符、裝飾音被併到同一格時不會把它撐大)"""
    m = stt.median(xs)
    return 1.4826 * stt.median(abs(x - m) for x in xs)

out = {}
for genre, g in acc.items():
    r = lambda x: round(x, 3)
    out[genre] = {
        "bars": g["bars"],
        "driftSdMs": r(rsd(g["drift"])), "driftLag1": r(stt.mean(g["driftLag1"])),
        "jitterSdMs": {pc: r(rsd(v)) for pc, v in g["jit"].items() if len(v) > 50},
        "sysMs": {k: r(stt.median(v)) for k, v in g["sys"].items() if len(v) > 30},
        "vel": {k: [r(stt.mean(v)), r(stt.pstdev(v))] for k, v in g["vel"].items() if len(v) > 30},
        "pAdd": {k: r(a / n) for k, (a, n) in g["add"].items() if n > 30 and a / n > 0.01},
        "pDrop": {k: r(a / n) for k, (a, n) in g["drop"].items() if n > 30},
        "pVaryByPhraseBar": {k: r(a / n) for k, (a, n) in g["phrase"].items() if n > 30},
    }
json.dump(out, sys.stdout, ensure_ascii=False)
