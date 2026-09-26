#!/usr/bin/env python3
"""City Pop「風格尺」(2026-09-26):**真歌與 Suno 都算正確答案**,找它們兩邊一致、我們不一樣的特徵。

舊的「像真人」尺(humanlike.py)把 Suno 當 0%,結果獎勵的是「跟真歌像、跟 Suno 不像」的節奏細節——
但使用者聽起來 Suno 是好的 City Pop。風格特徵應該是**真歌與 Suno 共有**的東西。

輸入:htdemucs_6s 的分軌資料夾(drums / bass / guitar / piano / other / vocals.wav)
  /tmp/abx/bin/python style.py [組…] [--reuse] [--merge-mix]
    組 = /tmp/sty/sep_<組>/htdemucs_6s/*/,預設 real suno ours;只重算指定的組,其餘保留在 db/style.json
    --reuse:已經在 db/style.json 的組不重算(例如只加 oursmel:`style.py oursmel --reuse`)
    --merge-mix:把 realmix(真歌合集)併進真歌再排名(不改 style.json)
輸出:db/style.json(每一段的特徵)、db/style_report.json(排名與 bootstrap 95% 區間、各組樣本數)

特徵(都是「聽得出來」的,不是十六分格子的細節):
- 各樂器佔伴奏的 dB(人聲不算)、亮度(頻譜重心)、立體聲寬度(1 − L/R 相關)
- 每拍幾個起音(密度)、小節之間的音量起伏(編曲有沒有在動)
- 和聲色彩:和聲樂器(吉他 + 鋼琴 + 其他)的能量有多少落在和弦模板之外。兩套模板並列:
  `和聲.*` 只有大小三和弦、`和聲7.*` 加上 maj7 / m7 / 7 / m7b5;`延伸音` = 九、十一、十三度
- 殘響感:起音之後 150–400ms 的能量佔比
"""
import glob, os, json, sys
import numpy as np, soundfile as sf, librosa

SR = 22050
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other']
TRI = [(0, 4, 7), (0, 3, 7)]
SEV = TRI + [(0, 4, 7, 11), (0, 3, 7, 10), (0, 4, 7, 10), (0, 3, 6, 10)]
GROUPS = [g for g in sys.argv[1:] if not g.startswith('-')] or ['real', 'suno', 'ours']
B = 2000
H = os.path.dirname(os.path.abspath(__file__))


def load(d, s, mono=True):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    if mono:
        return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
    return x, sr


def db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-12)


def feats(d):
    f = {}
    ys = {s: load(d, s) for s in STEMS}
    tot = 10 * np.log10(sum(np.mean(y ** 2) for y in ys.values()) + 1e-12)
    tempo, beats = librosa.beat.beat_track(y=ys['drums'] + ys['bass'], sr=SR)
    nb = max(1, len(beats))
    for s, y in ys.items():
        lv = db(y)
        f[f'{s}.佔比dB'] = round(lv - tot, 2)
        if lv - tot < -30:            # 幾乎不存在的軌,其他特徵不量
            continue
        f[f'{s}.亮度Hz'] = round(float(np.mean(librosa.feature.spectral_centroid(y=y, sr=SR))), 0)
        on = librosa.onset.onset_detect(y=y, sr=SR, units='time')
        f[f'{s}.每拍起音'] = round(len(on) / nb, 2)
        # 小節之間的音量起伏:每 4 拍的 RMS 的標準差(dB)
        bt = librosa.frames_to_time(beats, sr=SR)
        if len(bt) > 8:
            bars = [y[int(bt[i] * SR):int(bt[i + 4] * SR)] for i in range(0, len(bt) - 4, 4)]
            f[f'{s}.小節起伏dB'] = round(float(np.std([db(b) for b in bars if len(b)])), 2)
        x2, _ = load(d, s, mono=False)
        if x2.shape[1] == 2:
            c = np.corrcoef(x2[:, 0], x2[:, 1])[0, 1]
            f[f'{s}.寬度'] = round(float(1 - c), 3)
        # 殘響感:起音後 150–400ms 的能量 ÷ 起音後 0–150ms
        env = librosa.feature.rms(y=y, hop_length=256)[0]
        fr = librosa.time_to_frames(on, sr=SR, hop_length=256)
        k1, k2 = int(0.15 * SR / 256), int(0.4 * SR / 256)
        r = [env[i + k1:i + k2].mean() / (env[i:i + k1].mean() + 1e-9) for i in fr if i + k2 < len(env)]
        if r:
            f[f'{s}.殘響比'] = round(float(np.median(r)), 3)
    # 和聲色彩:和聲樂器合起來的 chroma,每拍找最像的和弦,量模板外的能量比例。
    # 兩套模板都量(REVIEW.md B2):只有大小三和弦(舊的,`和聲.*`)與加上 maj7 / m7 / 7 / m7b5(`和聲7.*`)。
    # 只有三和弦的模板會把 maj7 的七度算成「三和弦外」,所以兩套要並列看
    hy = ys['guitar'] + ys['piano'] + ys['other']
    C = librosa.feature.chroma_cqt(y=hy, sr=SR)
    bf = list(beats) + [C.shape[1]]
    for tag, Q in (('和聲', TRI), ('和聲7', SEV)):
        out, sev, ext = [], [], []
        for a, b in zip(bf[:-1], bf[1:]):
            if b <= a:
                continue
            c = C[:, a:b].mean(1)
            if c.sum() == 0:
                continue
            r, q = max(((r, q) for r in range(12) for q in Q),
                       key=lambda t: sum(c[(t[0] + i) % 12] for i in t[1]) / len(t[1]) ** 0.5)
            tot_c = c.sum()
            out.append(1 - sum(c[(r + i) % 12] for i in q) / tot_c)
            sev.append(sum(c[(r + i) % 12] for i in (10, 11) if i not in q) / tot_c)          # 模板外的七度
            ext.append((c[(r + 2) % 12] + c[(r + 5) % 12] + c[(r + 9) % 12]) / tot_c)        # 9 / 11 / 13
        f[f'{tag}.模板外'] = round(float(np.mean(out)), 3)
        f[f'{tag}.七度'] = round(float(np.mean(sev)), 3)
        f[f'{tag}.延伸音'] = round(float(np.mean(ext)), 3)
    f['速度'] = round(float(np.atleast_1d(tempo)[0]), 1)
    return f


