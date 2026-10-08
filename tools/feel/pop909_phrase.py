"""POP909:和弦換之前「搶拍」的比例,與樂句裡第幾小節的力度(4 小節一句)。
用法:python3 tools/feel/pop909_phrase.py /tmp/ds/pop909/POP909 > /tmp/ds/pop909_phrase.json
搶拍 = 和弦換的前 0.15–0.6 拍有鋼琴落下、而且換的那一拍(±0.1 拍)沒有再彈
"""
import sys, os, bisect, json, statistics as stt
from collections import defaultdict
import mido

ROOT = sys.argv[1]
push = [0, 0]; push_len = []
bar_vel = defaultdict(list)
for sid in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, sid)
    if not os.path.isdir(d): continue
    try:
        rows = [l.split() for l in open(os.path.join(d, "beat_midi.txt"))]
        chords = [l.split("\t") for l in open(os.path.join(d, "chord_midi.txt"))]
        mid = mido.MidiFile(os.path.join(d, sid + ".mid"))
    except Exception:
        continue
    beats = [float(r[0]) for r in rows]
    downs = [float(r[0]) for r in rows if float(r[2]) == 1.0]
    on = []
    # 用 mido 的秒數(整首固定速度)
    t, tempo = 0.0, 500000
    for msg in mido.merge_tracks([mid.tracks[0]] + [tr for tr in mid.tracks if tr.name == "PIANO"]):
        t += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
        if msg.type == "set_tempo": tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0: on.append((t, msg.velocity))
    if not on or len(beats) < 8: continue
    times = [o[0] for o in on]
    bl = stt.median(beats[i + 1] - beats[i] for i in range(len(beats) - 1))
    for c in chords[1:]:
        if c[2].strip() == "N": continue
        s = float(c[0])
        a = bisect.bisect_left(times, s - 0.6 * bl); b = bisect.bisect_left(times, s - 0.15 * bl)
        at = bisect.bisect_left(times, s - 0.1 * bl); at2 = bisect.bisect_left(times, s + 0.1 * bl)
        push[1] += 1
        if b > a and at2 == at:
            push[0] += 1; push_len.append((s - times[b - 1]) / bl)
    for i, ds in enumerate(downs[:-1]):
        a = bisect.bisect_left(times, ds); b = bisect.bisect_left(times, downs[i + 1])
        if b > a: bar_vel[i % 4].append(stt.mean(v for _, v in on[a:b]))
r = lambda x: round(x, 3)
m = stt.mean(stt.mean(v) for v in bar_vel.values())
json.dump({"anticipation": {"rate": r(push[0] / push[1]), "beatsEarly": r(stt.median(push_len)), "changes": push[1]},
           "velByBarInPhrase": [r(stt.mean(bar_vel[i]) / m) for i in range(4)]}, sys.stdout)
