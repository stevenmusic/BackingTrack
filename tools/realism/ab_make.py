#!/usr/bin/env python3
"""City Pop A/B(REVIEW.md 第三輪「下一步」3、4、6):量改前 / 改後的風格特徵,並做盲聽檔。
  /tmp/abx/bin/python ab_make.py measure   → 每個版本的 和聲7.延伸音、other 有聲亮度中位數(分軌在 /tmp/sty/sep_ab)
  /tmp/abx/bin/python ab_make.py blind     → 做盲聽檔到 /tmp/sty/blind/:
      每一項(ext、bright)× 每組進行一對,A / B 誰是改後由種子決定;兩個版本的 RMS 對齊到 ±0.3dB 以內
      對照表寫到 /tmp/sty/blind/_key.json(**不給 Steven 看**);音檔不進 repo"""
import sys, os, json, glob, hashlib
import numpy as np, soundfile as sf, librosa
H = os.path.dirname(os.path.abspath(__file__))
sys.argv, ARGS = sys.argv[:1], sys.argv[1:]          # style.py 在 import 時會讀 sys.argv
sys.path.insert(0, H)
import style

AB = '/tmp/sty/ab'
rows = [json.loads(l) for l in open(os.path.join(AB, 'clips.jsonl'))]
lab = {r['id']: (r['label'].replace('ab_', ''), r['prog']) for r in rows}
SHORT = {'Fmaj7 - E7 - Am7 - C7': 'marusa', 'Fmaj7 - G7 - Em7 - Am7 - Dm7 - G7 - Cmaj7 - C7': 'ohdo8',
         'Fmaj7 Em7 | Am7 Dm7 | Fmaj7 Em7 | Dm7 G7': 'fedg', 'Dm7 G7 | Cmaj7 Am7 | Fmaj7 | Em7': 'iivi'}


def other_active(d):
    x, sr = sf.read(os.path.join(d, 'other.wav'), always_2d=True, dtype='float32')
    y = librosa.resample(x.mean(1), orig_sr=sr, target_sr=22050)
    c = librosa.feature.spectral_centroid(y=y, sr=22050, hop_length=512)[0]
    r = librosa.feature.rms(y=y, hop_length=512)[0]
    return float(np.median(c[r > r.max() * 10 ** (-30 / 20)]))


def measure():
    res = {}
    for d in sorted(glob.glob('/tmp/sty/sep_ab/htdemucs_6s/*/')):
        cid = os.path.basename(d.rstrip('/'))
        if cid not in lab: continue
        v, p = lab[cid]
        f = style.feats(d)
        res.setdefault(v, []).append({'prog': SHORT.get(p, p), '和聲7.延伸音': f['和聲7.延伸音'],
                                      '和聲7.模板外': f['和聲7.模板外'], 'other有聲亮度': other_active(d)})
    for v, xs in res.items():
        print(f'{v:7s} n={len(xs)}  和聲7.延伸音 {np.mean([x["和聲7.延伸音"] for x in xs]):.3f}  '
              f'和聲7.模板外 {np.mean([x["和聲7.模板外"] for x in xs]):.3f}  other 有聲亮度 {np.mean([x["other有聲亮度"] for x in xs]):.0f}Hz')
    json.dump(res, open(os.path.join(H, 'db', 'ab_citypop.json'), 'w'), ensure_ascii=False, indent=1)
    print('參考:和聲7.延伸音 真歌 0.184 / Suno 0.182 / 改前 0.145;other 有聲亮度 上傳真歌 2223 / Suno 2306 / 改前 1320')


def blind():
    out = '/tmp/sty/blind'; os.makedirs(out, exist_ok=True)
    wav = {lab[r['id']]: os.path.join(AB, 'clips', r['id'] + '.wav') for r in rows if r['id'] in lab}
    key = {}
    for item in ('ext', 'bright'):
        for p, s in SHORT.items():
            a, b = wav.get(('base', p)), wav.get((item, p))
            if not a or not b: continue
            xa, sr = sf.read(a, always_2d=True); xb, _ = sf.read(b, always_2d=True)
            n = min(len(xa), len(xb)); xa, xb = xa[:n], xb[:n]
            g = np.sqrt(np.mean(xa ** 2) / (np.mean(xb ** 2) + 1e-12)); xb = xb * g          # 改後對齊改前的 RMS
            peak = max(np.abs(xa).max(), np.abs(xb).max())
            if peak > 0.95: xa, xb = xa * 0.95 / peak, xb * 0.95 / peak
            flip = int(hashlib.sha1(f'{item}:{s}'.encode()).hexdigest(), 16) % 2 == 1     # 固定種子
            A, B = (xb, xa) if flip else (xa, xb)
            fa, fb = f'cp_{item}_A_{s}.wav', f'cp_{item}_B_{s}.wav'
            sf.write(os.path.join(out, fa), A, sr, subtype='PCM_16'); sf.write(os.path.join(out, fb), B, sr, subtype='PCM_16')
            dr = 20 * np.log10(np.sqrt(np.mean(A ** 2)) / np.sqrt(np.mean(B ** 2)))
            key[f'{item}_{s}'] = {'改後是': 'A' if flip else 'B', 'RMS差dB': round(float(dr), 2)}
            print(fa, fb, f'RMS 差 {dr:+.2f}dB')
    json.dump(key, open(os.path.join(out, '_key.json'), 'w'), ensure_ascii=False, indent=1)


{'measure': measure, 'blind': blind}[ARGS[0] if ARGS else 'measure']()
