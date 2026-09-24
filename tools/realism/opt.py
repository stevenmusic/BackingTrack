#!/usr/bin/env python3
"""讓「像真實音樂的 %」一輪一輪往上爬(爬山法),但不准拿耳朵的盲點作弊。
  /tmp/abx/bin/python opt.py citypop [輪數]
三道護欄:
  1. 只轉有音樂意義的旋鈕(各層音量、EQ、chorus、殘響、寬度、力度範圍),全部走 FEELS[x] 的覆寫,
     範圍寫死在 SPACE 裡;不准加雜訊、不准動取樣
  2. VGGish 與 MERT 兩隻耳朵**都**要變好才收,而且要在兩組和弦進行上平均都變好
  3. 尖峰 ≤0.85(響度規則);最好的版本要送盲聽,使用者沒覺得比較好就不算數
紀錄寫在 opt/<曲風>.jsonl,最好的覆寫寫在 opt/<曲風>_best.json。"""
import sys, os, json, subprocess, copy, math, glob
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
FEEL = sys.argv[1]; ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 12
VERSION = os.environ.get('OPT_VERSION', 'bd80000')
CALIB_P = json.load(open(os.path.join(H, 'calib', 'cases0.json')))   # 只為了拿和弦進行
def auto_space(feel):
    """沒手寫範圍的曲風:從 index.html 的 FEELS[feel] 讀現值,各層音量與 mix 全部開放"""
    out = subprocess.run(['node', '-e', '''
const s=require("fs").readFileSync(process.argv[1],"utf8");const i=s.indexOf("const FEELS");let d=0,j;
for(let k=s.indexOf("{",i);k<s.length;k++){if(s[k]=="{")d++;if(s[k]=="}"){d--;if(!d){j=k;break}}}
const F=eval("("+s.slice(s.indexOf("{",i),j+1)+")");console.log(JSON.stringify(F[process.argv[2]]))''',
        os.path.join(H, '..', '..', 'index.html'), feel], capture_output=True, text=True).stdout
    f = json.loads(out); sp = []
    for k, v in (f.get('parts') or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0: sp.append((f'parts.{k}', v, v / 4, v * 2.5, 'log'))
        if isinstance(v, dict) and isinstance(v.get('lvl'), (int, float)): sp.append((f'parts.{k}.lvl', v['lvl'], v['lvl'] / 4, v['lvl'] * 2.5, 'log'))
    for k, dv in [('kickGain', 1), ('snareGain', 1), ('cymGain', 1), ('bassGain', 1)]:
        v = f.get(k, dv); sp.append((k, v, v / 2.5, v * 2, 'log'))
    sp.append(('velRange', f.get('velRange', .16), .08, .45, 'lin'))
    m = f.get('mix') or {}
    for k, dv, lo, hi, kind in [('keysLevel', 1, .5, 1.4, 'log'), ('keysAir', 0, -3, 6, 'db'), ('keysEq', 0, -8, 3, 'db'), ('keysChorus', 0, 0, .5, 'lin'),
                                ('gtrAir', 0, -3, 6, 'db'), ('gtrChorus', 0, 0, .5, 'lin'), ('drumAir', 0, -3, 6, 'db'), ('bassEq', 0, -4, 5, 'db'),
                                ('masterMid', 0, -6, 3, 'db'), ('masterAir', 0, -3, 6, 'db'), ('drumWidth', 1, .3, 1, 'lin'), ('roomLevel', 1, .1, 1.5, 'log'),
                                ('revLp', 20000, 3000, 20000, 'log')]:
        sp.append((f'mix.{k}', m.get(k, dv), lo, hi, kind))
    return sp

PROGS = {'citypop': ['Fmaj7 - E7 - Am7 - C7', 'Cmaj7 - Fmaj7 - Bm7b5 - E7 - Am7 - D7 - Dm7 - G7'],
         'kpop': ['Am7 - F - C - G', 'F - G - Em - Am']}.get(FEEL) or \
        [c['prog'] for c in json.load(open(os.path.join(H, 'calib', 'cases1.json')))['cases'] if c['feel'] == FEEL and c['style'] == 'comp' and not c.get('synth')][:2]
# (路徑, 現值, 下限, 上限, 種類) 種類 log = 乘法擾動、db = 加法擾動(單位 dB)、lin = 加法擾動
SPACE = {'citypop': [
  ('parts.glevel', .185, .06, .4, 'log'), ('parts.guitar2.lvl', .12, .03, .3, 'log'), ('parts.brass.lvl', .115, .03, .3, 'log'),
  ('parts.klevel', .032, .01, .08, 'log'), ('parts.perc.lvl', .26, .08, .5, 'log'),
  ('bassGain', 1.3, .8, 2.0, 'log'), ('kickGain', .66, .35, 1.1, 'log'), ('snareGain', .6, .3, 1.0, 'log'), ('cymGain', .28, .1, .6, 'log'),
  ('velRange', .28, .1, .45, 'lin'),
  ('mix.keysLevel', .85, .5, 1.3, 'log'), ('mix.keysAir', 2, -2, 6, 'db'), ('mix.keysEq', -3, -8, 2, 'db'), ('mix.keysChorus', .25, 0, .5, 'lin'),
  ('mix.gtrAir', 4, -2, 6, 'db'), ('mix.gtrChorus', .25, 0, .5, 'lin'), ('mix.drumAir', 4, -2, 6, 'db'), ('mix.bassEq', 2, -3, 5, 'db'),
  ('mix.masterMid', -2.5, -6, 2, 'db'), ('mix.masterAir', 2.5, -2, 6, 'db'),
  ('mix.drumWidth', .7, .3, 1.0, 'lin'), ('mix.roomLevel', .5, .1, 1.0, 'log'), ('mix.revLp', 6000, 2500, 16000, 'log')],
  # K-Pop 的 mix 本來是全透明的(0dB、20k),起點照抄現值
  'kpop': [
  ('parts.klevel', .075, .02, .15, 'log'), ('parts.klow', .145, .05, .3, 'log'), ('parts.vox.lvl', .085, .02, .2, 'log'),
  ('parts.arp.lvl', .07, .02, .15, 'log'), ('parts.perc.lvl', .12, .04, .3, 'log'),
  ('kickGain', .7, .35, 1.1, 'log'), ('snareGain', .62, .3, 1.0, 'log'), ('cymGain', .28, .1, .6, 'log'),
  ('lh', .3, .1, .6, 'log'), ('duck.bass', .22, .1, .8, 'lin'),
  ('mix.keysLevel', 1.0, .5, 1.3, 'log'), ('mix.keysAir', 0, -3, 6, 'db'), ('mix.keysEq', 0, -8, 3, 'db'), ('mix.keysChorus', 0, 0, .5, 'lin'),
  ('mix.drumAir', 0, -3, 6, 'db'), ('mix.bassEq', 0, -4, 5, 'db'),
  ('mix.masterMid', 0, -6, 3, 'db'), ('mix.masterAir', 0, -3, 6, 'db'), ('mix.revLp', 20000, 3000, 20000, 'log')]}.get(FEEL) or auto_space(FEEL)
rng = np.random.default_rng(int(os.environ.get('SEED', '1')))
TARGET = {'vggish': 89.8, 'mert': 99.6}      # MUSDB18 真實伴奏的 10% 分位 = 「標準範圍」的下緣
PLATEAU = int(os.environ.get('PLATEAU', '10'))  # 連續幾輪沒收就停,那表示旋鈕已經轉到頭

def to_ovr(vals):
    o = {}
    for (p, *_), v in zip(SPACE, vals):
        d = o; ks = p.split('.')
        for k in ks[:-1]: d = d.setdefault(k, {})
        d[ks[-1]] = round(float(v), 4)
    return o

def mutate(vals):
    v = list(vals)
    for i in rng.choice(len(SPACE), size=int(rng.integers(2, 4)), replace=False):
        _, _, lo, hi, kind = SPACE[i]
        if kind == 'log': v[i] *= math.exp(rng.normal(0, 0.35))
        elif kind == 'db': v[i] += rng.normal(0, 2.0)
        else: v[i] += rng.normal(0, (hi - lo) * 0.15)
        v[i] = min(hi, max(lo, v[i]))
    return v

# ── 耳朵(跟 ear.py 同一套特徵與權重)──
import torch, torchaudio, soundfile as sf
torch.set_num_threads(4)
sys.path.insert(0, H)
from audiobox_aesthetics.infer import AesPredictor
from vggish_np import VGGish, examples
sys.argv = ['ear', 'none']
exec(open(os.path.join(H, 'ear.py')).read().split("{'embed': cmd_embed")[0])
aes = AesPredictor(checkpoint_pth='/tmp/abx_ckpt/checkpoint.pt', precision='bf16')
vg = VGGish('/tmp/vgg/vggish.pth'); mert, mfe = load_mert()
MODELS = {f: np.load(os.path.join(H, 'calib', f'ear_model_{f}.npz')) for f in ('vggish', 'mert')}

def ears(path):
    x, sr = sf.read(path, always_2d=True, dtype='float32')
    e = vg.embed(examples(x, sr)); a = aes.forward([{'path': torch.from_numpy(x.T.copy()), 'sample_rate': sr}])[0]
    m24 = torchaudio.functional.resample(torch.from_numpy(x.mean(1)), sr, mfe.sampling_rate).numpy()
    with torch.no_grad():
        hs = mert(**mfe(m24, sampling_rate=mfe.sampling_rate, return_tensors='pt'), output_hidden_states=True).hidden_states
    mv = torch.stack([h[0].mean(0) for h in hs]).numpy()[5:10].mean(0)
    A = np.array([a['CE'], a['CU'], a['PC'], a['PQ']])
    fv = {'vggish': np.concatenate([A, e.mean(0), e.std(0)]), 'mert': np.concatenate([A, mv])}
    return {f: float(((fv[f] - M['mu']) / M['sd']) @ M['w'] + M['b']) for f, M in MODELS.items()}   # logit,越大越像真的

def evaluate(tag, cands):
    """cands: [(name, vals)] → 每個 name 的 {vggish, mert, peak}(兩組進行平均)"""
    out = f'/tmp/opt/{FEEL}/{tag}'; os.makedirs(out, exist_ok=True)
    cases = [{'version': VERSION, 'feel': FEEL, 'style': 'comp', 'prog': p, 'label': n, 'ovr': to_ovr(v)} for n, v in cands for p in PROGS]
    halves = [cases[0::2], cases[1::2]]; procs = []
    for i, hc in enumerate(halves):
        cf = f'{out}/cases{i}.json'; json.dump({'progressions': {}, 'cases': hc}, open(cf, 'w'), ensure_ascii=False)
        procs.append(subprocess.Popen(['node', os.path.join(H, 'render.mjs'), cf], env={**os.environ, 'REALISM_OUT': out},
                                      stdout=open(f'{out}/r{i}.log', 'w'), stderr=subprocess.STDOUT))
    for p in procs: p.wait()
    rows = [json.loads(l) for l in open(f'{out}/clips.jsonl')] if os.path.exists(f'{out}/clips.jsonl') else []
    res = {}
    for r in rows:
        s = ears(f"{out}/clips/{r['id']}.wav")
        d = res.setdefault(r['label'], {'vggish': [], 'mert': [], 'peak': []})
        d['vggish'].append(s['vggish']); d['mert'].append(s['mert']); d['peak'].append(r['features']['peak'])
    return {n: {k: (max(v) if k == 'peak' else float(np.mean(v))) for k, v in d.items()} | {'n': len(d['peak'])} for n, d in res.items()}

pct = lambda z: 100 / (1 + math.exp(-z))
log = open(os.path.join(H, 'opt', f'{FEEL}.jsonl'), 'a')
best = [s[1] for s in SPACE]
bp = os.path.join(H, 'opt', f'{FEEL}_best.json')
if os.path.exists(bp): best = json.load(open(bp))['vals']
cur = evaluate(f'base{len(glob.glob(f"/tmp/opt/{FEEL}/base*"))}', [('base', best)])['base']
print(f"起點 VGGish {pct(cur['vggish']):.1f}%  MERT {pct(cur['mert']):.1f}%  peak {cur['peak']:.3f}", flush=True)
log.write(json.dumps({'round': 0, 'accepted': True, 'score': cur, 'ovr': to_ovr(best)}, ensure_ascii=False) + '\n'); log.flush()
miss = 0
start = 1 + max([json.loads(l)['round'] for l in open(os.path.join(H, 'opt', f'{FEEL}.jsonl'))] or [0])
for r in range(start, start + ROUNDS):
    if pct(cur['vggish']) >= TARGET['vggish'] and pct(cur['mert']) >= TARGET['mert']:
        print('兩隻耳朵都進了標準範圍,停'); break
    if miss >= PLATEAU:
        print(f'連續 {PLATEAU} 輪沒進步,旋鈕轉到頭了,停'); break
    cands = [(f'm{k}', mutate(best)) for k in range(4)]
    res = evaluate(f'r{r:02d}', cands)
    ok = [(n, v, res[n]) for n, v in cands if n in res and res[n]['n'] == len(PROGS) and res[n]['peak'] <= 0.85
          and res[n]['vggish'] > cur['vggish'] and res[n]['mert'] > cur['mert']]
    ok.sort(key=lambda t: -(t[2]['vggish'] + t[2]['mert']))
    for n, v in cands:
        s = res.get(n)
        log.write(json.dumps({'round': r, 'cand': n, 'accepted': bool(ok and ok[0][0] == n), 'score': s, 'ovr': to_ovr(v)}, ensure_ascii=False) + '\n')
    log.flush()
    miss = 0 if ok else miss + 1
    if ok:
        best, cur = ok[0][1], ok[0][2]
        json.dump({'vals': best, 'ovr': to_ovr(best), 'score': cur}, open(bp, 'w'), ensure_ascii=False, indent=1)
    print(f"第 {r} 輪 {'收' if ok else '不收'}  VGGish {pct(cur['vggish']):.1f}%  MERT {pct(cur['mert']):.1f}%  peak {cur['peak']:.3f}", flush=True)
