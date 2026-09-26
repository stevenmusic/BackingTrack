#!/usr/bin/env python3
"""docs/REVIEW.md 的數字重現腳本(只讀,不寫檔)
  python3 review_stats.py drums   → A1 偏差毫秒、A2 各串力度、A3 Blues 逐串 swing 比例(db/drums_*.json)
  python3 review_stats.py leak [--merge-mix]  → 人聲滲漏表(db/style.json 的 ours vs oursmel,逐段配對,bootstrap 2000 次,種子 0);
                                              比例 = 滲漏 ÷ (參考平均 − 我們平均),參考 = 真歌 + Suno(加 --merge-mix 時真歌含合集)
  python3 review_stats.py mix     → 合集 vs 上傳真歌的分離度檢定(隨機對半切 300 次,種子 0)
  python3 review_stats.py sub     → 只用上傳 13 首真歌(不併合集)+ Suno 16:亮度與貝斯密度的 z、區間、分離度上限
  python3 review_stats.py dup <上傳資料夾>  → 重複檢查(CENS chroma 滑動相關;要原始 mp3,音檔不進 repo)"""
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

KEYS = ('和聲7.延伸音', '和聲.延伸音', '和聲.七度', '和聲.模板外', '和聲7.模板外', 'other.亮度Hz', 'guitar.亮度Hz', 'piano.亮度Hz',
        'drums.佔比dB', 'bass.佔比dB', 'bass.每拍起音', 'bass.殘響比', 'other.寬度', 'other.佔比dB', 'piano.佔比dB', 'guitar.佔比dB')

def refs(d):
    r = list(d['real'].values()) + list(d['suno'].values())
    if '--merge-mix' in sys.argv and 'realmix' in d:
        r += list(d['realmix'].values())
    return r

def leak():
    d = json.load(open(os.path.join(H, 'db', 'style.json')))
    a, b = d['ours'], d['oursmel']; rng = np.random.default_rng(0)
    for k in KEYS:
        ks = [t for t in a if k in a[t] and k in b[t]]
        if len(ks) < 3:
            print(f'{k:14s} 樣本不足 n={len(ks)}'); continue
        x = np.array([a[t][k] for t in ks]); y = np.array([b[t][k] for t in ks]); dl = y - x
        lo, hi = np.percentile([rng.choice(dl, len(dl)).mean() for _ in range(2000)], [2.5, 97.5])
        ref = np.array([f[k] for f in refs(d) if k in f])
        gap = ref.mean() - np.mean([f[k] for f in a.values() if k in f])
        print(f'{k:14s} 無 {x.mean():9.3f} 有 {y.mean():9.3f} 滲漏 {dl.mean():+9.3f} [{lo:+.3f},{hi:+.3f}] 差距 {gap:+9.3f} 比例 {dl.mean()/gap*100:+5.0f}% n={len(ks)}')

def mix():
    d = json.load(open(os.path.join(H, 'db', 'style.json')))
    auc = lambda a, b: float(np.mean([(x > y) + 0.5 * (x == y) for x in a for y in b]))
    keys = sorted({k for g in ('real', 'realmix') for f in d[g].values() for k in f})
    def med(A, B):
        return np.median([abs(auc([f[k] for f in A if k in f], [f[k] for f in B if k in f]) - 0.5) * 2
                          for k in keys if sum(k in f for f in A) >= 3 and sum(k in f for f in B) >= 3])
    A, Bm = list(d['real'].values()), list(d['realmix'].values()); obs = med(A, Bm)
    rng = np.random.default_rng(0); al = A + Bm; n = len(A)
    base = [med([al[i] for i in p[:n]], [al[i] for i in p[n:]]) for p in (rng.permutation(len(al)) for _ in range(300))]
    print(f'分離度中位 {obs:.3f};對半切 95% {np.percentile(base, 2.5):.3f}–{np.percentile(base, 97.5):.3f};p = {np.mean(np.array(base) >= obs):.3f}')
    for k in ('和聲7.延伸音', '和聲.七度', '和聲.延伸音', 'other.亮度Hz', '速度'):
        x = [f[k] for f in A if k in f]; y = [f[k] for f in Bm if k in f]
        print(f'  {k:12s} 上傳 平均 {np.mean(x):.3f} 中位 {np.median(x):.3f} | 合集 平均 {np.mean(y):.3f} 中位 {np.median(y):.3f} | 分離度 {abs(auc(x, y) - 0.5) * 2:.2f}')

