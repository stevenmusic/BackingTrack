#!/usr/bin/env python3
"""VSCO-2-CE 小號 / 長號斷奏(v3)逐顆量:真的音高(音分偏差)與音頭響度 → index.html 的 `BRASS_SMP` 表。

**時間窗**:從起音(> 最大值 10%,跟 `leadOf` 同一個門檻)後 50ms 到 290ms。
- 跳過前 50ms:管樂的音頭有嘴唇咬到位之前的上滑,那一段偏低(小號量到 −15～−46 音分),不是這顆音的音高
- 到 290ms:stab 在 0.22 秒開始收、時間常數 0.07,聽得到的就是這一段(`playBrassSmp`)
音高用 librosa.pyin(比 yin 穩;resolution 0.01 = 1 音分一格,預設 10 音分太粗),取有聲格子的中位數;dB = 起音後 150ms 的 RMS(`BRASS_TARGET` 拉平用)。

  /tmp/abx/bin/python tools/realism/brass_meas.py [/tmp/smp/VSCO-2-CE]
"""
import sys, glob, re, os
import numpy as np, soundfile as sf, librosa

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/smp/VSCO-2-CE'
SETS = [('tpt', 'Brass/Trumpet/stac/Sum_SHTrumpet_stac_{}_v2_rr{}.wav'),
        ('tbn', 'Brass/Tenor Trombone/stac/tenortbn_stac_{}_v2_rr{}.wav')]
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def nominal(lab):                       # 檔名的八度比標準低一個:A2 = midi 57
    m = re.match(r'([A-G])(#?)(\d)', lab)
    return (int(m.group(3)) + 2) * 12 + PC[m.group(1)] + (1 if m.group(2) else 0)


for ins, pat in SETS:
    labs = sorted({re.search(r'stac_([A-G]#?\d)_v2', f).group(1)
                   for f in glob.glob(os.path.join(ROOT, pat.format('*', '*')))}, key=nominal)
    rows = []
    for lab in labs:
        m0 = nominal(lab); cents, dbs = [], []
        for r in (1, 2):
            x, sr = sf.read(os.path.join(ROOT, pat.format(lab, r)), always_2d=True)
            y = x.mean(1); a = np.abs(y); on = int(np.argmax(a > a.max() * 0.1))
            seg = y[on + int(0.05 * sr):on + int(0.29 * sr)]
            f0, vo, _ = librosa.pyin(seg, fmin=librosa.midi_to_hz(m0 - 3), fmax=librosa.midi_to_hz(m0 + 3),
                                     sr=sr, frame_length=2048, hop_length=256, resolution=0.01)
            f = f0[vo & ~np.isnan(f0)]
            cents.append(int(round((librosa.hz_to_midi(np.median(f)) - m0) * 100)) if len(f) else 0)
            dbs.append(round(float(20 * np.log10(np.sqrt(np.mean(y[on:on + int(0.15 * sr)] ** 2)))), 1))
        rows.append(f'[{m0}, "{lab}", [{cents[0]}, {cents[1]}], [{dbs[0]}, {dbs[1]}]]')
    print(ins + ':', ', '.join(rows))
