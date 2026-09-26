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
rng = np.random.default_rng(0)
for s in ('guitar', 'piano', 'other'):
    ref = np.array(out[('real', s)][1] + out[('realmix', s)][1] + out[('suno', s)][1]); ours = np.array(out[('ours', s)][1])
    bs = [rng.choice(ours, len(ours)).mean() - rng.choice(ref, len(ref)).mean() for _ in range(2000)]
    print(s, f'我們 − 參考(真歌 26 + Suno)有聲中位 {ours.mean() - ref.mean():+.0f}Hz [95% {np.percentile(bs, 2.5):+.0f}, {np.percentile(bs, 97.5):+.0f}]  n={len(ref)}/{len(ours)}')
    for g in ('real', 'realmix', 'suno', 'ours'):
        a, b = out[(g, s)]
        print(f'  {g:8s} n={len(a):2d}  全部平均 {np.mean(a):6.0f}  有聲中位 {np.mean(b):6.0f}  (有聲中位的四分位 {np.percentile(b,25):.0f}–{np.percentile(b,75):.0f})')
