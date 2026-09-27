#!/usr/bin/env python3
"""GuitarSet(CC BY 4.0,Xi et al. ISMIR 2018)的放克伴奏(36 段、6 位樂手、97–119 BPM)→ 切音吉他的**律動範本**:
一拍四格(正拍 / e / & / a)各自「出現率、早晚(毫秒)、力度(相對正拍的 dB)」。
- 刷弦 = 各弦音頭 30ms 內的合成一下,時間取最早那條弦
- 格子與早晚:用樂手錄音時的節拍標註(beat_position)內插,一拍切四格
- 力度:麥克風錄音起音後 60ms 的 RMS(每段自己的中位數當 0dB)
資料:zenodo.org/records/3371780 的 annotation.zip 與 audio_mono-mic.zip(只取 *Funk*comp*)
  /tmp/abx/bin/python tools/realism/gs_groove.py /tmp/gs
"""
import sys, os, glob, json
import numpy as np, soundfile as sf

root = sys.argv[1] if len(sys.argv) > 1 else '/tmp/gs'
dev = [[] for _ in range(4)]; lvl = [[] for _ in range(4)]; cnt = np.zeros(4); nbeats = 0
for jf in sorted(glob.glob(os.path.join(root, 'ann', '*Funk*comp.jams'))):
    J = json.load(open(jf))
    ons = []
    beats = None
    for a in J['annotations']:
        if a['namespace'] == 'note_midi':
            ons += [d['time'] for d in a['data']]
        if a['namespace'] == 'beat_position':
            beats = np.array([d['time'] for d in a['data']])
    if beats is None or len(beats) < 4: continue
    ons = np.sort(np.array(ons))
    strums = []
    for t in ons:
        if not strums or t - strums[-1] > 0.03: strums.append(t)
    x, sr = sf.read(os.path.join(root, 'mic', os.path.basename(jf).replace('.jams', '_mic.wav')), always_2d=True)
    y = x.mean(1)
    db = np.array([20 * np.log10(np.sqrt(np.mean(y[int(t * sr):int((t + 0.06) * sr)] ** 2)) + 1e-9) for t in strums])
    db -= np.median(db)
    nbeats += len(beats) - 1
    for t, d in zip(strums, db):
        i = np.searchsorted(beats, t) - 1
        if i < 0 or i >= len(beats) - 1: continue
        span = beats[i + 1] - beats[i]
        pos = (t - beats[i]) / span * 4
        k = int(round(pos)) % 4
        if round(pos) == 4: continue            # 落到下一拍的正拍,那一拍自己算
        dev[k].append((pos - round(pos)) * span / 4 * 1000); lvl[k].append(d); cnt[k] += 1
names = ['正拍', 'e', '&', 'a']
base = np.median(lvl[0])
print(f'段數 {len(glob.glob(os.path.join(root, "ann", "*Funk*comp.jams")))}、拍數 {nbeats}')
for k in range(4):
    print(f'  {names[k]:3s} 出現率 {cnt[k] / nbeats:.2f}  早晚中位 {np.median(dev[k]):+5.1f}ms(四分位 {np.percentile(dev[k], 25):+.0f}～{np.percentile(dev[k], 75):+.0f})'
          f'  力度 {np.median(lvl[k]) - base:+5.1f}dB(四分位 {np.percentile(lvl[k], 25) - base:+.1f}～{np.percentile(lvl[k], 75) - base:+.1f})')
