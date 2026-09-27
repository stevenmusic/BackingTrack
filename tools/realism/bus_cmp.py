#!/usr/bin/env python3
"""各 bus 單獨錄(probe_solo.js + REALISM_SOLO)之後,同一個 case 檔的每個 label 比:
RMS dB、峰值 dB、亮度(有聲格子的頻譜重心中位數)、嘶%(5–10kHz 佔這條總能量)。
  for k in keysBus drumBus bassBus; do REALISM_PROBE=tools/realism/probe_solo.js REALISM_SOLO=$k REALISM_SECS=24 \\
    REALISM_OUT=/tmp/rr/$k node tools/realism/render.mjs tools/realism/cases_real.json; done
  /tmp/abx/bin/python tools/realism/bus_cmp.py /tmp/rr
"""
import sys, os, json
import numpy as np, soundfile as sf, librosa

root = sys.argv[1]
for bus in sorted(os.listdir(root)):
    p = os.path.join(root, bus, 'clips.jsonl')
    if not os.path.exists(p): continue
    seen = {}
    for l in open(p):
        r = json.loads(l); seen[r['id']] = r
    print('==', bus)
    for r in sorted(seen.values(), key=lambda r: r['label'] or ''):
        x, sr = sf.read(os.path.join(root, bus, 'clips', r['id'] + '.wav'), always_2d=True); y = x.mean(1)
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) ** 2
        fr = librosa.fft_frequencies(sr=sr, n_fft=2048)
        e = S.sum(0); act = np.sqrt(e) > np.sqrt(e.max()) * 10 ** (-30 / 20)
        cen = (fr[:, None] * S).sum(0) / (e + 1e-12)
        hiss = 100 * S[(fr >= 5000) & (fr < 10000)].sum() / (S.sum() + 1e-12)
        print(f"  {r['label']:12s} RMS {20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9):6.1f}  峰值 {20 * np.log10(np.abs(y).max() + 1e-9):5.1f}"
              f"  亮度 {np.median(cen[act]):6.0f}Hz  嘶 {hiss:5.1f}%")
