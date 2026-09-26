#!/usr/bin/env python3
"""docs/REVIEW.md 的數字重現腳本(只讀,不寫檔)
  python3 review_stats.py drums   → A1 偏差毫秒、A2 各串力度、A3 Blues 逐串 swing 比例(db/drums_*.json)
  python3 review_stats.py leak    → B1 人聲滲漏表(db/style.json 的 ours vs oursmel,逐段配對,bootstrap 2000 次,種子 0)"""
import json, os, sys, numpy as np
H = os.path.dirname(os.path.abspath(__file__))

def drums():
    for k, bpm in (('blues', 70), ('swing', 100), ('straight', 100), ('funk', 105)):
        D = json.load(open(os.path.join(H, 'db', f'drums_{k}.json')))
        a = np.abs(np.array([p / 1000 - round(p / 1000 * 4) / 4 for r in D['runs'] for b in r for p, x, v in b]))
        spb = 60 / bpm * 1000
        print(f'A1 {k:8s} @{bpm}BPM 偏差 中位 {np.median(a)*spb:.1f}ms 95% {np.percentile(a,95)*spb:.1f}ms 最大 {a.max()*spb:.1f}ms')
        means = [np.mean(v) for v in ([v for b in r for p, x, v in b if x in 'ks'] for r in D['runs']) if v]
        skipped = len(D['runs']) - len(means)
        d = [abs(x - y) for i, x in enumerate(means) for j, y in enumerate(means) if i != j]
        print(f'A2 {k:8s} 串平均力度(大鼓+小鼓) {min(means):.0f}–{max(means):.0f}/127,任兩串相差 中位 {np.median(d):.0f} 最大 {max(d):.0f}'
              + (f'(另有 {skipped} 串沒有大鼓小鼓,不算)' if skipped else ''))
        if k == 'blues':
            for m, r in zip(D['meta'], D['runs']):
                offs = [p / 1000 % 1 for b in r for p, x, v in b if x in 'hor' and 0.3 < p / 1000 % 1 < 0.9]
                sw = float(np.median(offs))
                print(f"A3 {m['style']:14s} {m['drummer']:9s} 小節 {len(r):2d} 反拍中位 {sw:.3f} → {sw/(1-sw):.2f}:1")

def leak():
    d = json.load(open(os.path.join(H, 'db', 'style.json')))
    a, b = d['ours'], d['oursmel']; rng = np.random.default_rng(0)
    for k in ('和聲.模板外', '和聲.延伸音', '和聲.七度', '和聲7.模板外', '和聲7.延伸音', '和聲7.七度', 'other.佔比dB', 'piano.佔比dB', 'guitar.佔比dB'):
        ks = [t for t in a if k in a[t] and k in b[t]]
        x = np.array([a[t][k] for t in ks]); y = np.array([b[t][k] for t in ks]); dl = y - x
        lo, hi = np.percentile([rng.choice(dl, len(dl)).mean() for _ in range(2000)], [2.5, 97.5])
        ref = np.array([f[k] for g in ('real', 'suno') for f in d[g].values() if k in f])
        gap = ref.mean() - x.mean()
        print(f'B1 {k:14s} 無 {x.mean():8.3f} 有 {y.mean():8.3f} 差 {dl.mean():+.3f} [{lo:+.3f},{hi:+.3f}] 參考差距 {gap:+.3f} 比例 {dl.mean()/gap*100:+.0f}% n={len(ks)}')

{'drums': drums, 'leak': leak}[sys.argv[1] if len(sys.argv) > 1 else 'drums']()
