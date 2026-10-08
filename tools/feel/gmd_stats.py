"""Groove MIDI Dataset(Magenta,CC BY 4.0)→ 每個曲風的鼓律動統計。
用法:python3 tools/feel/gmd_stats.py /tmp/ds/groove > /tmp/ds/gmd_stats.json
只用 4/4、beat(不含 fill)的段落。每個十六分位置記:打擊機率、力度、相對格線的時間偏差(ms)。
"""
import csv, json, sys, os, math, statistics as stt
import mido

PIECE = {36: "kick", 38: "snare", 40: "snare", 37: "rim", 42: "hat", 22: "hat", 44: "hat",
         46: "openhat", 26: "openhat", 49: "crash", 55: "crash", 57: "crash", 52: "crash",
         51: "ride", 59: "ride", 53: "ride", 48: "tom", 50: "tom", 45: "tom", 47: "tom", 43: "tom", 58: "tom"}

def notes(path, bpm):
    mid = mido.MidiFile(path)
    ppq = mid.ticks_per_beat
    out, t = [], 0
    for msg in mido.merge_tracks(mid.tracks):
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and msg.note in PIECE:
            out.append((t / ppq, PIECE[msg.note], msg.velocity))
    return out

def main():
    ROOT = sys.argv[1]
    stats = {}
    for row in csv.DictReader(open(os.path.join(ROOT, "info.csv"))):
        if row["beat_type"] != "beat" or row["time_signature"] != "4-4":
            continue
        genre = row["style"].split("/")[0]
        bpm = float(row["bpm"])
        ns = notes(os.path.join(ROOT, row["midi_filename"]), bpm)
        if not ns:
            continue
        g = stats.setdefault(genre, {"bars": 0, "files": 0, "bpm": [], "hits": {}, "series": {}})
        nbars = int(ns[-1][0] // 4) + 1
        g["bars"] += nbars; g["files"] += 1; g["bpm"].append(bpm)
        ms16 = 60000 / bpm / 4
        for beat, piece, vel in ns:
            x = beat * 4
            slot = round(x)
            off = (x - slot) * ms16
            bar, pos = divmod(slot, 16)
            g["hits"].setdefault(piece, {}).setdefault(pos, []).append((bar, vel, off))
            g["series"].setdefault(piece, []).append((row["midi_filename"], slot, off))

    def lag1(xs):
        if len(xs) < 3: return None
        m = stt.mean(xs); v = sum((x - m) ** 2 for x in xs)
        return sum((xs[i] - m) * (xs[i + 1] - m) for i in range(len(xs) - 1)) / v if v else None

    out = {}
    for genre, g in stats.items():
        G = {"files": g["files"], "bars": g["bars"], "bpm": round(stt.median(g["bpm"])), "pieces": {}}
        for piece, slots in g["hits"].items():
            P = {}
            for pos in range(16):
                hs = slots.get(pos, [])
                if not hs: continue
                bars_hit = len({(h[0]) for h in hs})
                vs = [h[1] for h in hs]; os_ = [h[2] for h in hs]
                P[pos] = {"p": round(len(hs) / g["bars"], 3), "vel": round(stt.mean(vs), 1),
                          "velSd": round(stt.pstdev(vs), 1), "ms": round(stt.mean(os_), 1), "msSd": round(stt.pstdev(os_), 1)}
            # 時間偏差的序列相關(同一個檔裡依序;扣掉每個位置的平均)
            ser = {}
            for f, slot, off in g["series"][piece]:
                ser.setdefault(f, []).append((slot, off))
            r1 = []
            for f, xs in ser.items():
                xs.sort()
                mean_by = {}
                for s, o in xs: mean_by.setdefault(s % 16, []).append(o)
                mb = {k: stt.mean(v) for k, v in mean_by.items()}
                res = [o - mb[s % 16] for s, o in xs]
                c = lag1(res)
                if c is not None and len(res) > 30: r1.append(c)
            G["pieces"][piece] = {"slots": P, "lag1": round(stt.mean(r1), 3) if r1 else None}
        out[genre] = G
    json.dump(out, sys.stdout, ensure_ascii=False)

if __name__ == "__main__":
    main()
