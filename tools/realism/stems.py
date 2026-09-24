#!/usr/bin/env python3
"""參考曲分軌之後逐樣樂器比:鼓、貝斯、其他樂器(人聲丟掉)。
  /tmp/abx/bin/python -m demucs -n htdemucs -o <out> song.wav   # 先分軌
  /tmp/abx/bin/python stems.py <分軌資料夾> [...]
量的是「演奏與平衡」,不是整首的頻譜(整首頻譜有人聲,拿來對 EQ 會把伴奏調壞,踩過)。
音檔不進 repo,只有量出來的數字(寫到 db/stems.json)。"""
import sys, os, json, numpy as np, soundfile as sf
from scipy.signal import butter, sosfiltfilt, find_peaks
def load(p):
    x, sr = sf.read(p, always_2d=True, dtype='float32'); return x, sr
def db(x): return 10 * np.log10(np.mean(x ** 2) + 1e-12)
def env(x, sr, hop):
    m = np.abs(x).reshape(-1)[: (len(x) // hop) * hop].reshape(-1, hop).max(1); return m
def onsets(mono, sr, lo=None, hi=None, hop=256, th=1.5):
    y = mono
    if lo or hi:
        sos = butter(4, [lo, hi] if lo and hi else (hi or lo), 'band' if lo and hi else ('low' if hi else 'high'), fs=sr, output='sos')
        y = sosfiltfilt(sos, mono)
    e = np.sqrt(np.convolve(y ** 2, np.ones(hop) / hop, 'same')[::hop] + 1e-12)
    le = np.log(e); d = np.maximum(0, np.diff(le, prepend=le[0]))
    pk, _ = find_peaks(d, height=np.median(d) + th * d.std(), distance=int(0.06 * sr / hop))
    return pk * hop / sr, e
def tempo(times, lo=70, hi=160):
    # 自相關找每分鐘拍數:把所有 onset 放到 10ms 的格子上
    if len(times) < 20: return None
    g = np.zeros(int(times[-1] * 100) + 10); g[(times * 100).astype(int)] = 1
    ac = np.correlate(g, g, 'full')[len(g) - 1:]
    lags = np.arange(len(ac)); bpm = 6000 / np.maximum(lags, 1)
    ok = (bpm >= lo) & (bpm <= hi)
    best = lags[ok][np.argmax(ac[ok])]
    # 細調:在附近掃
    return round(6000 / best, 1)
def f0(seg, sr):
    # 貝斯的基頻:自相關,限 30–200Hz
    seg = seg - seg.mean(); n = len(seg)
    if n < sr * 0.05: return None
    ac = np.correlate(seg, seg, 'full')[n - 1:]
    lo, hi = int(sr / 200), int(sr / 30)
    if hi >= n: return None
    k = lo + np.argmax(ac[lo:hi]); return sr / k if ac[k] > 0.3 * ac[0] else None
def analyze(folder, start=None, end=None):
    st = {}
    for k in ('drums', 'bass', 'other'):
        x, sr = load(os.path.join(folder, k + '.wav'))
        if start is not None: x = x[int(start * sr): int(end * sr) if end else None]
        st[k] = x
    mix = st['drums'] + st['bass'] + st['other']
    act = env(mix.mean(1), sr, 4800) > 0.02 * np.abs(mix).max()       # 只算真的在響的部分
    def active(x): e = x.mean(1)[: (len(x) // 4800) * 4800].reshape(-1, 4800); return e[act[: len(e)]].reshape(-1)
    out = {'sec': round(len(mix) / sr, 1)}
    tot = db(active(mix))
    for k, x in st.items():
        L, R = x[:, 0], x[:, 1]
        m = active(x)
        spec = np.abs(np.fft.rfft(m[: sr * 30] if len(m) > sr * 30 else m)) ** 2; fr = np.fft.rfftfreq(len(m[: sr * 30] if len(m) > sr * 30 else m), 1 / sr)
        bands = {b: 10 * np.log10(spec[(fr >= a) & (fr < c)].sum() / spec.sum() + 1e-12) for b, (a, c) in
                 {'<120': (20, 120), '120-500': (120, 500), '500-2k': (500, 2000), '2k-6k': (2000, 6000), '>6k': (6000, 20000)}.items()}
        out[k] = {'rel_dB': round(db(m) - tot, 1), 'corr': round(float(np.corrcoef(L, R)[0, 1]), 3),
                  'crest_dB': round(float(20 * np.log10(np.abs(m).max() + 1e-9) - db(m)), 1),
                  'centroid_Hz': int((fr * spec).sum() / spec.sum()), 'bands': {b: round(v, 1) for b, v in bands.items()}}
    # 節奏:鼓的 onset 抓速度與十六分的搖擺
    dm = st['drums'].mean(1); t, _ = onsets(dm, sr)
    bpm = tempo(t); out['bpm'] = bpm
    if bpm:
        beat = 60 / bpm
        # 用 hi-hat 那一段(>6k)的 onset 看十六分的位置分布
        th, _ = onsets(dm, sr, lo=6000, hi=None)
        ph = (th / beat) % 1.0
        # 找相位的偏移(第一拍在哪)——用最多 onset 落點的相位當 0
        h, edges = np.histogram(ph, 48, (0, 1)); off = edges[np.argmax(h)]
        ph = (ph - off) % 1.0
        slots = np.round(ph * 4) % 4
        dev = (ph - np.round(ph * 4) / 4)                              # 離直的十六分差多少拍
        out['hat_16th_share'] = [round(float(np.mean(slots == s)), 3) for s in range(4)]
        out['hat_dev_ms'] = [round(float(np.median(dev[slots == s]) * beat * 1000), 1) if np.any(slots == s) else None for s in range(4)]
        out['hat_per_beat'] = round(len(th) / (len(dm) / sr / beat), 2)
        # 貝斯:每拍幾顆、音長、音程
        bm = st['bass'].mean(1); tb, eb = onsets(bm, sr, hi=400, th=1.2)
        out['bass_per_beat'] = round(len(tb) / (len(bm) / sr / beat), 2)
        durs, pitches = [], []
        for i, t0 in enumerate(tb):
            t1 = tb[i + 1] if i + 1 < len(tb) else t0 + beat
            a, b2 = int(t0 * sr), int(t1 * sr); seg = bm[a:b2]
            if len(seg) < 200: continue
            e = np.abs(seg); pk = e[: int(0.05 * sr)].max() + 1e-9
            # 音長:包絡掉到尖峰的 -12dB 之前撐了多久(除以到下一顆的距離 = 連奏程度)
            sm = np.convolve(e, np.ones(256) / 256, 'same'); below = np.where(sm < pk * 0.25)[0]
            dur = (below[below > int(0.02 * sr)][0] / sr) if np.any(below > int(0.02 * sr)) else (b2 - a) / sr
            durs.append(min(1.0, dur / ((b2 - a) / sr)))
            p = f0(seg[int(0.03 * sr): int(0.03 * sr) + int(0.12 * sr)], sr)
            if p: pitches.append(12 * np.log2(p / 440) + 69)
        pitches = np.array(pitches); iv = np.abs(np.diff(pitches)) if len(pitches) > 2 else np.array([])
        ivr = np.round(iv)
        out['bass_legato'] = round(float(np.median(durs)), 2) if durs else None
        out['bass_range_semi'] = round(float(np.percentile(pitches, 95) - np.percentile(pitches, 5)), 1) if len(pitches) > 5 else None
        if len(ivr):
            out['bass_intervals'] = {'same': round(float(np.mean(ivr == 0)), 2), 'step(1-2)': round(float(np.mean((ivr >= 1) & (ivr <= 2))), 2),
                                     'leap(3-7)': round(float(np.mean((ivr >= 3) & (ivr <= 7))), 2), 'octave(11-13)': round(float(np.mean((ivr >= 11) & (ivr <= 13))), 2)}
    return out
if __name__ == '__main__':
    res = {}
    for f in sys.argv[1:]:
        name = os.path.basename(f.rstrip('/'))
        res[name] = json.loads(json.dumps(analyze(f), default=float)); print(name, json.dumps(res[name], ensure_ascii=False))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'stems.json')
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(res); json.dump(old, open(p, 'w'), ensure_ascii=False, indent=1, default=float)
