"""GuitarSet(CC BY 4.0,6 位吉他手 × 5 種風格的真人伴奏,每條弦分開標註)→ 刷弦統計。
用法:python3 tools/feel/guitarset_stats.py /tmp/ds/guitarset > /tmp/ds/guitarset_stats.json
- 一下刷弦裡各弦的時間差(spread)與方向(低弦先 = 下刷)
- 依十六分位置:刷的機率、相對拍點的偏差、音長
"""
import sys, os, json, statistics as stt
from collections import defaultdict

ROOT = sys.argv[1]
def rsd(xs):
    m = stt.median(xs); return 1.4826 * stt.median(abs(x - m) for x in xs)
acc = defaultdict(lambda: {"spread": [], "down": [], "slot": defaultdict(int), "off": defaultdict(list), "dur": [], "bars": 0, "lag": []})
for f in sorted(os.listdir(ROOT)):
    if not f.endswith("_comp.jams"): continue
    style = f.split("_")[1].split("-")[0].rstrip("0123456789")
    j = json.load(open(os.path.join(ROOT, f)))
    notes, beats, tempo = [], [], None
    for a in j["annotations"]:
        if a["namespace"] == "note_midi":
            s = int(a["annotation_metadata"]["data_source"])
            notes += [(n["time"], s, n["duration"]) for n in a["data"]]
        elif a["namespace"] == "tempo": tempo = a["data"][0]["value"]
        elif a["namespace"] == "beat_position": beats = [b["time"] for b in a["data"]]
    if not notes or not tempo: continue
    g = acc[style]
    notes.sort()
    ms16 = 60000 / tempo / 4
    t0 = beats[0] if beats else 0.0
    groups, k = [], 0
    while k < len(notes):
        grp = [notes[k]]
        while k + len(grp) < len(notes) and notes[k + len(grp)][0] - notes[k][0] < 0.06: grp.append(notes[k + len(grp)])
        groups.append(grp); k += len(grp)
    devs = []
    for grp in groups:
        x = (grp[0][0] - t0) * 1000 / ms16
        slot = round(x); off = (x - slot) * ms16
        g["slot"][slot % 16] += 1; g["off"][slot % 16].append(off); devs.append(off)
        g["dur"].append(stt.median(n[2] for n in grp) * 1000 / ms16)
        if len(grp) >= 3:
            g["spread"].append((grp[-1][0] - grp[0][0]) * 1000)
            strings = [n[1] for n in grp]
            if strings != sorted(strings) or strings != sorted(strings, reverse=True):
                g["down"].append(1 if strings[0] < strings[-1] else 0)
    g["bars"] += (notes[-1][0] - t0) * 1000 / ms16 / 16
    if len(devs) > 20:
        m = stt.mean(devs); v = sum((x - m) ** 2 for x in devs)
        if v: g["lag"].append(sum((devs[i] - m) * (devs[i + 1] - m) for i in range(len(devs) - 1)) / v)
r = lambda x: round(x, 2)
out = {}
for st, g in acc.items():
    sp = sorted(g["spread"])
    out[st] = {"bars": r(g["bars"]),
               "strumSpreadMs": {"p25": r(sp[len(sp) // 4]), "median": r(stt.median(sp)), "p75": r(sp[len(sp) * 3 // 4])},
               "downShare": r(stt.mean(g["down"])) if g["down"] else None,
               "hitPerBar": [r(g["slot"][i] / g["bars"]) for i in range(16)],
               "offMs": [r(stt.median(g["off"][i])) if g["off"][i] else None for i in range(16)],
               "jitterRsdMs": r(rsd([o - md for i in g["off"] for md in [stt.median(g["off"][i])] for o in g["off"][i]])),
               "durCells": {"p25": r(sorted(g["dur"])[len(g["dur"]) // 4]), "median": r(stt.median(g["dur"]))},
               "lag1": r(stt.mean(g["lag"]))}
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
