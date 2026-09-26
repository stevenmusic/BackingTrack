#!/usr/bin/env python3
"""City Pop「節奏變化」尺(2026-09-26,Steven:「不要整個和弦進行用完全一樣的節奏,避免像機器人」)。
真歌與 Suno 都算正確答案(同 style.py),看我們哪一層的節奏太重複、輕重音太平。

輸入:htdemucs_6s 分軌 /tmp/sty/sep_<組>/htdemucs_6s/*/(drums / bass / guitar / piano / other)
  /tmp/abx/bin/python vary.py [組…]         預設 real realmix suno ours;結果 db/vary.json
  /tmp/abx/bin/python vary.py --report      只印排名(讀 db/vary.json,真歌 = real + realmix)

做法:鼓 + 貝斯抓拍點,每 4 拍一小節、每拍切 4 格(十六分),每格取該分軌 onset strength 的最大值(±30ms)。
每小節除以自己的最大值 → 16 維的「起音輪廓」。
- 相鄰相似:相鄰兩小節輪廓的 cosine(越接近 1 = 每小節一樣)
- 隔一相似:隔一小節(兩小節一循環的型也算重複)
- 同型比例:二值化(> 0.35)後跟上一小節完全相同的比例
- 輕重對比:小節內有起音的格子,強度的變異係數(越小 = 每一下一樣重)
- 正拍比:正拍四格的平均強度 ÷ 其他有起音格的平均強度
分軌有滲漏(人聲、別的樂器),所以只比「方向」,穩定的定義同 style.py
"""
import glob, os, json, sys
import numpy as np, soundfile as sf, librosa

SR = 22050
HOP = 128
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other']
H = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(H, 'db', 'vary.json')


def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def feats(d):
    ys = {s: load(d, s) for s in STEMS}
    tot = sum(np.mean(y ** 2) for y in ys.values())
    _, beats = librosa.beat.beat_track(y=ys['drums'] + ys['bass'], sr=SR, hop_length=HOP)
    bt = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)
    if len(bt) < 12:
        return {}
    # 十六分格:相鄰拍之間切四等分
    grid = np.concatenate([np.linspace(bt[i], bt[i + 1], 5)[:4] for i in range(len(bt) - 1)])
    nbar = len(grid) // 16
    f = {}
    for s, y in ys.items():
        if 10 * np.log10(np.mean(y ** 2) / tot + 1e-12) < -30:
            continue
        env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
        t = librosa.frames_to_time(np.arange(len(env)), sr=SR, hop_length=HOP)
        w = int(0.03 * SR / HOP)
        slot = np.array([env[max(0, i - w):i + w + 1].max() if i < len(env) else 0
                         for i in np.searchsorted(t, grid[:nbar * 16])])
        thr = np.percentile(env, 60)                      # 低於這個算沒有起音
        bars = slot.reshape(nbar, 16)
        prof = [b / (b.max() + 1e-9) for b in bars if b.max() > thr]
        if len(prof) < 4:
            continue
        on = [p > 0.35 for p in prof]
        # 律動輪廓(docs/PLAN.md 的主尺):四種位置的平均強度。小節從哪一拍開始量不出來,但四種位置比得準
        P = np.mean(prof, 0)
        for nm, ix in (('正拍', [0, 4, 8, 12]), ('e', [1, 5, 9, 13]), ('&', [2, 6, 10, 14]), ('a', [3, 7, 11, 15])):
            f[f'{s}.位置.{nm}'] = round(float(P[ix].mean()), 3)
        f[f'{s}.相鄰相似'] = round(float(np.mean([cos(prof[i], prof[i + 1]) for i in range(len(prof) - 1)])), 3)
        f[f'{s}.隔一相似'] = round(float(np.mean([cos(prof[i], prof[i + 2]) for i in range(len(prof) - 2)])), 3)
        f[f'{s}.同型比例'] = round(float(np.mean([np.array_equal(on[i], on[i + 1]) for i in range(len(on) - 1)])), 3)
        cv = [np.std(p[p > 0.35]) / (np.mean(p[p > 0.35]) + 1e-9) for p in prof if (p > 0.35).sum() >= 2]
        if cv:
            f[f'{s}.輕重對比'] = round(float(np.mean(cv)), 3)
        dn = [p[[0, 4, 8, 12]].mean() / (p[[i for i in range(16) if i % 4 and p[i] > 0.35]].mean() + 1e-9)
              for p in prof if any(p[i] > 0.35 for i in range(16) if i % 4)]
        if dn:
            f[f'{s}.正拍比'] = round(float(np.mean(dn)), 3)
    return f


def auc(a, b):
    return float(np.mean([(x > y) + 0.5 * (x == y) for x in a for y in b]))


