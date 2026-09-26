#!/usr/bin/env python3
"""現成的「耳朵」:LAION-CLAP 音樂模型(laion/larger_clap_music)的嵌入 + Fréchet Audio Distance。
Gui et al., "Adapting Frechet Audio Distance for Generative Music Evaluation", ICASSP 2024(微軟 fadtk):
音樂上 CLAP 系列嵌入的 FAD 跟人的評分相關最好。距離越小 = 越像參考那一群。

**公平**:真歌有人聲、我們沒有 → 真歌一律用 demucs 拆掉人聲的伴奏(drums + bass + guitar + piano + other 相加)。
**先驗證尺**(CLAUDE.md:量尺要先證明是對的):
  - 真歌分兩半,一半當參考,另一半要最近
  - 我們的別的曲風(Swing / K-Pop / Bossa)要最遠
兩個都成立才拿來判斷 City Pop。

  HF_HOME=/tmp/hf /tmp/abx/bin/python clapfad.py embed <名字> <wav 或分軌資料夾 glob>   → /tmp/clap/<名字>.npy(每 10 秒一個嵌入)
  HF_HOME=/tmp/hf /tmp/abx/bin/python clapfad.py report                               → 驗證 + 各組到真歌的距離(bootstrap)
  CLIPS_JSONL=/tmp/abl/clips.jsonl /tmp/abx/bin/python clapfad.py ablation            → 逐層拿掉 / 加上(先 embed abl_<label> 到 /tmp/clap)
"""
import sys, os, glob
import numpy as np, soundfile as sf, librosa
from scipy import linalg

OUT = '/tmp/clap'
SR = 48000
WIN = 10


def audio_of(path):
    if os.path.isdir(path):   # demucs 分軌資料夾 → 去人聲伴奏
        xs = [sf.read(os.path.join(path, s + '.wav'), always_2d=True, dtype='float32') for s in ('drums', 'bass', 'guitar', 'piano', 'other')]
        sr = xs[0][1]; y = sum(x for x, _ in xs).mean(1)
    else:
        x, sr = sf.read(path, always_2d=True, dtype='float32'); y = x.mean(1)
    y = librosa.resample(y, orig_sr=sr, target_sr=SR)
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-9) * 0.1          # 響度對齊,只比內容不比大小聲


def embed(name, pattern):
    import torch
    from transformers import ClapModel, ClapProcessor
    m = ClapModel.from_pretrained('laion/larger_clap_music').eval(); p = ClapProcessor.from_pretrained('laion/larger_clap_music')
    embs, owner = [], []
    for i, f in enumerate(sorted(glob.glob(pattern))):
        y = audio_of(f.rstrip('/'))
        wins = [y[s:s + SR * WIN] for s in range(0, len(y) - SR * WIN + 1, SR * WIN)][:30]   # 一首最多 30 窗(合集那種長檔不讓它獨大)
        if not wins: continue
        with torch.no_grad():
            e = m.get_audio_features(**p(audios=wins, sampling_rate=SR, return_tensors='pt')).numpy()
        embs.append(e); owner += [i] * len(e)
        print(name, os.path.basename(f.rstrip('/')), len(wins), flush=True)
    os.makedirs(OUT, exist_ok=True)
    np.save(f'{OUT}/{name}.npy', np.concatenate(embs)); np.save(f'{OUT}/{name}_owner.npy', np.array(owner))


def fad(a, b):
    mu1, mu2 = a.mean(0), b.mean(0)
    s1, s2 = np.cov(a, rowvar=False), np.cov(b, rowvar=False)
    cs, _ = linalg.sqrtm(s1 @ s2, disp=False)
    return float(np.sum((mu1 - mu2) ** 2) + np.trace(s1 + s2 - 2 * cs.real))


def load(name):
    return np.load(f'{OUT}/{name}.npy'), np.load(f'{OUT}/{name}_owner.npy')


def by_song(e, o, keep):
    return np.concatenate([e[o == k] for k in keep])


