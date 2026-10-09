"""Meta Audiobox Aesthetics(Tjandra et al. 2025,用人工評分訓練的音訊美學預測器)替每個檔打四個分數:
CE 好不好聽、CU 實用度、PC 製作複雜度、PQ 製作品質(1–10)。只當旁證:CLAUDE.md 規定量尺只擋壞掉的東西。
用法(要另外的 venv:torch + audiobox_aesthetics):/tmp/abxenv/bin/python tools/mix/aes_score.py <資料夾> [...]
"""
import sys, glob, os, json
import numpy as np, soundfile as sf, torch
from audiobox_aesthetics.infer import initialize_predictor

pred = initialize_predictor()
for d in sys.argv[1:]:
    for f in sorted(glob.glob(os.path.join(d, "*__auto_16.wav"))):
        x, sr = sf.read(f, always_2d=True)
        x = x.T.astype(np.float32)
        # 對齊響度不影響分數太多,但兩邊同樣處理:峰值正規化到 0.9
        x *= 0.9 / max(1e-9, np.abs(x).max())
        r = pred.forward([{"path": torch.from_numpy(x), "sample_rate": sr}])[0]
        print(json.dumps({"dir": d, "style": os.path.basename(f).split("__")[0], **{k: round(v, 2) for k, v in r.items()}}, ensure_ascii=False))