def report(groups):
    real = {**groups.get('real', {}), **{'mix_' + k: v for k, v in groups.get('realmix', {}).items()}}
    G = {'real': real, 'suno': groups['suno'], 'ours': groups['ours']}
    rng = np.random.default_rng(0)
    keys = sorted({k for g in G.values() for f in g.values() for k in f})
    zf = lambda v: (np.mean(v['ours']) - np.mean(np.r_[v['real'], v['suno']])) / (np.std(np.r_[v['real'], v['suno']]) + 1e-9)
    sf_ = lambda v: abs(auc(list(v['real']), list(v['suno'])) - 0.5) * 2
    rows = []
    for k in keys:
        v = {g: np.array([f[k] for f in G[g].values() if k in f]) for g in G}
        if min(len(x) for x in v.values()) < 3:
            continue
        bz = [zf({g: rng.choice(x, len(x)) for g, x in v.items()}) for _ in range(2000)]
        bs = [sf_({g: rng.choice(x, len(x)) for g, x in v.items()}) for _ in range(2000)]
        zlo, zhi = np.percentile(bz, [2.5, 97.5]); shi = np.percentile(bs, 97.5)
        st = (zlo > 0 or zhi < 0) and shi < 0.6
        rows.append((k, zf(v), zlo, zhi, sf_(v), shi, st, v['real'].mean(), v['suno'].mean(), v['ours'].mean(),
                     {g: len(x) for g, x in v.items()}))
    print('特徵              我們的 z [95%]            真歌vsSuno分離度(上限)  判定  真歌   Suno   我們   n')
    out = []
    for r in sorted(rows, key=lambda x: (not x[6], -abs(x[1]))):
        k, z, lo, hi, s, shi, st, a, b, c, n = r
        print(f'{k:16s} {z:+6.2f} [{lo:+6.2f},{hi:+6.2f}]   {s:.2f} ({shi:.2f})   {"穩定" if st else "趨勢"}  '
              f'{a:6.3f} {b:6.3f} {c:6.3f}  {n["real"]}/{n["suno"]}/{n["ours"]}')
        out.append({'特徵': k, 'z': round(z, 2), 'z95': [round(lo, 2), round(hi, 2)], '分離度上限': round(shi, 2),
                    '穩定': bool(st), '真歌': a, 'Suno': b, '我們': c, 'n': n})
    return out


# 總分 D 用的特徵(docs/PLAN.md 第 2 節):滲漏超過差距 30% 的不收(第七輪量:guitar.相鄰相似 47%)
ADOPT = [f'{s}.位置.{p}' for s in ('drums', 'bass', 'guitar') for p in ('正拍', 'e', '&', 'a')] + ['other.輕重對比']


def ref_of(groups):
    return list(groups.get('real', {}).values()) + list(groups.get('realmix', {}).values()) + list(groups.get('suno', {}).values())


def score(ref, clips, keys=ADOPT):
    """總分 D:每個特徵「我們的平均」到參考組四分位範圍的距離 ÷ 四分位寬度,加總(在範圍內 = 0)"""
    D, parts = 0.0, {}
    for k in keys:
        r = np.array([f[k] for f in ref if k in f]); o = [f[k] for f in clips if k in f]
        if len(r) < 5 or not o:
            continue
        lo, hi = np.percentile(r, [25, 75]); m = float(np.mean(o))
        d = max(lo - m, m - hi, 0) / (hi - lo + 1e-9)
        parts[k] = {'我們': round(m, 3), '參考25–75': [round(lo, 3), round(hi, 3)], '距離': round(d, 2)}
        D += d
    return round(D, 2), parts


def main():
    groups = json.load(open(DB)) if os.path.exists(DB) else {}
    if '--report' not in sys.argv:
        for g in [a for a in sys.argv[1:] if not a.startswith('-')] or ['real', 'realmix', 'suno', 'ours']:
            dirs = sorted(glob.glob(f'/tmp/sty/sep_{g}/htdemucs_6s/*/'))
            groups[g] = {os.path.basename(d.rstrip('/')): feats(d) for d in dirs}
            print(g, len(dirs), '段', flush=True)
        json.dump(groups, open(DB, 'w'), ensure_ascii=False, indent=1, default=float)
    rep = report(groups)
    json.dump({'說明': '穩定 = z 的 95% 區間不跨 0,且真歌 vs Suno 分離度上限 < 0.6;bootstrap 2000 次,種子 0;真歌 = 上傳 + 合集',
               '結果': rep}, open(os.path.join(H, 'db', 'vary_report.json'), 'w'), ensure_ascii=False, indent=1, default=float)


if __name__ == '__main__':
    main()
