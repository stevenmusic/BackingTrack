"""伴奏真實度評測(eval)。
  python realism.py ref add <音檔> --name "Plastic Love" --genre citypop [--start 20 --end 40] [--vocal]
  python realism.py score          # 每個片段:跟真實錄音的距離、判別器覺得它是真錄音的機率、各組 FAD
  python realism.py analyze        # 跟 db/ratings.jsonl(你的盲聽分數)對照,寫 KNOWLEDGE.md

嵌入模型是 VGGish(vggish_np.py,權重見那個檔案的說明)。真實歌曲**只存嵌入不存音檔**
(db/refs/*.npy),版權音檔不要進 repo。"""
import sys, os, json, glob, argparse, re, math
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'db')
sys.path.insert(0, HERE)
from vggish_np import VGGish, examples
WEIGHTS = os.environ.get('VGGISH', '/tmp/vgg/vggish.pth')
_model = None
def model():
    global _model
    if _model is None: _model = VGGish(WEIGHTS)
    return _model

def embed_file(path, start=None, end=None):
    x, sr = sf.read(path, always_2d=True)
    if start is not None: x = x[int(start * sr):int(end * sr) if end else None]
    return model().embed(examples(x, sr))

def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []

def refs():
    rows = jl(os.path.join(DB, 'refs.jsonl'))
    for r in rows: r['emb'] = np.load(os.path.join(DB, 'refs', r['slug'] + '.npy'))
    return rows

def clip_emb(c):
    p = os.path.join(DB, 'emb', c['id'] + '.npy')
    if not os.path.exists(p):
        wav = os.path.join(HERE, 'clips', c['id'] + '.wav')
        if not os.path.exists(wav): return None
        os.makedirs(os.path.dirname(p), exist_ok=True); np.save(p, embed_file(wav))
    return np.load(p)

def fad(a, b):
    """Fréchet Audio Distance:兩組嵌入各自當高斯,算兩個分佈的距離。越小越像"""
    from scipy.linalg import sqrtm
    m1, m2 = a.mean(0), b.mean(0)
    s1, s2 = np.cov(a, rowvar=False), np.cov(b, rowvar=False)
    cs = sqrtm(s1 @ s2)
    if np.iscomplexobj(cs): cs = cs.real
    return float(((m1 - m2) ** 2).sum() + np.trace(s1 + s2 - 2 * cs))

def logreg(X, y, l2=1.0, it=600, lr=0.1):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd; w = np.zeros(Z.shape[1]); b = 0.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = p - y
        w -= lr * (Z.T @ g / len(y) + l2 * w / len(y)); b -= lr * g.mean()
    return lambda Q: 1 / (1 + np.exp(-(((Q - mu) / sd) @ w + b)))

def cmd_ref_add(a):
    slug = re.sub(r'[^a-z0-9]+', '-', a.name.lower()).strip('-')
    e = embed_file(a.file, a.start, a.end)
    os.makedirs(os.path.join(DB, 'refs'), exist_ok=True)
    np.save(os.path.join(DB, 'refs', slug + '.npy'), e)
    rows = [r for r in jl(os.path.join(DB, 'refs.jsonl')) if r['slug'] != slug]
    rows.append({'slug': slug, 'name': a.name, 'genre': a.genre, 'start': a.start, 'end': a.end,
                 'vocal': a.vocal, 'frames': len(e)})
    with open(os.path.join(DB, 'refs.jsonl'), 'w') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('ref', slug, len(e), 'frames')

