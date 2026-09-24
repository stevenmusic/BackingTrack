#!/usr/bin/env python3
"""訓練「耳朵」:自己餵資料,再拿使用者的盲聽分數考試。
  /tmp/abx/bin/python ear.py embed    # 每段取 VGGish(平均+標準差 256 維)+ Audiobox 四軸,快取在 /tmp/ear
  /tmp/abx/bin/python ear.py train    # 三種資料一起訓練,寫 calib/ear.json 與 calib/ear_report.json

三種資料:
  1. 真實唱片:MUSDB18 的無人聲伴奏(/tmp/musdb/acc)、GTZAN(/tmp/gtzan/genres,1000 段 30 秒、10 種曲風,取中間 10 秒)+ Plastic Love → 標「真」
     我們錄的伴奏(校準集原樣 + 合成備援 + 盲聽題庫)→ 標「伴奏」
  2. 已知答案的配對(calib.py):原樣 > 弄壞的、真取樣 > 合成備援 → 排序限制
  3. 使用者的盲聽分數:**不拿來訓練耳朵本身**,只拿來考試(留一交叉驗證),
     再另外訓一個「耳朵分數 + 曲風」的小模型對到 1–5 分
兩個評分器內部都轉成 16kHz 單聲道,所以 GTZAN(22kHz 單聲道)跟我們(44kHz 立體聲)的格式差不會變成線索。
MERT(音樂自監督預訓練)凍結、只訓練最後一層;GTZAN 用過濾版切法(見 gt_split)。
音檔不進 repo;嵌入快取在 /tmp/ear,只有模型權重與報告進 repo。"""
import sys, os, json, glob
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(H, 'calib')
CACHE = '/tmp/ear'; GT = '/tmp/gtzan/genres'
GENRES = ['pop', 'blues', 'jazz', 'disco', 'rock', 'reggae', 'country', 'hiphop']   # 古典與金屬跟伴奏無關,不收
def jl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []

SPLIT = '/tmp/dnn-mgr/gtzan'   # Kereliuk & Sturm 的過濾版切法(git clone coreyker/dnn-mgr)
def gt_split():
    """GTZAN 有重複的歌與同一個歌手,隨機切會「在訓練集聽過同一首的另一段」→ 考試分數虛高。
    用學界修正過的切法:train+valid 拿來訓練、test 拿來考試,不在清單裡的(重複/壞檔)不收"""
    out = {}
    for part, lab in [('train', 'tr'), ('valid', 'tr'), ('test', 'te')]:
        for l in open(os.path.join(SPLIT, part + '_filtered.txt')):
            l = l.strip()
            if l: out['gt_' + os.path.basename(l)[:-4]] = lab
    return out

def items():
    """(key, 檔案, 起點秒, 類別)"""
    out = []; sp = gt_split()
    for g in GENRES:
        for f in sorted(glob.glob(os.path.join(GT, g, g + '.*.wav'))):
            k = 'gt_' + os.path.basename(f)[:-4]
            if k in sp: out.append((k, f, 10.0, 'real'))
    # MUSDB18 的分軌:鼓+貝斯+其他 = 沒有人聲的真實伴奏(44.1k 立體聲),比整首有人聲的 GTZAN 更對題
    for f in sorted(glob.glob('/tmp/musdb/acc/*.wav')):
        out.append(('md_' + os.path.basename(f)[:-4], f, 0.0, 'real'))
    for f in sorted(glob.glob(os.path.join(C, 'clips', '*.wav'))):
        k = os.path.basename(f)[:-4]
        out.append(('c_' + k, f, 0.0, 'real' if k.startswith('ref__') else 'ours'))
    return out

def cmd_embed():
    import torch, torchaudio, soundfile as sf
    torch.set_num_threads(int(os.environ.get('THREADS', '2')))
    sys.path.insert(0, H)
    from audiobox_aesthetics.infer import AesPredictor
    from vggish_np import VGGish, examples
    aes = AesPredictor(checkpoint_pth='/tmp/abx_ckpt/checkpoint.pt', precision='bf16')
    mert, mfe = load_mert()
    vg = VGGish(os.environ.get('VGGISH', '/tmp/vgg/vggish.pth'))
    os.makedirs(CACHE, exist_ok=True)
    todo = [it for it in items() if not os.path.exists(os.path.join(CACHE, it[0] + '.npz'))
            or 'mert' not in np.load(os.path.join(CACHE, it[0] + '.npz')).files]
    print('要算', len(todo), '段', flush=True)
    for i, (k, f, st, lab) in enumerate(todo):
        try:
            x, sr = sf.read(f, always_2d=True, dtype='float32')
        except Exception as e:
            print('讀不到', f, e); continue
        x = x[int(st * sr):int((st + 10) * sr)]
        if len(x) < sr * 5: continue
        p = os.path.join(CACHE, k + '.npz')
        old = dict(np.load(p)) if os.path.exists(p) else {}
        if 'vm' not in old:
            e = vg.embed(examples(x, sr))
            a = aes.forward([{'path': torch.from_numpy(x.T.copy()), 'sample_rate': sr}])[0]
            old.update(vm=e.mean(0), vs=e.std(0), aes=np.array([a['CE'], a['CU'], a['PC'], a['PQ']], dtype=np.float32))
        mono = torch.from_numpy(x.mean(1))
        m24 = torchaudio.functional.resample(mono, sr, mfe.sampling_rate).numpy()
        with torch.no_grad():
            hs = mert(**mfe(m24, sampling_rate=mfe.sampling_rate, return_tensors='pt'), output_hidden_states=True).hidden_states
        old['mert'] = torch.stack([h[0].mean(0) for h in hs]).numpy().astype(np.float16)   # 13 層 × 768,每層對時間取平均
        np.savez(p, **old)
        if i % 50 == 0: print(i, k, flush=True)

