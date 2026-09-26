#!/usr/bin/env python3
"""每一下的響度(銅管單獨錄,見 probe_brassonly.js):50ms 一格取峰值,找局部最大(> 全段最大的 20%)當一下,
每一下取 −20ms～+200ms 的 RMS。印每個 label × 進行的「每下 RMS 中位 [最小, 最大]」與峰值中位。
  /tmp/abx/bin/python tools/realism/hits.py /tmp/bcal
"""
import sys, json, os
import numpy as np, soundfile as sf

root = sys.argv[1]
for l in open(os.path.join(root, 'clips.jsonl')):
    r = json.loads(l); x, sr = sf.read(os.path.join(root, 'clips', r['id'] + '.wav')); y = np.abs(x).max(1)
    h = int(sr * 0.05); e = np.array([y[i:i + h].max() for i in range(0, len(y) - h, h)])
    idx = [i for i in range(1, len(e) - 1) if e[i] >= e[i - 1] and e[i] > e[i + 1] and e[i] > e.max() * 0.2]
    rms = [np.sqrt(np.mean(x[max(0, int((i * 0.05 - 0.02) * sr)):int((i * 0.05 + 0.2) * sr)] ** 2)) for i in idx]
    print(r['label'], r['prog'][:14], '下數', len(idx), '峰值中位 %.1f' % (20 * np.log10(np.median(e[idx]))),
          '每下 RMS 中位 %.1f [%.1f, %.1f]' % tuple(20 * np.log10([np.median(rms), min(rms), max(rms)])))
