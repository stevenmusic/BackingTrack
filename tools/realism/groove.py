#!/usr/bin/env python3
"""真人演奏的「語法」量測:分軌之後,每一軌在一拍四格(十六分)的每一格上
- 出現率(這一格有沒有人打)、力度(相對強度)、時間偏移(毫秒,正 = 落後)與偏移的標準差
- 音長(下一個起音之前,能量掉 12dB 用了這段間隔的幾成)
鼓再切三個頻段:大鼓(<150Hz)、小鼓(150–2k)、鈸(>6k)。
參考曲與我們的錄音**走同一條管線**(一樣用節拍追蹤找格子),兩邊的誤差才一樣。
  /tmp/abx/bin/python groove.py <分軌資料夾 glob> <標籤>"""
import sys, glob, os, json, numpy as np, soundfile as sf, librosa, scipy.signal as ss
pat, label = sys.argv[1], sys.argv[2]
SR = 22050
def load(d, stem):
    x, sr = sf.read(os.path.join(d, stem + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
def band(x, lo, hi):
    if lo and hi: sos = ss.butter(4, [lo, hi], 'bandpass', fs=SR, output='sos')
    elif lo: sos = ss.butter(4, lo, 'highpass', fs=SR, output='sos')
    else: sos = ss.butter(4, hi, 'lowpass', fs=SR, output='sos')
    return ss.sosfilt(sos, x)
def grid(d):
    mix = sum(load(d, s) for s in ('drums', 'bass', 'other'))
    tempo, beats = librosa.beat.beat_track(y=mix, sr=SR, units='time', start_bpm=105, tightness=200)
    beats = np.asarray(beats)
    # 十六分格:相鄰兩拍之間線性切四格(吃得下速度的微小飄移)
    g = []
    for a, b in zip(beats[:-1], beats[1:]):
        g += [a + (b - a) * k / 4 for k in range(4)]
    return np.array(g), float(np.median(np.diff(beats)))
def onsets(x):
    env = librosa.onset.onset_strength(y=x, sr=SR, hop_length=128)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=128, units='time', backtrack=False, delta=0.08)
    fr = librosa.time_to_frames(on, sr=SR, hop_length=128)
    return on, env[np.clip(fr, 0, len(env) - 1)]
def durfrac(x, on):
    rms = librosa.feature.rms(y=x, frame_length=1024, hop_length=128)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=128)
    out = []
    for i, o in enumerate(on[:-1]):
        nxt = on[i + 1]; s = (t >= o) & (t < nxt)
        if s.sum() < 3: continue
        r = rms[s]; pk = r.max(); k = np.argmax(r)
        low = np.where(r[k:] < pk * 10 ** (-12 / 20))[0]
        out.append(((low[0] + k) if len(low) else len(r)) / len(r))
    return out
def analyse(on, st, g, spb):
    slot = spb / 4
    R = {k: [] for k in range(4)}
    for o, s in zip(on, st):
        i = np.searchsorted(g, o) - 1
        if i < 0 or i + 1 >= len(g): continue
        j = i if o - g[i] < g[i + 1] - o else i + 1
        off = (o - g[j]) * 1000
        if abs(off) > slot * 1000 * 0.45: continue
        R[j % 4].append((off, s))
    n = len(g) / 4
    smax = max([s for v in R.values() for _, s in v] or [1])
    return {str(k): {'出現率': round(len(v) / n, 2), '力度': round(float(np.mean([s for _, s in v]) / smax), 2) if v else 0,
                     '偏移ms': round(float(np.mean([o for o, _ in v])), 1) if v else 0,
                     '偏移SD': round(float(np.std([o for o, _ in v])), 1) if v else 0} for k, v in R.items()}
res = {}
for d in sorted(glob.glob(pat)):
    g, spb = grid(d)
    r = {'bpm': round(60 / spb, 1)}
    dr = load(d, 'drums')
    for name, (lo, hi) in {'大鼓': (0, 150), '小鼓': (150, 2000), '鈸': (6000, 0)}.items():
        on, st = onsets(band(dr, lo, hi)); r[name] = analyse(on, st, g, spb)
    for stem, name in (('bass', '貝斯'), ('other', '其他')):
        x = load(d, stem); on, st = onsets(x); r[name] = analyse(on, st, g, spb)
        df = durfrac(x, on); r[name + '音長'] = round(float(np.median(df)), 2) if df else None
        r[name + '每拍幾個起音'] = round(len(on) / (len(g) / 4), 2)
    res[os.path.basename(d)] = r
    print(os.path.basename(d), r['bpm'], flush=True)
# 平均
keys = [k for k in next(iter(res.values())) if isinstance(next(iter(res.values()))[k], dict)]
avg = {}
for k in keys:
    avg[k] = {s: {m: round(float(np.mean([v[k][s][m] for v in res.values()])), 2) for m in ('出現率', '力度', '偏移ms', '偏移SD')} for s in '0123'}
for k in ('貝斯音長', '其他音長', '貝斯每拍幾個起音', '其他每拍幾個起音'):
    vals = [v[k] for v in res.values() if v.get(k) is not None]; avg[k] = round(float(np.mean(vals)), 2) if vals else None
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'groove.json')
allr = json.load(open(p)) if os.path.exists(p) else {}
allr[label] = {'平均': avg, '每首': res}; json.dump(allr, open(p, 'w'), ensure_ascii=False, indent=1)
print(json.dumps(avg, ensure_ascii=False))
