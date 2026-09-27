#!/usr/bin/env python3
"""貝斯(或任一 bus)單獨錄之後的起音數與安靜比例:用來抓「有音被吃掉」(第十一輪:貝斯單音吃掉幽靈音後面那顆與過門最後一顆)。
起音 = librosa.onset.onset_detect(22050Hz);安靜比例 = RMS 格子 < 最大值 3% 的比例。
  REALISM_PROBE=tools/realism/probe_solo.js REALISM_SOLO=bassBus REALISM_SECS=24 REALISM_OUT=/tmp/bm \\
    node tools/realism/render.mjs tools/realism/cases_mono.json
  /tmp/abx/bin/python tools/realism/onsets.py /tmp/bm
"""
import sys, os, json
import numpy as np, soundfile as sf, librosa

root = sys.argv[1]
seen = {}
for l in open(os.path.join(root, 'clips.jsonl')):
    r = json.loads(l); seen[r['id']] = r
for r in sorted(seen.values(), key=lambda r: r['label'] or ''):
    x, sr = sf.read(os.path.join(root, 'clips', r['id'] + '.wav'), always_2d=True)
    y = librosa.resample(x.mean(1), orig_sr=sr, target_sr=22050)
    on = librosa.onset.onset_detect(y=y, sr=22050, units='time')
    rms = librosa.feature.rms(y=y)[0]
    print(f"{r['label']:12s} {r['version']:8s} 起音 {len(on):4d}  安靜比例 {(rms < rms.max() * 0.03).mean():.2f}  RMS {r['features']['rms']}")
