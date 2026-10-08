"""母帶響度:量全混音的 BS.1770 整合響度與 true peak(4 倍超取樣),算出各曲風的 master.gainDb 寫進 styles.json。
用法:python3 tools/mix/solve_loudness.py <WAV 資料夾> [--write]   (檔名 <style>__auto_16.wav)
目標:−14 LUFS(串流平台的標準響度),true peak ≤ −1 dBTP(限幅器負責)
"""
import sys, os, re, json, glob
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import load, lufs

TARGET = -14.0
def true_peak(x):
    up = signal.resample_poly(x, 4, 1, axis=-1)
    return 20 * np.log10(np.abs(up).max() + 1e-12)

D = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
P = os.path.join(ROOT, "styles", "styles.json")
txt = open(P).read(); data = json.loads(txt)
cur = {s["id"]: s.get("master", {}).get("gainDb", 0) for s in data["styles"]}
new = {}
for f in sorted(glob.glob(os.path.join(D, "*__auto_16.wav"))):
    style = os.path.basename(f).split("__")[0]
    x, sr = load(f)
    L, tp = lufs(x, sr), true_peak(x)
    new[style] = round(cur.get(style, 0) + TARGET - L, 1)
    print(f"{style:16s} {L:6.1f} LUFS  true peak {tp:+5.1f} dBTP  → gainDb {new[style]:+.1f}")
if "--write" in sys.argv:
    for style, g in new.items():
        i = txt.index(f'\n      "id": "{style}"'); j = txt.find('\n      "id": "', i + 1); j = j if j > 0 else len(txt)
        block = txt[i:j]
        if '"master":' in block:
            block = re.sub(r'"master": \{[^}]*\}', f'"master": {{ "gainDb": {g} }}', block, count=1)
        else:
            k = block.index("\n", 1)
            block = block[:k] + f'\n      "master": {{ "gainDb": {g} }},' + block[k:]
        txt = txt[:i] + block + txt[j:]
    json.loads(txt); open(P, "w").write(txt); print("寫入", P)
