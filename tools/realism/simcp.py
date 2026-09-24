#!/usr/bin/env python3
"""跟真實 City Pop 的相似度(只比伴奏:鼓+貝斯+其他,人聲拿掉,所以旋律不算)。
尺:100% = 一首真的 City Pop 跟另外兩首有多像;0% = 全部合成(一個取樣都沒有)的版本。
嵌入用 MERT(音樂的自監督模型),每 10 秒一段,相似度 = 每一段跟參考曲裡最像那一段的餘弦相似度。
分軌一律過同一個 Demucs,兩邊的分軌誤差才一樣。"""
import sys, os, glob, json, numpy as np, soundfile as sf, torch, torchaudio
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
sys.argv = ['x', 'none']; exec(open(os.path.join(H, 'ear.py')).read().split("{'embed': cmd_embed")[0])
torch.set_num_threads(4)
mert, mfe = load_mert()
STEMS = {'伴奏': ('drums', 'bass', 'other'), '鼓': ('drums',), '貝斯': ('bass',), '其他樂器': ('other',)}
def emb(x, sr):
    m = torchaudio.functional.resample(torch.from_numpy(x.mean(1).astype(np.float32)), sr, mfe.sampling_rate).numpy()
    with torch.no_grad():
        hs = mert(**mfe(m, sampling_rate=mfe.sampling_rate, return_tensors='pt'), output_hidden_states=True).hidden_states
    v = torch.stack([h[0].mean(0) for h in hs]).numpy()[5:10].mean(0); return v / np.linalg.norm(v)
def windows(folder, stems, start=10, step=10):
    xs = [sf.read(os.path.join(folder, s + '.wav'), always_2d=True, dtype='float32') for s in stems]
    sr = xs[0][1]; x = sum(a for a, _ in xs)
    out = []
    for t in range(start, int(len(x) / sr) - 10 + 1, step):
        seg = x[t * sr:(t + 10) * sr]
        if np.sqrt((seg ** 2).mean()) > 1e-3: out.append(emb(seg, sr))
    return out
GROUPS = {
  'ref': sorted(glob.glob('/tmp/refcp/sep/htdemucs/*')),
  'before': sorted(glob.glob('/tmp/ours/sep/htdemucs/ours_*')),
  'after': sorted(glob.glob('/tmp/ours3/sep/htdemucs/n3_*')),
  'synth': sorted(glob.glob('/tmp/synthcp/sep/htdemucs/syn_*')),
  'A': sorted(glob.glob('/tmp/ours4/sep/htdemucs/n4_*')),   # 方案 A:鼓改乾之後
}
res = {}
for name, stems in STEMS.items():
    E = {g: {os.path.basename(f): windows(f, stems, start=0 if g == 'synth' else 10) for f in fs} for g, fs in GROUPS.items()}
    refs = E['ref']
    def sim_to_refs(vs, exclude=None):
        pool = np.array([v for k, l in refs.items() if k != exclude for v in l])
        return float(np.mean([(pool @ v).max() for v in vs]))
    ref_self = np.mean([sim_to_refs(v, exclude=k) for k, v in refs.items()])     # 真歌 vs 另外兩首
    s = {g: np.mean([sim_to_refs(v) for v in E[g].values()]) for g in ('before', 'after', 'A', 'synth')}
    pct = lambda x: round(100 * (x - s['synth']) / (ref_self - s['synth']), 1)
    res[name] = {'真歌之間': round(float(ref_self), 4), **{g: round(float(v), 4) for g, v in s.items()},
                 '改之前%': pct(s['before']), '改之後%': pct(s['after']), '方案A%': pct(s['A'])}
    print(name, res[name], flush=True)
json.dump(res, open(os.path.join(H, 'db', 'simcp.json'), 'w'), ensure_ascii=False, indent=1)
