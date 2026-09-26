#!/usr/bin/env python3
"""亮度兩種算法並列(REVIEW.md 第三輪建議 5):
  全部格子平均(style.py 的算法)vs 只算有聲的格子取中位數(instgram.py 的算法:RMS > 該軌最大的 −30dB)
  /tmp/abx/bin/python bright_active.py            → 讀 /tmp/sty/sep_{real,realmix,suno,ours}/htdemucs_6s/*/"""
import glob, os, numpy as np, soundfile as sf, librosa
SR = 22050; hop = 512
out = {}
for g in ('real', 'realmix', 'suno', 'ours'):
    for s in ('guitar', 'piano', 'other'):
        allm, act = [], []
        for d in sorted(glob.glob(f'/tmp/sty/sep_{g}/htdemucs_6s/*/')):
            x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
            y = librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
            if 10 * np.log10(np.mean(y ** 2) + 1e-12) < -60: continue
            c = librosa.feature.spectral_centroid(y=y, sr=SR, hop_length=hop)[0]
            rms = librosa.feature.rms(y=y, hop_length=hop)[0]; thr = rms.max() * 10 ** (-30 / 20)
            allm.append(c.mean()); act.append(np.median(c[rms > thr]))
        out[(g, s)] = (allm, act)
import sys
if len(sys.argv) > 1 and sys.argv[1] == 'leak':
    # 人聲滲漏:sep_ours 對 sep_oursmel 的 other 有聲中位,逐段配對,bootstrap 2000 次,種子 0
    def act(d):
        x, sr = sf.read(os.path.join(d, 'other.wav'), always_2d=True, dtype='float32')
        y = librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
        c = librosa.feature.spectral_centroid(y=y, sr=SR, hop_length=hop)[0]; r = librosa.feature.rms(y=y, hop_length=hop)[0]
        return np.median(c[r > r.max() * 10 ** (-30 / 20)])
    ids = sorted(os.path.basename(d.rstrip('/')) for d in glob.glob('/tmp/sty/sep_ours/htdemucs_6s/*/'))
    dl = np.array([act(f'/tmp/sty/sep_oursmel/htdemucs_6s/{i}') - act(f'/tmp/sty/sep_ours/htdemucs_6s/{i}') for i in ids])
    rng = np.random.default_rng(0)
    lo, hi = np.percentile([rng.choice(dl, len(dl)).mean() for _ in range(2000)], [2.5, 97.5])
    print(f'other 有聲中位 滲漏 {dl.mean():+.0f}Hz [{lo:+.0f}, {hi:+.0f}] n={len(dl)}'); sys.exit()
rng = np.random.default_rng(0)
for s in ('guitar', 'piano', 'other'):
    ref = np.array(out[('real', s)][1] + out[('realmix', s)][1] + out[('suno', s)][1]); ours = np.array(out[('ours', s)][1])
    bs = [rng.choice(ours, len(ours)).mean() - rng.choice(ref, len(ref)).mean() for _ in range(2000)]
    print(s, f'我們 − 參考(真歌 + 合集 + Suno)有聲中位 {ours.mean() - ref.mean():+.0f}Hz [95% {np.percentile(bs, 2.5):+.0f}, {np.percentile(bs, 97.5):+.0f}]  n={len(ref)}/{len(ours)}')
    ref2 = np.array(out[('real', s)][1] + out[('suno', s)][1])
    bs2 = [rng.choice(ours, len(ours)).mean() - rng.choice(ref2, len(ref2)).mean() for _ in range(2000)]
    print(' ' * len(s), f'我們 − 參考(只用上傳真歌 + Suno)     {ours.mean() - ref2.mean():+.0f}Hz [95% {np.percentile(bs2, 2.5):+.0f}, {np.percentile(bs2, 97.5):+.0f}]  n={len(ref2)}/{len(ours)}')
    for g in ('real', 'realmix', 'suno', 'ours'):
        a, b = out[(g, s)]
        print(f'  {g:8s} n={len(a):2d}  全部平均 {np.mean(a):6.0f}  有聲中位 {np.mean(b):6.0f}  (有聲中位的四分位 {np.percentile(b,25):.0f}–{np.percentile(b,75):.0f})')
