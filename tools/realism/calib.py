#!/usr/bin/env python3
"""耳朵校準:用「答案已知」的題目檢查打分工具可不可信。
  /tmp/abx/bin/python calib.py degrade   # 每段原始錄音做 8 種已知的破壞(calib/clips/<id>__<種類>.wav)
  /tmp/abx/bin/python calib.py score     # Audiobox 四軸 + VGGish,寫 calib/scores.jsonl
  /tmp/abx/bin/python calib.py report    # 已知答案的題目答對幾成,寫 calib/report.json

已知答案(不需要人評):
  A. 原樣 > 被破壞的同一段(悶掉、削波、雜訊、位元壓縮、電話音、低音被切掉、被殘響淹掉、走音晃動)
  B. 真取樣 > 同一段換成合成備援(render.mjs 的 synth case)
  C. 真唱片(Plastic Love 的 10 秒窗)> 我們的 City Pop
通過只代表「這把尺抓得到明顯的壞」,不代表它跟你的喜好一致——那要看盲聽分數。"""
import sys, os, json, glob
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
H = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(H, 'calib'); CL = os.path.join(C, 'clips')
REF = os.environ.get('REF_MP3', '/tmp/claude-0/-home-user/89adda12-dafd-58db-b902-b08a616a26cf/scratchpad/ref.mp3')
def jl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []

def seed(s): return np.random.default_rng(abs(hash(s)) % (2**32))
DEG = {
  'lp':    lambda x, sr, r: sosfilt(butter(4, 2500, 'low', fs=sr, output='sos'), x, axis=0),
  'clip':  lambda x, sr, r: np.clip(x * 4, -0.5, 0.5) * 1.6,
  'noise': lambda x, sr, r: x + r.standard_normal(x.shape) * np.sqrt((x ** 2).mean()) * 0.18,
  'crush': lambda x, sr, r: np.repeat((np.round(x[::6] * 24) / 24), 6, axis=0)[:len(x)],
  'tel':   lambda x, sr, r: sosfilt(butter(4, [400, 3000], 'band', fs=sr, output='sos'), x, axis=0) * 2,
  'hp':    lambda x, sr, r: sosfilt(butter(4, 350, 'high', fs=sr, output='sos'), x, axis=0),
  'wash':  None,
  'wow':   None,
}
def wow(x, sr):
    t = np.arange(len(x)) / sr
    dev = 0.0035 * np.sin(2 * np.pi * 0.9 * t) + 0.0015 * np.sin(2 * np.pi * 5.3 * t)   # 走音晃動 ±40 音分左右
    pos = np.clip(np.cumsum(1 + dev) - 1, 0, len(x) - 1)
    return np.stack([np.interp(pos, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1)

def wash(x, sr, r):
    n = int(sr * 3.0); t = np.arange(n) / sr
    ir = r.standard_normal((n, 2)) * np.exp(-t / 0.9)[:, None]; ir /= np.sqrt((ir ** 2).sum(0))
    from scipy.signal import fftconvolve
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(x.shape[1])], 1)
    return 0.25 * x + wet * np.sqrt((x ** 2).mean() / max(1e-12, (wet ** 2).mean()))   # 被殘響淹掉

def cmd_degrade():
    rows = [r for r in jl(os.path.join(C, 'clips.jsonl')) if '__' not in r['id']]
    n = 0
    for r in rows:
        src = os.path.join(CL, r['id'] + '.wav')
        if not os.path.exists(src) or r.get('synth'): continue
        x, sr = sf.read(src, always_2d=True)
        for k, f in DEG.items():
            out = os.path.join(CL, f"{r['id']}__{k}.wav")
            if os.path.exists(out): continue
            y = wow(x, sr) if k == 'wow' else wash(x, sr, seed(r['id'] + k)) if k == 'wash' else f(x, sr, seed(r['id'] + k))
            y = y / max(1e-9, np.abs(y).max()) * min(0.95, np.abs(x).max())   # 響度拉回原本的尖峰,不讓「比較小聲」變成線索
            sf.write(out, y.astype(np.float32), sr, subtype='PCM_16'); n += 1
    # 盲聽題庫那 29 段也一起打分(它們有你的分數,可以順便對人評)
    for f in glob.glob(os.path.join(H, 'clips', '*.wav')):
        out = os.path.join(CL, 'blind__' + os.path.basename(f))
        if not os.path.exists(out): os.symlink(f, out); n += 1
    d, sr = sf.read(REF, always_2d=True)
    for s in range(0, int(len(d) / sr) - 10, 10):
        out = os.path.join(CL, f'ref__{s:03d}.wav')
        if not os.path.exists(out): sf.write(out, d[s * sr:(s + 10) * sr].astype(np.float32), sr, subtype='PCM_16'); n += 1
    print('寫了', n, '段')