def auc(a, b):
    """a 比 b 大的機率(0.5 = 分不開)"""
    if not a or not b:
        return None
    return float(np.mean([(x > y) + 0.5 * (x == y) for x in a for y in b]))


def boot(v, fn, rng):
    """bootstrap:每一組各自重抽,回 95% 信賴區間"""
    vals = [fn({g: rng.choice(x, len(x)) for g, x in v.items()}) for _ in range(B)]
    return np.percentile(vals, [2.5, 97.5])


def main():
    cache = os.path.join(H, 'db', 'style.json')
    # 一律先讀舊檔,只覆寫這次指定的組(不然 oursmel 那種實驗組會被蓋掉);--reuse = 已經有的組也不重算
    groups = json.load(open(cache)) if os.path.exists(cache) else {}
    for g in GROUPS:
        if g in groups and '--reuse' in sys.argv:
            continue
        dirs = sorted(glob.glob(f'/tmp/sty/sep_{g}/htdemucs_6s/*/'))
        groups[g] = {os.path.basename(d.rstrip('/')): feats(d) for d in dirs}
        print(g, len(dirs), '段', flush=True)
    json.dump(groups, open(cache, 'w'), ensure_ascii=False, indent=1, default=float)
    # --merge-mix:真歌合集(realmix,照時間碼切的 13 首)併進真歌。併之前先確認兩組分不開(REVIEW.md 第一輪 B3)
    if '--merge-mix' in sys.argv and 'realmix' in groups:
        groups = dict(groups, real={**groups['real'], **{'mix_' + k: v for k, v in groups['realmix'].items()}})
    rng = np.random.default_rng(0)
    keys = sorted({k for g in ('real', 'suno', 'ours') for f in groups[g].values() for k in f})
    rows = []
    zf = lambda v: (np.mean(v['ours']) - np.mean(np.r_[v['real'], v['suno']])) / (np.std(np.r_[v['real'], v['suno']]) + 1e-9)
    sf_ = lambda v: abs(auc(list(v['real']), list(v['suno'])) - 0.5) * 2
    for k in keys:
        v = {g: np.array([f[k] for f in groups[g].values() if k in f]) for g in ('real', 'suno', 'ours')}
        if min(len(x) for x in v.values()) < 3:
            continue
        z, rs = zf(v), sf_(v)
        zlo, zhi = boot(v, zf, rng)
        slo, shi = boot(v, sf_, rng)
        stable = (zlo > 0 or zhi < 0) and shi < 0.6
        rows.append((k, z, zlo, zhi, rs, slo, shi, stable, v['real'].mean(), v['suno'].mean(), v['ours'].mean(),
                     {g: len(x) for g, x in v.items()}))
    rep = []
    print('\n特徵              我們的 z [95%CI]          真歌vsSuno分離度 [95%CI]   穩定  真歌  Suno  我們')
    for r in sorted(rows, key=lambda x: (not x[7], -abs(x[1]) * (1 - x[4]))):
        k, z, zlo, zhi, rs, slo, shi, st, a, b, c, n = r
        print(f'{k:16s} {z:+6.2f} [{zlo:+6.2f},{zhi:+6.2f}]   {rs:.2f} [{slo:.2f},{shi:.2f}]   {"穩定" if st else "趨勢"}  '
              f'{a:8.3f} {b:8.3f} {c:8.3f}')
        rep.append({'特徵': k, 'z': round(z, 2), 'z95': [round(zlo, 2), round(zhi, 2)], '分離度': round(rs, 2),
                    '分離度95': [round(slo, 2), round(shi, 2)], '穩定': bool(st), '真歌': a, 'Suno': b, '我們': c, 'n': n})
    json.dump({'說明': '穩定 = z 的 95% 區間不跨 0,且真歌 vs Suno 分離度的區間上限 < 0.6;其餘只能算趨勢。bootstrap 2000 次,各組各自重抽',
               '併了真歌合集': '--merge-mix' in sys.argv,
               '結果': rep}, open(os.path.join(H, 'db', 'style_report.json'), 'w'), ensure_ascii=False, indent=1, default=float)


if __name__ == '__main__':
    main()
