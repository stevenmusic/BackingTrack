#!/usr/bin/env python3
"""真歌的鋪底(「其他」軌,Basic Pitch 轉成音符)換和弦時怎麼接。
只看長音(≥1 拍)那一層:
  - 共同音延續率:新和弦進來(同時 ≥2 顆長音起音)那一刻,正在響、而且沒有在 ±0.15 秒內結束的長音,
    佔「這一刻之後在響的長音」的幾成(= 沒有重新起音、直接撐過去的)
  - 交疊:上一顆和弦的長音在新和弦進來之後還撐多久(秒、拍)
  - 空隙:在新和弦之前就先斷掉的,斷多久
  - 同時幾顆長音、音域(midi 中位數)
  /tmp/abx/bin/python padgram.py /tmp/bp/other.json"""
import json, sys, os, numpy as np
D = json.load(open(sys.argv[1]))
C = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'chords.json')))
res = {}
for song, v in D.items():
    spb = 60 / C[song]['bpm']
    N = [n for n in v['notes'] if n[1] - n[0] >= spb * 1.0]
    N.sort()
    if len(N) < 20: continue
    starts = np.array([n[0] for n in N])
    # 和弦進來的時刻:60ms 內 ≥2 顆長音一起起音
    evs = []; i = 0
    while i < len(N):
        j = i
        while j + 1 < len(N) and N[j + 1][0] - N[i][0] < 0.06: j += 1
        if j > i: evs.append(N[i][0])
        i = j + 1
    held, fresh, over, gap = 0, 0, [], []
    for t in evs:
        for n in N:
            if n[0] < t - 0.15 and n[1] > t + 0.15: held += 1              # 撐過去的共同音
            elif abs(n[0] - t) <= 0.06: fresh += 1                         # 這一刻新起音的
            elif n[0] < t - 0.15 and t - 0.6 < n[1] <= t + 0.6:            # 上一顆和弦在這附近結束的
                (over if n[1] > t else gap).append(abs(n[1] - t))
    poly = []
    for t in np.arange(N[0][0], N[-1][1], 0.25):
        poly.append(sum(1 for n in N if n[0] <= t < n[1]))
    poly = [p for p in poly if p > 0]
    res[song] = {'和弦進來次數': len(evs), '共同音延續率': round(held / max(1, held + fresh), 2),
                 '交疊(拍)中位': round(float(np.median(over)) / spb, 2) if over else None,
                 '先斷掉的比例': round(len(gap) / max(1, len(gap) + len(over)), 2),
                 '空隙(拍)中位': round(float(np.median(gap)) / spb, 2) if gap else None,
                 '同時長音數': round(float(np.median(poly)), 1) if poly else None,
                 '音域midi': round(float(np.median([n[2] for n in N])), 1),
                 '長音平均長(拍)': round(float(np.median([(n[1] - n[0]) / spb for n in N])), 2)}
    print(song, json.dumps(res[song], ensure_ascii=False))
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'padgram.json'), 'w'), ensure_ascii=False, indent=1)