def cmd_score(a):
    R = refs()
    if not R: sys.exit('沒有參考曲:先跑 ref add')
    clips = [c for c in jl(os.path.join(DB, 'clips.jsonl'))]
    seen = {}; 
    for c in clips: seen[c['id']] = c          # 同一個 id 錄過兩次取最後一次
    clips = [c for c in seen.values() if clip_emb(c) is not None]
    E = {c['id']: clip_emb(c) for c in clips}
    real = np.concatenate([r['emb'] for r in R])
    gen_all = np.concatenate(list(E.values()))
    # 判別器:真錄音 vs 我們的片段。每一個片段都是「留它在外面」訓練,再問它像不像真的
    out = []
    for c in clips:
        others = np.concatenate([E[k] for k in E if k != c['id']]) if len(E) > 1 else np.zeros((0, 128))
        X = np.concatenate([real, others]); y = np.r_[np.ones(len(real)), np.zeros(len(others))]
        clf = logreg(X, y)
        g = [r for r in R if r['genre'] == c['feel']] or R
        gref = np.concatenate([r['emb'] for r in g])
        cn = gref / (np.linalg.norm(gref, axis=1, keepdims=True) + 1e-9)
        ce = E[c['id']] / (np.linalg.norm(E[c['id']], axis=1, keepdims=True) + 1e-9)
        near = 1 - (ce @ cn.T).max(axis=1)                 # 每一秒離最像的那一秒真錄音多遠
        out.append({'id': c['id'], 'commit': c['commit'], 'feel': c['feel'], 'style': c['style'],
                    'pReal': round(float(clf(E[c['id']]).mean()), 3),
                    'nearDist': round(float(near.mean()), 4),
                    'refSet': [r['slug'] for r in g]})
    # 自我檢查:把真錄音自己切一半當「片段」,判別器應該給高分——給不出來就代表這把尺不能用
    half = len(real) // 2
    chk = logreg(np.concatenate([real[:half], gen_all]), np.r_[np.ones(half), np.zeros(len(gen_all))])(real[half:]).mean()
    # 每一組(版本 × 曲風)的 FAD
    groups = {}
    for c in clips: groups.setdefault((c['commit'], c['feel']), []).append(E[c['id']])
    fads = {f'{k[0]}:{k[1]}': round(fad(np.concatenate(v), real), 2) for k, v in groups.items()}
    with open(os.path.join(DB, 'scores.jsonl'), 'w') as f:
        for r in out: f.write(json.dumps(r) + '\n')
    json.dump({'selfCheck_pReal_heldOutReal': round(float(chk), 3), 'fad': fads,
               'refs': [r['slug'] for r in R], 'clips': len(clips)},
              open(os.path.join(DB, 'summary.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'自我檢查(留下來的真錄音被判成真的機率,應該接近 1):{chk:.3f}')
    for r in sorted(out, key=lambda r: -r['pReal']):
        print(f"{r['id']}  {r['commit']:8} {r['feel']:9} {r['style']:6} P(真)={r['pReal']:.3f}  最近距離={r['nearDist']:.3f}")
    print('FAD(越小越像參考曲):', fads)

def cmd_analyze(a):
    clips = {c['id']: c for c in jl(os.path.join(DB, 'clips.jsonl'))}
    sc = {s['id']: s for s in jl(os.path.join(DB, 'scores.jsonl'))}
    rt = jl(os.path.join(DB, 'ratings.jsonl'))
    by = {}
    for r in rt: by.setdefault(r['clip'], []).append(r)
    rows = []
    for cid, rs in by.items():
        if cid not in clips: continue
        f = clips[cid]['features']; s = sc.get(cid, {})
        rows.append({'id': cid, 'human': float(np.mean([r['score'] for r in rs])), 'n': len(rs),
                     'pReal': s.get('pReal'), 'nearDist': s.get('nearDist'), 'crest': f['crest'],
                     'corr': f['corr'], 'rms': f['rms'],
                     **{f'b{b}': f['bandsRel'][i] for i, b in enumerate([31, 63, 125, 250, 500, '1k', '2k', '4k', '8k', '16k'])}})
    fake = {}
    for r in rt:
        for k in r.get('fake', []): fake[k] = fake.get(k, 0) + 1
    lines = ['## 自動產生的分析(`python realism.py analyze`)', '',
             f'- 評分筆數:{len(rt)}、有分數的片段:{len(rows)}']
    if len(rows) >= 5:
        h = np.array([r['human'] for r in rows])
        lines.append('- 各指標跟你的分數的相關(Spearman,|ρ|>0.5 才算有關):')
        from scipy.stats import spearmanr
        for k in [k for k in rows[0] if k not in ('id', 'human', 'n')]:
            v = np.array([r[k] if r[k] is not None else np.nan for r in rows], float)
            ok = ~np.isnan(v)
            if ok.sum() >= 5: lines.append(f'  - `{k}`: ρ = {spearmanr(v[ok], h[ok]).correlation:+.2f}')
    else:
        lines.append('- 評分少於 5 個片段,還不能算相關')
    if fake: lines.append('- 被勾「聽起來假」的樂器:' + '、'.join(f'{k} {v} 次' for k, v in sorted(fake.items(), key=lambda x: -x[1])))
    path = os.path.join(HERE, 'KNOWLEDGE.md'); txt = open(path).read() if os.path.exists(path) else '# 真實度知識庫\n'
    mark = '<!-- AUTO -->'
    txt = txt.split(mark)[0].rstrip() + '\n\n' + mark + '\n' + '\n'.join(lines) + '\n'
    open(path, 'w').write(txt); print('\n'.join(lines))

def _dataset():
    clips = {c['id']: c for c in jl(os.path.join(DB, 'clips.jsonl'))}
    by = {}
    for r in jl(os.path.join(DB, 'ratings.jsonl')): by.setdefault(r['clip'], []).append(r['score'])
    ids = [i for i in by if i in clips and clip_emb(clips[i]) is not None]
    y = np.array([np.mean(by[i]) for i in ids])
    hand = np.array([clips[i]['features']['bandsRel'] + [clips[i]['features'][k] for k in ('crest', 'corr', 'rms', 'bal')] for i in ids])
    emb = np.array([clip_emb(clips[i]).mean(0) for i in ids])
    return ids, y, {'聲學特徵': hand, 'VGGish': emb, '兩者合併': np.hstack([hand, emb])}

def _ridge(X, y, lam):
    mu, sd = X.mean(0), X.std(0) + 1e-6; Z = (X - mu) / sd; ym = y.mean()
    w = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - ym))
    return {'mu': mu.tolist(), 'sd': sd.tolist(), 'w': w.tolist(), 'b': float(ym)}

def _pred(m, X):
    return ((X - np.array(m['mu'])) / np.array(m['sd'])) @ np.array(m['w']) + m['b']

def cmd_learn(a):
    """學你的耳朵:ridge 回歸,**留一驗證**(每次拿掉一段、用其餘的訓練、猜它)。
    比的是「猜平均分」這條基準線——贏不了它就代表還沒學到東西,要老實說"""
    from scipy.stats import spearmanr
    ids, y, sets = _dataset()
    n = len(y); print(f'樣本 {n} 段,分數平均 {y.mean():.2f},分數種類 {sorted(set(y.tolist()))}')
    base = np.mean([abs(y[i] - np.delete(y, i).mean()) for i in range(n)])
    print(f'基準線(永遠猜平均):平均誤差 {base:.2f} 分')
    best = None
    for name, X in sets.items():
        for lam in (1, 10, 100, 1000):
            p = np.array([_pred(_ridge(np.delete(X, i, 0), np.delete(y, i), lam), X[i:i + 1])[0] for i in range(n)])
            mae = np.abs(np.clip(p, 1, 5) - y).mean(); rho = spearmanr(p, y).correlation
            if best is None or mae < best[0]: best = (mae, name, lam, rho)
            print(f'  {name:6} λ={lam:<5} 留一驗證平均誤差 {mae:.2f}  排序相關 ρ={rho:+.2f}')
    mae, name, lam, rho = best
    m = _ridge(sets[name], y, lam); m.update({'features': name, 'lam': lam, 'looMAE': round(float(mae), 3),
        'looRho': round(float(rho), 3), 'baselineMAE': round(float(base), 3), 'n': n})
    json.dump(m, open(os.path.join(DB, 'model.json'), 'w'))
    verdict = '贏過基準線' if mae < base - 0.05 else '**沒有贏過基準線**(樣本太少,還不能信)'
    print(f'最好的:{name} λ={lam},誤差 {mae:.2f} vs 基準 {base:.2f} → {verdict}')

def cmd_predict(a):
    """用學到的模型幫還沒人打分的片段打分"""
    m = json.load(open(os.path.join(DB, 'model.json')))
    clips = {c['id']: c for c in jl(os.path.join(DB, 'clips.jsonl'))}
    rated = {r['clip'] for r in jl(os.path.join(DB, 'ratings.jsonl'))}
    for i, c in clips.items():
        e = clip_emb(c)
        if e is None: continue
        hand = np.array([c['features']['bandsRel'] + [c['features'][k] for k in ('crest', 'corr', 'rms', 'bal')]])
        X = {'聲學特徵': hand, 'VGGish': e.mean(0)[None], '兩者合併': np.hstack([hand, e.mean(0)[None]])}[m['features']]
        print(f"{i} {c['commit']} {c['feel']:9} {c['style']:6} 預測 {float(np.clip(_pred(m, X)[0], 1, 5)):.2f}" + ('  (已有人工分)' if i in rated else ''))

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
r = sp.add_parser('ref'); rs = r.add_subparsers(dest='sub', required=True)
ra = rs.add_parser('add'); ra.add_argument('file'); ra.add_argument('--name', required=True); ra.add_argument('--genre', required=True)
ra.add_argument('--start', type=float); ra.add_argument('--end', type=float); ra.add_argument('--vocal', action='store_true')
sp.add_parser('score'); sp.add_parser('analyze'); sp.add_parser('learn'); sp.add_parser('predict')
a = ap.parse_args()
{'ref': cmd_ref_add, 'score': cmd_score, 'analyze': cmd_analyze, 'learn': cmd_learn, 'predict': cmd_predict}[a.cmd](a)