def cmd_score():
    import torch, torchaudio
    sys.path.insert(0, H)
    from audiobox_aesthetics.infer import AesPredictor
    from vggish_np import VGGish, examples
    import realism
    p = AesPredictor(checkpoint_pth='/tmp/abx_ckpt/checkpoint.pt', precision='bf16')
    R = realism.refs(); real = np.concatenate([r['emb'] for r in R])
    rn = real / np.linalg.norm(real, axis=1, keepdims=True)
    # 判別器只用盲聽題庫的片段訓練(不碰校準集),免得它背答案
    train = [e for e in (realism.clip_emb(c) for c in realism.jl(os.path.join(H, 'db', 'clips.jsonl'))) if e is not None]
    clf = realism.logreg(np.concatenate([real] + train), np.r_[np.ones(len(real)), np.zeros(sum(len(t) for t in train))])
    vm = realism.model()
    path = os.path.join(C, 'scores.jsonl'); done = {r['id']: r for r in jl(path)}
    fo = open(path, 'a')
    for f in sorted(glob.glob(os.path.join(CL, '*.wav'))):
        cid = os.path.basename(f)[:-4]
        if cid in done: continue
        wav, sr = torchaudio.load(f)
        a = p.forward([{'path': wav, 'sample_rate': sr}])[0]
        x, sr2 = sf.read(f, always_2d=True); e = vm.embed(examples(x, sr2))
        en = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
        r = {'id': cid, **{k: round(v, 3) for k, v in a.items()},
             'pReal': round(float(clf(e).mean()), 4), 'near': round(float(1 - (en @ rn.T).max(1).mean()), 4)}
        fo.write(json.dumps(r) + '\n'); fo.flush(); print(r, flush=True)

METRICS = [('CE', 1), ('CU', 1), ('PC', 1), ('PQ', 1), ('pReal', 1), ('near', -1)]
def cmd_report():
    S = {r['id']: r for r in jl(os.path.join(C, 'scores.jsonl'))}
    base = {r['id']: r for r in jl(os.path.join(C, 'clips.jsonl'))}
    tests = {}
    def add(name, good, bad):
        if good in S and bad in S: tests.setdefault(name, []).append((good, bad))
    for i, r in base.items():
        if r.get('synth'): continue
        for k in DEG: add('A 原樣>' + k, i, f'{i}__{k}')
        for j, q in base.items():
            if q.get('synth') and q['feel'] == r['feel'] and q['prog'] == r['prog'] and r['style'] == 'comp': add('B 真取樣>合成', i, j)
    refs = [k for k in S if k.startswith('ref__')]
    for i, r in base.items():
        if r['feel'] == 'citypop' and not r.get('synth'):
            for k in refs: add('C 唱片>City Pop', k, i)
    out = {}
    for name, pairs in sorted(tests.items()):
        out[name] = {'n': len(pairs)}
        for m, sgn in METRICS:
            acc = np.mean([(S[g][m] - S[b][m]) * sgn > 0 for g, b in pairs])
            out[name][m] = round(float(acc), 3)
    allA = [p for k, v in tests.items() if k.startswith('A') for p in v]
    out['A 全部'] = {'n': len(allA), **{m: round(float(np.mean([(S[g][m] - S[b][m]) * s > 0 for g, b in allA])), 3) for m, s in METRICS}}
    # D. 跟你的盲聽分數像不像(spearman,同一段多筆分數取平均)
    hum = {}
    for r in jl(os.path.join(H, 'db', 'ratings.jsonl')): hum.setdefault('blind__' + r['clip'], []).append(r['score'])
    ks = [k for k in hum if k in S]
    if len(ks) >= 5:
        rk = lambda a: np.argsort(np.argsort(a)).astype(float)
        y = rk(np.array([np.mean(hum[k]) for k in ks]))
        out['D 對人評 spearman'] = {'n': len(ks), **{m: round(float(np.corrcoef(rk(np.array([S[k][m] * s for k in ks])), y)[0, 1]), 3) for m, s in METRICS}}
    json.dump(out, open(os.path.join(C, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print(f"{'題型':18}{'n':>5}" + ''.join(f'{m:>8}' for m, _ in METRICS))
    for k, v in out.items(): print(f"{k:18}{v['n']:>5}" + ''.join(f"{v[m]:>8.2f}" for m, _ in METRICS))
    print('總題數', len(S))

{'degrade': cmd_degrade, 'score': cmd_score, 'report': cmd_report}[sys.argv[1]]()
