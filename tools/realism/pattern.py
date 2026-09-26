#!/usr/bin/env python3
"""**驗證未過(2026-09-26),不要拿它的數字當依據**:拿我們自己的錄音驗證,大鼓在 16 格都偵測到(62–99%)、
小鼓在第 1、3 拍也偵測到,小節線找錯(貝斯第一格只有 31%)。鼓分軌用頻段拆不開大鼓 / 小鼓 / hi-hat。
見 docs/PLAN.md「目前進度」。

City Pop「每一格打多少、打多重」逆向量測(docs/PLAN.md 第 3 節:**先量真歌,再照著設定**,不猜)。

每一首:鼓 + 貝斯抓拍點 → 每拍切 4 格(十六分)。鼓分軌再用頻段拆成
  大鼓(< 150Hz)、小鼓(200–2500Hz)、hi-hat(> 6kHz)三條 onset strength。
**找小節線**:試 4 種起點,挑「小鼓落在第 2、4 拍、大鼓落在第 1、3 拍」最明顯的那一種。
每一格輸出兩個數:
  出現率 = 這一格有起音的小節比例(強度 > 這首這條線 95 百分位的 30%)
  強度   = 有起音時的平均強度(÷ 95 百分位)
對象:drums 的三條頻段、bass、guitar、piano、other

  /tmp/abx/bin/python pattern.py [組…]      預設 real realmix suno ours;結果 db/pattern.json
  /tmp/abx/bin/python pattern.py --table    印參考組(真歌 26 + Suno 16)與我們的 16 格表
"""
import glob, os, json, sys
import numpy as np, soundfile as sf, librosa

SR = 22050
HOP = 128
H = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(H, 'db', 'pattern.json')
BANDS = {'kick': (0, 100), 'snare': (1500, 5000), 'hat': (7000, 11000)}
STEMS = ['bass', 'guitar', 'piano', 'other']


def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)


def band_env(y, lo, hi):
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=HOP))
    fr = librosa.fft_frequencies(sr=SR, n_fft=1024)
    return librosa.onset.onset_strength(S=librosa.amplitude_to_db(S[(fr >= lo) & (fr < hi)] + 1e-9), sr=SR, hop_length=HOP)


def slots(env, grid):
    """真的起音(尖峰)對到最近的格子,±35ms 內才算;沒有起音的格子 = 0。強度 ÷ 這條線尖峰的 90 百分位"""
    pk = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP, units='frames')
    v = np.zeros(len(grid))
    if not len(pk):
        return v
    t = librosa.frames_to_time(pk, sr=SR, hop_length=HOP); a = env[pk] / (np.percentile(env[pk], 90) + 1e-9)
    for ti, ai in zip(t, a):
        j = int(np.argmin(np.abs(grid - ti)))
        if abs(grid[j] - ti) <= 0.035:
            v[j] = max(v[j], ai)
    return v


def one(d):
    dr, ba = load(d, 'drums'), load(d, 'bass')
    _, beats = librosa.beat.beat_track(y=dr + ba, sr=SR, hop_length=HOP)
    bt = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)
    if len(bt) < 13:
        return None
    grid = np.concatenate([np.linspace(bt[i], bt[i + 1], 5)[:4] for i in range(len(bt) - 1)])
    lines = {k: slots(band_env(dr, *b), grid) for k, b in BANDS.items()}
    for s in STEMS:
        y = load(d, s)
        lines[s] = slots(librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP), grid)
    # 小節線:起點 o(0–3 拍)讓「小鼓在 2、4 拍 − 1、3 拍」+「大鼓在 1、3 拍 − 2、4 拍」最大
    best, bo = -1e9, 0
    for o in range(4):
        n = (len(grid) - o * 4) // 16
        if n < 3:
            continue
        sn = lines['snare'][o * 4:o * 4 + n * 16].reshape(n, 16).mean(0)
        kk = lines['kick'][o * 4:o * 4 + n * 16].reshape(n, 16).mean(0)
        sc = sn[4] + sn[12] - sn[0] - sn[8] + kk[0] + kk[8] - kk[4] - kk[12]
        if sc > best:
            best, bo = sc, o
    n = (len(grid) - bo * 4) // 16
    out = {'小節數': int(n), '小節線分數': round(float(best), 3)}
    for k, v in lines.items():
        m = v[bo * 4:bo * 4 + n * 16].reshape(n, 16)
        on = m > 0.15
        out[k] = {'出現率': on.mean(0).round(3).tolist(),
                  '強度': [round(float(m[on[:, i], i].mean()), 3) if on[:, i].any() else 0 for i in range(16)]}
    return out


def table(g):
    ref = [x for k in ('real', 'realmix', 'suno') for x in g.get(k, {}).values() if x]
    ours = [x for x in g.get('ours', {}).values() if x]
    print(f'參考 {len(ref)} 首、我們 {len(ours)} 段;小節線分數中位 參考 {np.median([x["小節線分數"] for x in ref]):.2f} / 我們 {np.median([x["小節線分數"] for x in ours]):.2f}')
    for k in list(BANDS) + STEMS:
        for q in ('出現率', '強度'):
            R = np.array([x[k][q] for x in ref if k in x]); O = np.array([x[k][q] for x in ours if k in x])
            print(f'\n{k} {q}      ' + ' '.join(f'{i:>5}' for i in range(16)))
            print('  參考中位 ' + ' '.join(f'{v:5.2f}' for v in np.median(R, 0)))
            print('  參考25%  ' + ' '.join(f'{v:5.2f}' for v in np.percentile(R, 25, 0)))
            print('  參考75%  ' + ' '.join(f'{v:5.2f}' for v in np.percentile(R, 75, 0)))
            print('  我們     ' + ' '.join(f'{v:5.2f}' for v in np.mean(O, 0)))


def main():
    g = json.load(open(DB)) if os.path.exists(DB) else {}
    if '--table' not in sys.argv:
        for grp in [a for a in sys.argv[1:] if not a.startswith('-')] or ['real', 'realmix', 'suno', 'ours']:
            g[grp] = {os.path.basename(d.rstrip('/')): one(d) for d in sorted(glob.glob(f'/tmp/sty/sep_{grp}/htdemucs_6s/*/'))}
            print(grp, len(g[grp]), flush=True)
        json.dump(g, open(DB, 'w'), ensure_ascii=False, indent=1, default=float)
    table(g)


if __name__ == '__main__':
    main()
