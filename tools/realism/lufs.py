#!/usr/bin/env python3
"""母帶的專業量法:整合響度 LUFS(ITU-R BS.1770-4,pyloudnorm)、True Peak(4× 升取樣後的峰值 dBTP)、
L/R 相關、單聲道損失。串流平台的常見目標:約 −14 LUFS、True Peak ≤ −1 dBTP。
  /tmp/abx/bin/python tools/realism/lufs.py <render 輸出資料夾>
"""
import sys, os, json
import numpy as np, soundfile as sf, pyloudnorm as pyln
from scipy.signal import resample_poly

root = sys.argv[1]
seen = {}
for l in open(os.path.join(root, 'clips.jsonl')):
    r = json.loads(l); seen[r['id']] = r
for r in sorted(seen.values(), key=lambda r: r['label'] or ''):
    x, sr = sf.read(os.path.join(root, 'clips', r['id'] + '.wav'), always_2d=True)
    lufs = pyln.Meter(sr).integrated_loudness(x)
    tp = 20 * np.log10(np.abs(resample_poly(x, 4, 1, axis=0)).max() + 1e-12)
    sp = 20 * np.log10(np.abs(x).max() + 1e-12)
    corr = np.corrcoef(x[:, 0], x[:, 1])[0, 1]
    mono = 10 * np.log10(np.mean(((x[:, 0] + x[:, 1]) / 2) ** 2) / np.mean(x ** 2))
    print(f"{r['label']:14s} {r['version']:8s} {lufs:6.1f} LUFS  True Peak {tp:5.2f} dBTP(取樣峰值 {sp:5.2f})  L/R 相關 {corr:.2f}  單聲道 {mono:+.1f}dB")
