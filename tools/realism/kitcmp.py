#!/usr/bin/env python3
"""挑鼓組:同一個 City Pop 鼓型(102 BPM、大鼓一與「二的後半」與三、小鼓二四、hi-hat 八分帶強弱),
用每一組候選的大鼓/小鼓/hi-hat 近麥取樣離線排出來,再跟三首參考曲分出來的鼓軌比 MERT 相似度。
  /tmp/abx/bin/python kitcmp.py kits.json
kits.json: {名字: {"kick": [檔案...], "snare": [...], "hat": [...]}}(每一件給幾個 round robin 輪流用)"""
import sys, os, json, glob, numpy as np, soundfile as sf
from scipy.signal import resample_poly
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
SR = 44100
def load(p):
    x, sr = sf.read(p, always_2d=True, dtype='float32')
    x = x.mean(1)
    if sr != SR: x = resample_poly(x, SR, sr).astype(np.float32)
    return x / (np.abs(x).max() + 1e-9)
def render(kit, bpm=102, bars=8, seed=0):
    rng = np.random.default_rng(seed); spb = 60 / bpm; n = int(bars * 4 * spb * SR) + SR
    out = np.zeros(n, np.float32)
    S = {k: [load(p) for p in v] for k, v in kit.items()}
    lv = {'kick': 0.9, 'snare': 0.8, 'hat': 0.28}
    cnt = {k: 0 for k in S}
    def hit(k, t, g):
        s = S[k][cnt[k] % len(S[k])]; cnt[k] += 1
        i = max(0, int(t * SR)); m = min(len(s), n - i); out[i:i + m] += s[:m] * g * lv[k]
    for b in range(bars):
        t0 = b * 4 * spb
        for beat8 in range(8):                       # hi-hat 八分,正拍重、反拍輕
            hit('hat', t0 + beat8 * spb / 2 + rng.normal(0, 0.003), 1.0 if beat8 % 2 == 0 else 0.62)
        for q in (0, 1.5, 2.0) if b % 2 == 0 else (0, 2.0, 2.75):
            hit('kick', t0 + q * spb + rng.normal(0, 0.002), 1.0)
        for q in (1, 3):
            hit('snare', t0 + q * spb + 0.003 + rng.normal(0, 0.002), 1.0)
    return out / (np.abs(out).max() + 1e-9) * 0.8
if __name__ == '__main__':
    import torch, torchaudio
    sys.argv, kitsfile = ['x', 'none'], sys.argv[1]
    exec(open(os.path.join(H, 'ear.py')).read().split("{'embed': cmd_embed")[0])
    torch.set_num_threads(4); mert, mfe = load_mert()
    def emb(x, sr):
        m = torchaudio.functional.resample(torch.from_numpy(x.astype(np.float32)), sr, mfe.sampling_rate).numpy()
        with torch.no_grad():
            hs = mert(**mfe(m, sampling_rate=mfe.sampling_rate, return_tensors='pt'), output_hidden_states=True).hidden_states
        v = torch.stack([h[0].mean(0) for h in hs]).numpy()[5:10].mean(0); return v / np.linalg.norm(v)
    refs = []
    for f in sorted(glob.glob('/tmp/refcp/sep/htdemucs/*/drums.wav')):
        x, sr = sf.read(f, always_2d=True, dtype='float32'); x = x.mean(1)
        for t in range(10, int(len(x) / sr) - 10, 10):
            seg = x[t * sr:(t + 10) * sr]
            if np.sqrt((seg ** 2).mean()) > 1e-3: refs.append(emb(seg, sr))
    R = np.array(refs)
    kits = json.load(open(kitsfile)); res = {}
    for name, kit in kits.items():
        y = render(kit); vs = [emb(y[i * SR:(i + 10) * SR], SR) for i in range(0, int(len(y) / SR) - 10, 5)]
        res[name] = round(float(np.mean([(R @ v).max() for v in vs])), 4)
        sf.write(f'/tmp/kits/render_{name}.wav', y, SR)
        print(name, res[name], flush=True)
    json.dump(res, open(os.path.join(H, 'db', 'kitcmp.json'), 'w'), ensure_ascii=False, indent=1)
