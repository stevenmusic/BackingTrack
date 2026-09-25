#!/usr/bin/env python3
"""從 Groove MIDI Dataset(Google Magenta,CC BY 4.0)挑 City Pop 用的真人鼓。
每一小節存成 [[拍位置×1000(整數,含微時值), 鼓件, 力度0–127], …];**不量化**。
挑的條件(City Pop 的鼓):大鼓踩第 1 拍、小鼓 backbeat 在 2 / 4、hi-hat 走八分或十六分、
大鼓一小節 2–6 下、沒有 ride 撐整小節、除了第 1 拍不打 crash。
**連續通過的小節整串保留**(同一個鼓手一路打下去的呼吸,是真人最明顯的特徵);過門另外從 fill 檔挑。
  /tmp/abx/bin/python drumphr.py → db/drums_citypop.json"""
import csv, json, os, pretty_midi, numpy as np
GMD = '/tmp/ds/groove'
HERE = os.path.dirname(os.path.abspath(__file__))
# Roland TD-11 的鍵位(GMD 用的)→ 我們的鼓件
MAP = {36: 'k', 38: 's', 40: 's', 37: 'x', 42: 'h', 22: 'h', 44: 'p', 46: 'o', 26: 'o',
       43: 'l', 58: 'l', 45: 't', 47: 't', 48: 't', 50: 't', 49: 'c', 55: 'c', 57: 'c', 52: 'c',
       51: 'r', 59: 'r', 53: 'r'}
def bars_of(path, bpm):
    pm = pretty_midi.PrettyMIDI(path)
    spb = 60 / bpm
    hits = []
    for ins in pm.instruments:
        for n in ins.notes:
            p = MAP.get(n.pitch)
            if p: hits.append((n.start / spb, p, n.velocity))
    hits.sort()
    if not hits: return []
    nb = int(hits[-1][0] // 4) + 1
    bars = [[] for _ in range(nb)]
    for b, p, v in hits:
        i = int((b + 0.12) // 4)                      # 小節線前 0.12 拍以內搶進來的算下一小節(拍位置會是負的)
        if 0 <= i < nb: bars[i].append((round(b - i * 4, 3), p, v))
    return bars
def near(pos, t, w=0.12): return abs(pos - t) <= w
def ok_bar(bar):
    k = [h for h in bar if h[1] == 'k']; s = [h for h in bar if h[1] == 's' and h[2] >= 55]
    hh = [h for h in bar if h[1] in 'ho']; r = [h for h in bar if h[1] == 'r']
    c = [h for h in bar if h[1] == 'c']; t = [h for h in bar if h[1] in 'tl']
    if not any(near(h[0], 0) for h in k): return False
    if not (any(near(h[0], 1) for h in s) and any(near(h[0], 3) for h in s)): return False
    if not (2 <= len(k) <= 6): return False
    if not (7 <= len(hh) <= 18): return False
    if len(r) > 3 or t: return False
    if any(not near(h[0], 0) for h in c): return False
    if sum(1 for h in k if near(h[0], 1, 0.08) or near(h[0], 3, 0.08)) > 0: return False   # 大鼓不踩 2 / 4 的正拍
    return True
rows = list(csv.DictReader(open(f'{GMD}/info.csv')))
runs, fills = [], []
for x in rows:
    st = x['style'].split('/')[0]; bpm = int(x['bpm'])
    if x['time_signature'] != '4-4' or st not in ('funk', 'soul', 'pop', 'rock') or not 85 <= bpm <= 125: continue
    bars = bars_of(f"{GMD}/{x['midi_filename']}", bpm)
    if x['beat_type'] == 'beat':
        cur = []
        for b in bars:
            if ok_bar(b): cur.append(b)
            else:
                if len(cur) >= 4: runs.append({'style': x['style'], 'bpm': bpm, 'drummer': x['drummer'], 'bars': cur})
                cur = []
        if len(cur) >= 4: runs.append({'style': x['style'], 'bpm': bpm, 'drummer': x['drummer'], 'bars': cur})
    else:
        # fill 檔:找「tom 或小鼓很密」的那一小節,而且第 1 拍還是律動(過門從後半才開始)
        for b in bars:
            dense = [h for h in b if h[1] in 'stl' and h[0] >= 2]
            if len(dense) >= 4 and any(h[1] == 'k' and near(h[0], 0) for h in b) and len(b) <= 40:
                fills.append({'style': x['style'], 'bpm': bpm, 'bar': b}); break
# 統計這些小節在一拍四格上的出現率,拿來跟 12 首真歌的鼓比
def stat(bars):
    c = np.zeros(4); n = 0
    for b in bars:
        n += 1
        for pos, p, v in b:
            if p in 'ksh': c[int(round((pos % 1) * 4)) % 4] += 1
    return (c / (n * 4)).round(2)
allbars = [b for r in runs for b in r['bars']]
print('整串', len(runs), '段、共', len(allbars), '小節;過門', len(fills), '個')
print('一拍四格(拍點/e/&/a,每拍幾下,大鼓+小鼓+hi-hat):', stat(allbars))
enc = lambda b: [[int(round(pos * 1000)), p, v] for pos, p, v in b]
out = {'runs': [{'style': r['style'], 'bpm': r['bpm'], 'drummer': r['drummer'], 'bars': [enc(b) for b in r['bars']]} for r in runs],
       'fills': [{'style': f['style'], 'bpm': f['bpm'], 'bar': enc(f['bar'])} for f in fills],
       'license': 'Groove MIDI Dataset, Google LLC, CC BY 4.0'}
json.dump(out, open(os.path.join(HERE, 'db', 'drums_citypop.json'), 'w'))
import collections
print(collections.Counter(r['style'] for r in runs).most_common(10))