def load_mert():
    """MERT(音樂的自監督預訓練模型,m-a-p/MERT-v1-95M)。**位置卷積的權重要自己補**:
    新版 PyTorch 的 weight_norm 改了參數名稱,from_pretrained 會默默把它當成「新初始化」
    (log 裡那句 newly initialized),不補的話整個模型跑在一層隨機權重上"""
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoModel, Wav2Vec2FeatureExtractor
    m = AutoModel.from_pretrained('m-a-p/MERT-v1-95M', trust_remote_code=True).eval()
    sd = torch.load(hf_hub_download('m-a-p/MERT-v1-95M', 'pytorch_model.bin'), map_location='cpu')
    conv = m.encoder.pos_conv_embed.conv
    with torch.no_grad():
        conv.parametrizations.weight.original0.copy_(sd['encoder.pos_conv_embed.conv.weight_g'])
        conv.parametrizations.weight.original1.copy_(sd['encoder.pos_conv_embed.conv.weight_v'])
    return m, Wav2Vec2FeatureExtractor.from_pretrained('m-a-p/MERT-v1-95M', trust_remote_code=True)

FEAT = os.environ.get('FEAT', 'mert')   # vggish / mert / both
def feats(k):
    z = np.load(os.path.join(CACHE, k + '.npz'))
    parts = [z['aes']]
    if FEAT in ('vggish', 'both'): parts += [z['vm'], z['vs']]
    if FEAT in ('mert', 'both'): parts += [z['mert'][5:10].astype(np.float32).mean(0)]   # 中間層:音色與演奏的資訊最多
    return np.concatenate(parts)