def dup():
    import glob, librosa
    U = sys.argv[2]
    def c(f, a=0, dd=None):
        y, sr = librosa.load(f, sr=11025, mono=True, offset=a, duration=dd)
        return librosa.feature.chroma_cens(y=y, sr=sr, hop_length=2048)
    def best(A, B, L=80):
        s = 0
        for st in (0.25, 0.5, 0.75):
            i = int(A.shape[1] * st); q = A[:, i:i + L]
            if q.shape[1] < L: continue
            qn = (q - q.mean()) / (q.std() + 1e-9)
            for j in range(0, B.shape[1] - L, 4):
                w = B[:, j:j + L]; s = max(s, float(((w - w.mean()) / (w.std() + 1e-9) * qn).mean()))
        return s
    up = {os.path.basename(f).split('-', 1)[1][:28]: f for f in glob.glob(U + '/*.mp3') if 'vol.69' not in f and 'NO_AI' not in f and 'Karaoke' not in f}
    mixf = glob.glob(U + '/*NO_AI*.mp3')[0]
    tc = [0, 224, 502, 767, 1061, 1380, 1679, 1854, 2077, 2417, 2821, 3096, 3411, 3650]
    full = {k: c(f) for k, f in up.items()}
    for i in range(13):
        full[f'合集{i + 1:02d}'] = c(mixf, tc[i], tc[i + 1] - tc[i])
    o = glob.glob(U + '/*Plastic_Love_Official*')[0]; kk = glob.glob(U + '/*Karaoke*')[0]
    print('正對照:同一錄音', round(best(c(o, 0, 150), c(o)), 2), '/ 同一首不同錄音', round(best(c(kk), c(o)), 2))
    ks = list(full); r = sorted(((best(full[ks[i]], full[ks[j]]), ks[i], ks[j]) for i in range(len(ks)) for j in range(i + 1, len(ks))), reverse=True)
    for s_, a_, b_ in r[:5]:
        print(f'  {s_:.2f} {a_} ↔ {b_}')

def sub():
    d = json.load(open(os.path.join(H, 'db', 'style.json'))); rng = np.random.default_rng(0)
    auc = lambda a, b: float(np.mean([(x > y) + 0.5 * (x == y) for x in a for y in b]))
    for k in ('other.亮度Hz', 'guitar.亮度Hz', 'piano.亮度Hz', 'bass.每拍起音', '和聲7.延伸音'):
        v = {g: np.array([f[k] for f in d[g].values() if k in f]) for g in ('real', 'suno', 'ours')}
        zf = lambda v: (v['ours'].mean() - np.r_[v['real'], v['suno']].mean()) / (np.r_[v['real'], v['suno']].std() + 1e-9)
        sf_ = lambda v: abs(auc(list(v['real']), list(v['suno'])) - 0.5) * 2
        bz, bs = [], []
        for _ in range(2000):
            w = {g: rng.choice(x, len(x)) for g, x in v.items()}; bz.append(zf(w)); bs.append(sf_(w))
        print(f'{k:12s} z {zf(v):+.2f} [{np.percentile(bz,2.5):+.2f},{np.percentile(bz,97.5):+.2f}]  分離度 {sf_(v):.2f} 上限 {np.percentile(bs,97.5):.2f}  '
              f'n={len(v["real"])}/{len(v["suno"])}/{len(v["ours"])}  真歌中位 {np.median(v["real"]):.3f}')

{'drums': drums, 'leak': leak, 'mix': mix, 'dup': dup, 'sub': sub}[sys.argv[1] if len(sys.argv) > 1 else 'drums']()
