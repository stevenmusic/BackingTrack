#!/usr/bin/env python3
"""每一件樂器符不符合 City Pop:htdemucs_6s 的五軌(鼓/貝斯/吉他/鋼琴/其他)各量同一組特徵,
拿我們的跟 12 首真歌比,落在真歌範圍外的標出來。
  - 佔伴奏 dB(五軌能量總和)、每拍起音、一拍四格(拍點/e/&/a)的出現率
  - 每一下多長(拍)、音域(CQT 能量加權 midi)、亮度(頻譜重心 Hz)、反拍/拍點力度
  - 音準:這一軌的 `estimate_tuning` 減掉整首有音高的幾軌的中位數(音分)——
    老唱片本身不一定是 A440,所以只看「跟同一首的其他樂器差多少」
  /tmp/abx/bin/python instgram.py 輸出.json <名字=資料夾> ...   (資料夾是 htdemucs_6s 的一首)"""
import sys, os, json, numpy as np, soundfile as sf, librosa
SR = 22050
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other']
def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
out = {}
for arg in sys.argv[2:]:
    name, d = arg.split('=', 1)
    y = {s: load(d, s) for s in STEMS}
    tempo, beats = librosa.beat.beat_track(y=y['drums'] + y['bass'], sr=SR, start_bpm=105, tightness=200, units='time')
    tempo = float(np.atleast_1d(tempo)[0]); spb = 60 / tempo
    tot = sum(float(np.mean(v ** 2)) for v in y.values()) + 1e-12
    hop = 256; res = {'bpm': round(tempo, 1)}; tunes = {}
    for s in STEMS:
        g = y[s]; e = float(np.mean(g ** 2))
        r = {'佔伴奏dB': round(10 * np.log10(e / tot + 1e-12), 1)}
        if e < 1e-7: res[s] = r; continue
        env = librosa.onset.onset_strength(y=g, sr=SR, hop_length=hop)
        on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=hop, units='time', delta=0.08)
        rms = librosa.feature.rms(y=g, hop_length=hop)[0]; tt = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=hop)
        thr = np.percentile(rms, 90) * 0.2
        slot = np.zeros(4); stg = [[], [], [], []]; durs = []; ab = 0
        for i in range(len(beats) - 1):
            a, b = beats[i], beats[i + 1]
            fa, fb = np.searchsorted(tt, a), np.searchsorted(tt, b)
            if rms[fa:fb].max(initial=0) < thr: continue
            ab += 1
            for t in on[(on >= a - 0.03) & (on < b - 0.03)]:
                k = int(np.clip(round((t - a) / (b - a) * 4), 0, 4)) % 4
                slot[k] += 1
                f0 = np.searchsorted(tt, t); pk = rms[f0:f0 + 6].max(initial=1e-9); stg[k].append(pk)
                j = f0 + int(np.argmax(rms[f0:f0 + 6])); end = j
                while end < len(rms) - 1 and rms[end] > pk * 10 ** (-15 / 20) and tt[end] - tt[j] < 2 * spb: end += 1
                durs.append((tt[end] - tt[j]) / spb)
        if ab < 8: res[s] = r; continue
        sm = [float(np.mean(v)) if v else 0 for v in stg]
        r.update({'每拍起音': round(slot.sum() / ab, 2), '拍點/e/&/a': [round(v / ab, 2) for v in slot],
                  '音長(拍)': round(float(np.median(durs)), 2) if durs else None,
                  '亮度Hz': round(float(np.median(librosa.feature.spectral_centroid(y=g, sr=SR, hop_length=hop)[0][rms > thr]))),
                  '反拍/拍點力度': round(sm[2] / sm[0], 2) if sm[0] else None})
        if s != 'drums':
            lo = 'E1' if s == 'bass' else 'E2'
            C = np.abs(librosa.cqt(g, sr=SR, hop_length=hop, fmin=librosa.note_to_hz(lo), n_bins=60)) ** 2
            mid = librosa.note_to_midi(lo) + np.arange(60)
            r['音域(midi)'] = round(float((C.sum(1) * mid).sum() / C.sum()), 1)
            act = g[np.repeat(rms > thr, hop)[:len(g)]] if (rms > thr).any() else g
            tunes[s] = float(librosa.estimate_tuning(y=act[:SR * 60], sr=SR, resolution=0.01)) * 100
        res[s] = r
    ref = float(np.median(list(tunes.values()))) if tunes else 0
    for s, v in tunes.items(): res[s]['音準差(音分)'] = round(v - ref, 1)
    out[name] = res
    print(name, json.dumps(res, ensure_ascii=False), flush=True)
json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
