#!/usr/bin/env python3
"""每一條 bus 單獨錄音(REALISM_PROBE,見 /tmp/solo/probe_<bus>.js 的寫法)→ 按小節折疊到 16 格,
每一格取「−10ms～+50ms 的峰值」對小節平均,印 dBFS。用來回答「每小節突出的那一下是誰、在第幾格」,
不靠 demucs 拆軌(拆軌會跨層漏音,審查第九輪 B1)。錄音從 currentBeat() ≥ 32 開始,t = 0 大約是小節線。
**注意**:每條 bus 是**分開錄**的,錄音起點各自會差到一個 ScriptProcessor 緩衝(4096 取樣 ≈ 90ms)——
**不同 bus 之間只能比音量(每小節峰值),不能比「落在第幾格」**。第幾格要看排程(REALISM_PROBE 包 `strum` / `pluck` 記拍點)。

  /tmp/abx/bin/python fold.py <根目錄> <bpm> <id>...     根目錄底下是 <bus>/clips/<id>.wav
"""
import sys, os
import numpy as np, soundfile as sf

root, bpm, ids = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
bar = 4 * 60 / bpm; sl = bar / 16
for cid in ids:
    print('==', cid)
    for k in sorted(os.listdir(root)):
        p = os.path.join(root, k, 'clips', cid + '.wav')
        if not os.path.exists(p): continue
        x, sr = sf.read(p, always_2d=True); y = np.abs(x).max(1)
        n = int(len(y) / sr / bar) - 1
        prof = np.zeros(16)
        for b in range(n):
            for s in range(16):
                a = max(0, int((b * bar + s * sl - 0.01) * sr)); e = int((b * bar + s * sl + 0.05) * sr)
                prof[s] += y[a:e].max() / n
        db = 20 * np.log10(prof + 1e-9)
        bars = [y[int(b * bar * sr):int((b + 1) * bar * sr)].max() for b in range(n)]
        print(f'  {k:8s}', ' '.join(f'{d:4.0f}' for d in db), f'  每小節峰值中位 {20 * np.log10(np.median(bars)):5.1f} dBFS')
