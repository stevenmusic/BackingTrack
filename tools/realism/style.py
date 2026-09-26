#!/usr/bin/env python3
"""City Pop「風格尺」(2026-09-26):**真歌與 Suno 都算正確答案**,找它們兩邊一致、我們不一樣的特徵。

舊的「像真人」尺(humanlike.py)把 Suno 當 0%,結果獎勵的是「跟真歌像、跟 Suno 不像」的節奏細節——
但使用者聽起來 Suno 是好的 City Pop。風格特徵應該是**真歌與 Suno 共有**的東西。

輸入:htdemucs_6s 的分軌資料夾(drums / bass / guitar / piano / other / vocals.wav)
  /tmp/abx/bin/python style.py            → 讀 /tmp/sty/sep_{real,suno,ours}/htdemucs_6s/*/
輸出:db/style.json(每一段的特徵)+ 印出排名

特徵(都是「聽得出來」的,不是十六分格子的細節):
- 各樂器佔伴奏的 dB(人聲不算)、亮度(頻譜重心)、立體聲寬度(1 − L/R 相關)
- 每拍幾個起音(密度)、小節之間的音量起伏(編曲有沒有在動)
- 和聲色彩:和聲樂器(吉他 + 鋼琴 + 其他)的能量有多少落在三和弦之外(七、九、十一、十三度)
- 殘響感:起音之後 150–400ms 的能量佔比
"""
import glob, os, json, sys
import numpy as np, soundfile as sf, librosa

SR = 22050
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other']
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
    # 和聲色彩:和聲樂器合起來的 chroma,每拍找最像的大/小三和弦,量三和弦外的能量比例
    hy = ys['guitar'] + ys['piano'] + ys['other']
    C = librosa.feature.chroma_cqt(y=hy, sr=SR)
    tri = [(r, q) for r in range(12) for q in ((0, 4, 7), (0, 3, 7))]
    out, sev, ext = [], [], []
    bf = list(beats) + [C.shape[1]]
    for a, b in zip(bf[:-1], bf[1:]):
        c = C[:, a:b].mean(1) if b > a else None
        if c is None or c.sum() == 0:
            continue
        r, q = max(tri, key=lambda t: sum(c[(t[0] + i) % 12] for i in t[1]))
        tot_c = c.sum()
        out.append(1 - sum(c[(r + i) % 12] for i in q) / tot_c)
        sev.append((c[(r + 10) % 12] + c[(r + 11) % 12]) / tot_c)        # 七度
        ext.append((c[(r + 2) % 12] + c[(r + 5) % 12] + c[(r + 9) % 12]) / tot_c)   # 9 / 11 / 13
    f['和聲.三和弦外'] = round(float(np.mean(out)), 3)
    f['和聲.七度'] = round(float(np.mean(sev)), 3)
    f['和聲.延伸音'] = round(float(np.mean(ext)), 3)
    f['速度'] = round(float(np.atleast_1d(tempo)[0]), 1)
    return f


def auc(a, b):
    """a 比 b 大的機率(0.5 = 分不開)"""
    if not a or not b:
        return None
    return float(np.mean([(x > y) + 0.5 * (x == y) for x in a for y in b]))


def main():
    groups = {}
    for g in ('real', 'suno', 'ours'):
        dirs = sorted(glob.glob(f'/tmp/sty/sep_{g}/htdemucs_6s/*/'))
        groups[g] = {os.path.basename(d.rstrip('/')): feats(d) for d in dirs}
        print(g, len(dirs), '段', flush=True)
    json.dump(groups, open(os.path.join(H, 'db', 'style.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    keys = sorted({k for g in groups.values() for f in g.values() for k in f})
    rows = []
    for k in keys:
        v = {g: [f[k] for f in groups[g].values() if k in f] for g in groups}
        if min(len(v['real']), len(v['suno']), len(v['ours'])) < 3:
            continue
        ref = v['real'] + v['suno']
        mu, sd = np.mean(ref), np.std(ref) + 1e-9
        rs = abs(auc(v['real'], v['suno']) - 0.5) * 2       # 0 = 真歌與 Suno 一致、1 = 完全分得開
        z = (np.mean(v['ours']) - mu) / sd
        rows.append((k, z, rs, np.mean(v['real']), np.mean(v['suno']), np.mean(v['ours'])))
    # 風格特徵:真歌與 Suno 一致(rs 小)、我們差很多(|z| 大)
    print('\n特徵                 我們的 z   真歌vsSuno分離度   真歌    Suno    我們')
    for k, z, rs, r, s, o in sorted(rows, key=lambda x: -abs(x[1]) * (1 - x[2])):
        print(f'{k:18s} {z:+6.2f}      {rs:.2f}        {r:8.3f} {s:8.3f} {o:8.3f}')


if __name__ == '__main__':
    main()
