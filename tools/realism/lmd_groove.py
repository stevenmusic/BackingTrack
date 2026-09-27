#!/usr/bin/env python3
"""Lakh MIDI(CC BY 4.0,Raffel 2016;Hugging Face AghaTizi/lakh_lmd_full 的 lmd_full.tar.gz)裡**真人彈進去的**伴奏軌
→ 一拍四格(正拍 / e / & / a)的出現率、早晚、力度,給 Rhodes(GM 4、5 電鋼琴)、貝斯(32–39)、乾淨電吉他(27)當律動範本。
篩選(只留真人彈的十六分律動):
- 整首只有一個速度、4/4、速度 85–130
- 這一軌:音頭離十六分格的偏差標準差 ≥ 6ms(沒有量化)、力度至少 10 種(不是一個力度到底)、e / a 格佔 ≥ 15%(十六分律動)
- 和弦(30ms 內一起按)算一下,力度取最大;力度換成振幅比用 sfz 的預設曲線(振幅 ∝ 力度²)
  /tmp/abx/bin/python tools/realism/lmd_groove.py /tmp/lmd/lmd_full [最多幾首]
"""
import sys, os, glob, warnings
import numpy as np, pretty_midi
warnings.filterwarnings('ignore')

root = sys.argv[1]; cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
GROUPS = {'rhodes': range(4, 6), 'bass': range(32, 40), 'eguitar': [27]}
stat = {g: {'dev': [[] for _ in range(4)], 'vel': [[] for _ in range(4)], 'cnt': np.zeros(4), 'beats': 0, 'tracks': 0} for g in GROUPS}
files = sorted(glob.glob(os.path.join(root, '*', '*.mid')))[:cap]
for fi, f in enumerate(files):
    try:
        pm = pretty_midi.PrettyMIDI(f)
    except Exception:
        continue
    tt, tempi = pm.get_tempo_changes()
    if len(tempi) != 1 or not (85 <= tempi[0] <= 130): continue
    ts = pm.time_signature_changes
    if ts and any((t.numerator, t.denominator) != (4, 4) for t in ts): continue
    spb = 60 / tempi[0]; step = spb / 4
    for inst in pm.instruments:
        if inst.is_drum: continue
        g = next((k for k, r in GROUPS.items() if inst.program in r), None)
        if not g or len(inst.notes) < 64: continue
        ns = sorted(inst.notes, key=lambda n: n.start)
        hits = []
        for n in ns:
            if hits and n.start - hits[-1][0] < 0.03: hits[-1][1] = max(hits[-1][1], n.velocity)
            else: hits.append([n.start, n.velocity])
        t = np.array([h[0] for h in hits]) - tt[0]; v = np.array([h[1] for h in hits], float)
        q = np.round(t / step); d = (t - q * step) * 1000
        slot = (q % 4).astype(int)
        if np.std(d) < 6 or len(np.unique(v)) < 10 or np.mean((slot == 1) | (slot == 3)) < 0.15: continue
        S = stat[g]; S['tracks'] += 1; S['beats'] += int((t[-1] - t[0]) / spb) + 1
        for k in range(4):
            m = slot == k
            S['dev'][k] += list(d[m]); S['vel'][k] += list(v[m]); S['cnt'][k] += m.sum()
    if fi % 5000 == 0: print('…', fi, {g: stat[g]['tracks'] for g in GROUPS}, flush=True)
names = ['正拍', 'e', '&', 'a']
for g, S in stat.items():
    if not S['tracks']: print(g, '沒有'); continue
    v0 = np.median(S['vel'][0]); d0 = np.median(S['dev'][0])
    print(f"== {g}  軌數 {S['tracks']}、拍數 {S['beats']}")
    for k in range(4):
        vm = np.median(S['vel'][k])
        print(f"  {names[k]:3s} 出現率 {S['cnt'][k] / S['beats']:.2f}  早晚(相對正拍){np.median(S['dev'][k]) - d0:+5.1f}ms"
              f"  力度中位 {vm:5.1f}(振幅比 {(vm / v0) ** 2:.2f} = {40 * np.log10(vm / v0):+.1f}dB)")
