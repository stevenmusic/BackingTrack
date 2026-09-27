#!/usr/bin/env python3
"""Weresax(Karoryfer,CC0)中音薩克斯 forte / 電容麥(cnd)逐顆量:音高(音分)、音頭響度、起音多快 → index.html 的 `BRASS_SMP.sax`。
量法跟 brass_meas.py 一樣:起音(> 最大值 10%)後 50–290ms 用 pyin 量音高;dB = 起音後 150ms 的 RMS。
另外印「起音到 90% 最大值要幾毫秒」:這是長音取樣,拿來當斷奏要音頭夠快。
  /tmp/abx/bin/python tools/realism/sax_meas.py [/tmp/smp/karoryfer.weresax]
"""
import sys, os, re
import numpy as np, soundfile as sf, librosa
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/smp/karoryfer.weresax'
PC = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
def midi(lab):                       # 檔名 db2 = key 49(sfz 的 pitch_keycenter)
    m = re.match(r'([a-g])(b?)(\d)', lab)
    return (int(m.group(3)) + 2) * 12 + PC[m.group(1)] - (1 if m.group(2) else 0)
labs = sorted({f.split('_')[0] for f in os.listdir(os.path.join(ROOT, 'Samples/alto')) if '_f_' in f and 'cnd' in f}, key=midi)
rows = []
for lab in labs:
    m0 = midi(lab); cents, dbs, atk = [], [], []
    for r in (1, 2):
        x, sr = sf.read(os.path.join(ROOT, f'Samples/alto/{lab}_f_rr{r}_cnd.wav'), always_2d=True)
        y = x.mean(1); a = np.abs(y); on = int(np.argmax(a > a.max() * 0.1))
        env = np.convolve(a, np.ones(64) / 64, 'same'); pk = env[on:on + int(0.4 * sr)]
        atk.append(round(float(np.argmax(pk > pk.max() * 0.9) / sr * 1000)))
        seg = y[on + int(0.05 * sr):on + int(0.29 * sr)]
        f0, vo, _ = librosa.pyin(seg, fmin=librosa.midi_to_hz(m0 - 3), fmax=librosa.midi_to_hz(m0 + 3), sr=sr,
                                 frame_length=2048, hop_length=256, resolution=0.01)
        f = f0[vo & ~np.isnan(f0)]
        cents.append(int(round((librosa.hz_to_midi(np.median(f)) - m0) * 100)) if len(f) else 0)
        dbs.append(round(float(20 * np.log10(np.sqrt(np.mean(y[on:on + int(0.15 * sr)] ** 2)))), 1))
    rows.append(f'[{m0}, "{lab}", [{cents[0]}, {cents[1]}], [{dbs[0]}, {dbs[1]}]]')
    print(lab, m0, cents, dbs, '起音 ms', atk, file=sys.stderr)
print('sax:', ', '.join(rows))