def report():
    rng = np.random.default_rng(0)
    real, ro = load('real')
    songs = np.unique(ro)
    groups = [n[:-4] for n in sorted(os.listdir(OUT)) if n.endswith('.npy') and not n.endswith('_owner.npy') and n != 'real.npy']
    print('每一組都跟「真歌一半」比,換 20 種切法取中位 [5%, 95%];真歌自己的另一半是基準(越接近它越好)')
    res = {}
    for g in ['真歌另一半'] + groups:
        vals, coss = [], []
        for _ in range(20):
            half = rng.permutation(songs); A, B = half[:len(half) // 2], half[len(half) // 2:]
            ref = by_song(real, ro, A)
            if g == '真歌另一半': x = by_song(real, ro, B)
            else:
                e, o = load(g); x = e
            vals.append(fad(ref, x))
            # 第二個指標(不怕樣本少):每一窗跟「參考那一半」平均嵌入的 cos 相似度
            c = ref.mean(0); c /= np.linalg.norm(c)
            coss.append((x / np.linalg.norm(x, axis=1, keepdims=True)) @ c)
        res[g] = vals
        cs = np.concatenate(coss)
        print(f'  {g:14s} FAD {np.median(vals):7.3f} [{np.percentile(vals, 5):.3f}, {np.percentile(vals, 95):.3f}]  '
              f'相似度 {cs.mean():.3f} [{np.percentile(cs, 10):.3f}, {np.percentile(cs, 90):.3f}]  窗數 {len(x)}')


def ablation(clips_jsonl=os.environ.get('CLIPS_JSONL', '/tmp/abl/clips.jsonl')):
    """每個 abl_* 版本跟**全部**真歌比 FAD;對**我們的片段**重抽 300 次給 95% 區間,並列出跟 abl_base 的配對差。
    **配對**:embed 的 owner 是「排序後的檔名(片段 id)」的位置,id 是雜湊,各版本排序不同——
    所以先用 clips.jsonl 把 owner 換成 (疏密, 進行),每一次重抽的是同一組 (疏密, 進行),各版本各自對到自己的片段。
    檔案要照 /tmp/abl/by/<label>/<id>.wav 放(render 的 label 就是 abl_*)"""
    import json
    real, _ = load('real')
    rng = np.random.default_rng(0)
    rows = [json.loads(l) for l in open(clips_jsonl)]
    names = sorted(n[:-4] for n in os.listdir(OUT) if n.startswith('abl_') and n.endswith('.npy') and not n.endswith('_owner.npy'))
    data = {}
    for n in names:
        e, o = load(n)
        ids = sorted(r['id'] for r in rows if r['label'] == n)
        key = {i: (r['style'], r['prog']) for i, cid in enumerate(ids) for r in rows if r['id'] == cid}
        data[n] = (e, [key[k] for k in o])
    keys = sorted(set(data['abl_base'][1]))
    for n in names:
        assert sorted(set(data[n][1])) == keys, f'{n} 的片段跟 abl_base 對不上'
    draws = [[keys[k] for k in rng.integers(0, len(keys), len(keys))] for _ in range(300)]
    def f(n, pick):
        e, o = data[n]; return fad(real, np.concatenate([e[[x == k for x in o]] for k in pick]))
    base = np.array([f('abl_base', d) for d in draws])
    print(f'全部真歌當參考;片段數 {len(keys)}(疏密 × 進行),重抽 300 次,每次各版本抽同一組')
    for n in names:
        v = np.array([f(n, d) for d in draws]); dv = v - base
        print(f'  {n:16s} FAD {f(n, keys):.4f} [{np.percentile(v, 2.5):.4f}, {np.percentile(v, 97.5):.4f}]  '
              f'跟原版差 {np.mean(dv):+.4f} [{np.percentile(dv, 2.5):+.4f}, {np.percentile(dv, 97.5):+.4f}]')


{'embed': lambda: embed(sys.argv[2], sys.argv[3]), 'report': report, 'ablation': ablation}[sys.argv[1]]()
