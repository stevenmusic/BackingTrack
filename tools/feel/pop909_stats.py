"""POP909(MIT,909 首華語流行歌的真人鋼琴伴奏)→ 鍵盤彈法統計。
用法:python3 tools/feel/pop909_stats.py /tmp/ds/pop909/POP909 > /tmp/ds/pop909_stats.json
- 和弦裡各音不會同時落下:同一下(40ms 內)的最早到最晚(spread)、由低到高還是由高到低
- 頂音比其他音大聲多少
- 依十六分位置的力度、相對拍點的時間偏差
- 音長:一下和弦按多久(以拍為單位)
"""
import sys, os, bisect, json, statistics as stt
from collections import defaultdict
import mido

ROOT = sys.argv[1]
def rsd(xs):
    m = stt.median(xs); return 1.4826 * stt.median(abs(x - m) for x in xs)

spread, order_up, order_n, topdiff, groupsize = [], 0, 0, [], []
vel_pos, off_pos, durs, lag = defaultdict(list), defaultdict(list), [], []
lh_rh = [[], []]
songs = 0
for sid in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, sid)
    if not os.path.isdir(d): continue
    try:
        beats = [float(l.split()[0]) for l in open(os.path.join(d, "beat_midi.txt"))]
        mid = mido.MidiFile(os.path.join(d, sid + ".mid"))
    except Exception:
        continue
    songs += 1
    on, ns, t = {}, [], 0.0
    tempo = 500000
    for msg in mido.merge_tracks([mid.tracks[0]] + [tr for tr in mid.tracks if tr.name == "PIANO"]):
        t += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        if msg.type == "set_tempo": tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0: on[msg.note] = (t, msg.velocity)
        elif msg.type in ("note_off", "note_on") and msg.note in on:
            s, v = on.pop(msg.note); ns.append((s, t - s, msg.note, v))
    ns.sort()
    # 依拍點換算位置與偏差
    devs = []
    for s, dur, n, v in ns:
        i = bisect.bisect_right(beats, s) - 1
        if i < 0 or i + 1 >= len(beats): continue
        bl = beats[i + 1] - beats[i]
        x = (s - beats[i]) / bl * 4
        slot = round(x)
        if slot == 4: continue
        off = (x - slot) * bl / 4 * 1000
        pos = (i % 4) * 4 + slot  # 以 4 拍為一小節近似(多數是 4/4)
        vel_pos[pos].append(v); off_pos[pos].append(off); devs.append(off)
        durs.append(dur / bl)
        lh_rh[0 if n < 60 else 1].append(v)
    if len(devs) > 20:
        m = stt.mean(devs); vv = sum((x - m) ** 2 for x in devs)
        if vv: lag.append(sum((devs[k] - m) * (devs[k + 1] - m) for k in range(len(devs) - 1)) / vv)
    # 和弦:40ms 內落下的算同一下
    k = 0
    while k < len(ns):
        g = [ns[k]]
        while k + len(g) < len(ns) and ns[k + len(g)][0] - ns[k][0] < 0.04: g.append(ns[k + len(g)])
        if len(g) >= 3:
            spread.append((g[-1][0] - g[0][0]) * 1000)
            groupsize.append(len(g))
            byp = sorted(g, key=lambda x: x[2])
            first_low = min(g, key=lambda x: x[0])[2] == byp[0][2]
            first_high = min(g, key=lambda x: x[0])[2] == byp[-1][2]
            if first_low != first_high: order_n += 1; order_up += first_low
            topdiff.append(byp[-1][3] - stt.mean(x[3] for x in byp[:-1]))
        k += len(g)

r = lambda x: round(x, 2)
med = {p: stt.median(v) for p, v in off_pos.items()}
out = {
    "songs": songs,
    "chordSpreadMs": {"median": r(stt.median(spread)), "p75": r(sorted(spread)[len(spread) * 3 // 4]), "p90": r(sorted(spread)[len(spread) * 9 // 10])},
    "lowFirstShare": r(order_up / order_n),
    "topMinusRestVel": {"median": r(stt.median(topdiff)), "mean": r(stt.mean(topdiff))},
    "velByPos": [r(stt.mean(vel_pos[p])) for p in range(16)],
    "velSdByPos": [r(stt.pstdev(vel_pos[p])) for p in range(16)],
    "offMsByPos": [r(stt.median(off_pos[p])) for p in range(16)],
    "jitterRsdMs": r(rsd([o - med[p] for p in off_pos for o in off_pos[p]])),
    "lag1": r(stt.mean(lag)),
    "durBeats": {"p25": r(sorted(durs)[len(durs) // 4]), "median": r(stt.median(durs)), "p75": r(sorted(durs)[len(durs) * 3 // 4])},
    "velLowVsHigh": [r(stt.mean(lh_rh[0])), r(stt.mean(lh_rh[1]))],
}
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