def cmd_train():
    rng = np.random.default_rng(0)
    have = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(CACHE, '*.npz'))}
    its = [it for it in items() if it[0] in have]
    base = {r['id']: r for r in jl(os.path.join(C, 'clips.jsonl'))}
    # ── 1. 真 vs 伴奏 ──
    X = np.array([feats(k) for k, *_ in its]); y = np.array([1.0 if lab == 'real' else 0.0 for *_, lab in its])
    keys = [k for k, *_ in its]
    # ── 2. 已知答案的配對 ──
    pairs = []
    for i, r in base.items():
        if r.get('synth'): continue
        for d in ['lp', 'clip', 'noise', 'crush', 'tel', 'hp', 'wash', 'wow']:
            if 'c_' + i in have and f'c_{i}__{d}' in have: pairs.append(('c_' + i, f'c_{i}__{d}', i))
        for j, q in base.items():
            if q.get('synth') and q['feel'] == r['feel'] and q['prog'] == r['prog'] and r['style'] == 'comp' and 'c_' + j in have:
                pairs.append(('c_' + i, 'c_' + j, i))
    # 驗證切法:以「原始錄音」為單位切,同一段的破壞版不會一半在訓練一半在考試
    groups = sorted({g for *_, g in pairs}); rng.shuffle(groups); hold = set(groups[:len(groups) // 5])
    sp_ = gt_split(); hold_gt = {k for k in keys if sp_.get(k) == 'te'}
    # MUSDB 以「歌」為單位切:同一首的其他段落不能出現在訓練裡
    songs = sorted({k.split('__')[0] for k in keys if k.startswith('md_')}); rng.shuffle(songs)
    hold_gt |= {k for k in keys if k.startswith('md_') and k.split('__')[0] in set(songs[:len(songs) // 3])}
    idx = {k: n for n, k in enumerate(keys)}
    mu, sd = X.mean(0), X.std(0) + 1e-6; Z = (X - mu) / sd
    tr = np.array([not (k in hold_gt or any(k == a or k == b for a, b, g in pairs if g in hold)) for k in keys])
    P_tr = [(idx[a], idx[b]) for a, b, g in pairs if g not in hold]
    P_te = [(idx[a], idx[b]) for a, b, g in pairs if g in hold]
    w = np.zeros(Z.shape[1]); b0 = 0.0; lr = 0.05; lam = float(os.environ.get('L2', '3.0')); beta = float(os.environ.get('PAIRW', '1.0'))
    Ztr, ytr = Z[tr], y[tr]; pw = ytr.mean()
    A = np.array([Z[a] for a, _ in P_tr]); B = np.array([Z[b] for _, b in P_tr])
    for it in range(1500):
        p = 1 / (1 + np.exp(-(Ztr @ w + b0)))
        wt = np.where(ytr == 1, 0.5 / pw, 0.5 / (1 - pw))                      # 兩類等權
        g1 = Ztr.T @ ((p - ytr) * wt) / len(ytr); gb = ((p - ytr) * wt).mean()
        d = (A - B) @ w; q = 1 / (1 + np.exp(-d))
        g2 = -((1 - q)[:, None] * (A - B)).mean(0)
        w -= lr * (g1 + beta * g2 + lam * w / len(ytr)); b0 -= lr * gb
    score = lambda Q: Q @ w + b0
    s = score(Z)
    rep = {'特徵': FEAT, 'n_real': int(y.sum()), 'n_ours': int((1 - y).sum()), 'pairs_train': len(P_tr), 'pairs_test': len(P_te)}
    te = ~tr
    rep['真vs伴奏_考試正確率'] = round(float(((s[te] > 0) == (y[te] == 1)).mean()), 3)
    rep['配對_考試正確率'] = round(float(np.mean([s[a] > s[b] for a, b in P_te])), 3) if P_te else None
    kinds = {}
    for a, b, g in pairs:
        if g in hold:
            kd = b.split('__')[1] if '__' in b else 'synth'
            kinds.setdefault(kd, []).append(s[idx[a]] > s[idx[b]])
    rep['配對_各題型'] = {k: round(float(np.mean(v)), 3) for k, v in kinds.items()}
    md_te = [idx[k] for k in keys if k.startswith('md_') and k in hold_gt]
    ours_te = [idx[k] for k in keys if k.startswith('c_') and not k.startswith('c_ref') and not k.startswith('c_blind') and not tr[idx[k]]]
    if md_te: rep['真實伴奏(MUSDB 沒聽過的歌)判成真'] = round(float(np.mean(s[md_te] > 0)), 3)
    if ours_te: rep['我們的伴奏(考試那一份)判成伴奏'] = round(float(np.mean(s[ours_te] <= 0)), 3)
    # 唱片 > 我們的 City Pop(Plastic Love 那幾段有沒有被排在我們前面)
    refs = [idx[k] for k in keys if k.startswith('c_ref__')]
    cps = [idx['c_' + i] for i, r in base.items() if r['feel'] == 'citypop' and not r.get('synth') and 'c_' + i in idx]
    if refs and cps: rep['唱片>City Pop'] = round(float(np.mean([s[r] > s[c] for r in refs for c in cps])), 3)
    # ── 3. 考試:使用者的盲聽分數 ──
    R = jl(os.path.join(H, 'db', 'ratings.jsonl')); cl = {r['id']: r for r in jl(os.path.join(H, 'db', 'clips.jsonl'))}
    hum = {}
    for r in R: hum.setdefault(r['clip'], []).append(r['score'])
    ks = [c for c in hum if 'c_blind__' + c in idx]
    rk = lambda a: np.argsort(np.argsort(a, kind='stable'), kind='stable').astype(float)
    sp = lambda a, b: float(np.corrcoef(rk(np.array(a)), rk(np.array(b)))[0, 1])
    yh = np.array([np.mean(hum[c]) for c in ks]); eh = np.array([s[idx['c_blind__' + c]] for c in ks])
    rep['人評_n'] = len(ks)
    rep['人評_耳朵直接_spearman'] = round(sp(eh, yh), 3)
    # 小模型:耳朵分數 + 批次(使用者的尺度會飄)→ 1–5 分,留一
    feelmean = lambda c, excl: np.mean([np.mean(hum[d]) for d in ks if d != excl and cl[d]['feel'] == cl[c]['feel']] or [yh.mean()])
    bt = np.array([1.0 if cl[c].get('batch', 1) == 2 else 0.0 for c in ks])
    pred, predf = [], []
    for n, c in enumerate(ks):
        m = np.arange(len(ks)) != n
        F = np.c_[np.ones(m.sum()), eh[m], bt[m]]
        coef = np.linalg.solve(F.T @ F + np.diag([0, 1, 1]), F.T @ yh[m])
        pred.append(coef @ [1, eh[n], bt[n]]); predf.append(feelmean(c, c))
    rep['人評_耳朵+批次_留一_spearman'] = round(sp(pred, yh), 3)
    rep['人評_耳朵+批次_留一_MAE'] = round(float(np.abs(np.array(pred) - yh).mean()), 3)
    rep['對照_只看曲風_留一_spearman'] = round(sp(predf, yh), 3)
    rep['對照_只看曲風_留一_MAE'] = round(float(np.abs(np.array(predf) - yh).mean()), 3)
    rep['對照_全猜平均_MAE'] = round(float(np.abs(yh - yh.mean()).mean()), 3)
    json.dump(rep, open(os.path.join(C, f'ear_report_{FEAT}.json'), 'w'), ensure_ascii=False, indent=1)
    np.savez(os.path.join(C, f'ear_model_{FEAT}.npz'), w=w, b=b0, mu=mu, sd=sd)
    for k, v in rep.items(): print(f'{k}: {v}')

{'embed': cmd_embed, 'train': cmd_train}[sys.argv[1]]()
