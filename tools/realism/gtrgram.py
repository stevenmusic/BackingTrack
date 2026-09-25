#!/usr/bin/env python3
"""吉他那一軌的「語法」:真歌與我們的 htdemucs_6s 吉他分軌,走同一條管線比。
  - 一拍四格(拍點 / e / & / a)的出現率,每拍幾下
  - 每一下多長(能量掉到峰值 −15dB 的時間,以拍為單位)
  - 同時幾個音(和弦 vs 單音):起音後 80ms 的 chroma 有幾個音級 ≥ 最大值的 45%
  - 音域:能量加權的平均 midi(CQT)、亮度(頻譜重心)
  - 強弱:拍點與反拍的起音強度比
  /tmp/abx/bin/python gtrgram.py <名字=資料夾> ...   (資料夾內要有 guitar.wav 與 drums.wav)"""
import sys, os, json, numpy as np, soundfile as sf, librosa
SR = 22050
def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
res = {}
for arg in sys.argv[1:]:
    name, d = arg.split('=', 1)
    g = load(d, 'guitar'); dr = load(d, 'drums'); ba = load(d, 'bass')
    if np.sqrt(np.mean(g ** 2)) < 1e-4: continue
    tempo, beats = librosa.beat.beat_track(y=dr + ba, sr=SR, start_bpm=105, tightness=200, units='time')
    tempo = float(np.atleast_1d(tempo)[0])
    hop = 256
    env = librosa.onset.onset_strength(y=g, sr=SR, hop_length=hop)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=hop, units='time', backtrack=False, delta=0.08)
    rms = librosa.feature.rms(y=g, hop_length=hop)[0]; tt = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=hop)
    chroma = librosa.feature.chroma_cqt(y=g, sr=SR, hop_length=hop)
    C = np.abs(librosa.cqt(g, sr=SR, hop_length=hop, fmin=librosa.note_to_hz('E2'), n_bins=60))
    spb = 60 / tempo
    slot = np.zeros(4); strength = [[], [], [], []]; durs = []; poly = []
    # 只算有吉他在響的地方(整軌 RMS 的 20% 以上),前奏沒吉他不要稀釋
    thr = np.percentile(rms, 90) * 0.2
    active_beats = 0
    for i in range(len(beats) - 1):
        a, b = beats[i], beats[i + 1]
        fa, fb = np.searchsorted(tt, a), np.searchsorted(tt, b)
        if rms[fa:fb].max(initial=0) < thr: continue
        active_beats += 1
        for t in on[(on >= a - 0.03) & (on < b - 0.03)]:
            k = int(np.clip(round((t - a) / (b - a) * 4), 0, 4)) % 4
            slot[k] += 1
            f0 = np.searchsorted(tt, t); pk = rms[f0:f0 + 6].max(initial=1e-9)
            strength[k].append(pk)
            j = f0 + int(np.argmax(rms[f0:f0 + 6]))
            end = j
            while end < len(rms) - 1 and rms[end] > pk * 10 ** (-15 / 20) and tt[end] - tt[j] < 2 * spb: end += 1
            durs.append((tt[end] - tt[j]) / spb)
            ch = chroma[:, f0:f0 + max(1, int(0.08 * SR / hop))].mean(1)
            poly.append(int((ch >= ch.max() * 0.45).sum()))
    if active_beats < 8: continue
    E = C ** 2; mid = librosa.note_to_midi('E2') + np.arange(60)
    reg = float((E.sum(1) * mid).sum() / E.sum())
    cent = float(np.median(librosa.feature.spectral_centroid(y=g, sr=SR, hop_length=hop)[0][rms > thr]))
    sm = [float(np.mean(s)) if s else 0 for s in strength]
    res[name] = {'bpm': round(tempo, 1), '每拍起音': round(slot.sum() / active_beats, 2),
                 '拍點/e/&/a 每拍': [round(v / active_beats, 2) for v in slot],
                 '音長(拍)': round(float(np.median(durs)), 2), '同時音數': round(float(np.median(poly)), 1),
                 '和弦比例(≥3音)': round(float(np.mean(np.array(poly) >= 3)), 2),
                 '音域(midi)': round(reg, 1), '亮度Hz': round(cent),
                 '反拍/拍點力度': round(sm[2] / sm[0], 2) if sm[0] else None,
                 'e,a/拍點力度': round((sm[1] + sm[3]) / 2 / sm[0], 2) if sm[0] else None}
    print(name, json.dumps(res[name], ensure_ascii=False), flush=True)
json.dump(res, open(os.environ.get('GTR_OUT', '/tmp/gtrgram.json'), 'w'), ensure_ascii=False, indent=1)
