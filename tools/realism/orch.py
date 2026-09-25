#!/usr/bin/env python3
"""配器分析:用 htdemucs_6s 把歌拆成 鼓/貝斯/吉他/鋼琴(含電鋼琴)/其他/人聲,量每一件的
- 佔伴奏(不含人聲)的 dB、每拍幾個起音、十六分 e/a 上的比例(切音 vs 長音)、音長、亮度(頻譜重心 Hz)
  /tmp/abx/bin/python orch.py "<6軌資料夾 glob>" <標籤>"""
import sys, glob, os, json, numpy as np, soundfile as sf, librosa
SR = 22050
pat, label = sys.argv[1], sys.argv[2]
def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
out = {}
for d in sorted(glob.glob(pat)):
    st = {s: load(d, s) for s in ('drums', 'bass', 'guitar', 'piano', 'other')}
    mix = sum(st.values())
    tempo, beats = librosa.beat.beat_track(y=mix, sr=SR, units='time', start_bpm=105, tightness=200)
    spb = float(np.median(np.diff(beats))); tot = sum(float((v ** 2).mean()) for v in st.values())
    r = {'bpm': round(60 / spb, 1)}
    for s in ('guitar', 'piano', 'other'):
        x = st[s]; e = float((x ** 2).mean())
        env = librosa.onset.onset_strength(y=x, sr=SR, hop_length=256)
        on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=256, units='time', delta=0.1)
        pos = []
        for o in on:
            i = np.searchsorted(beats, o) - 1
            if 0 <= i < len(beats) - 1:
                f = (o - beats[i]) / (beats[i + 1] - beats[i]); pos.append(int(round(f * 4)) % 4)
        pos = np.array(pos)
        cent = librosa.feature.spectral_centroid(y=x, sr=SR)[0]
        rms = librosa.feature.rms(y=x)[0]
        # 音長:能量在起音之後掉 12dB 要多久(拍)
        durs = []
        t = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=512)
        for o in on[:200]:
            k = np.searchsorted(t, o); seg = rms[k:k + 60]
            if len(seg) < 5: continue
            pk = seg[:6].max(); low = np.where(seg < pk * 0.25)[0]
            if len(low): durs.append(t[k + low[0]] - t[k])
        r[s] = {'佔伴奏dB': round(10 * np.log10(e / tot + 1e-12), 1),
                '每拍起音': round(len(on) / (len(beats)), 2),
                'e或a比例': round(float(np.isin(pos, [1, 3]).mean()), 2) if len(pos) else 0,
                '音長拍': round(float(np.median(durs)) / spb, 2) if durs else None,
                '亮度Hz': int(np.median(cent[rms > rms.max() * 0.05])) if (rms > 0).any() else 0}
    out[os.path.basename(d)] = r
    print(os.path.basename(d), r, flush=True)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'orch.json')
allr = json.load(open(p)) if os.path.exists(p) else {}
allr[label] = out; json.dump(allr, open(p, 'w'), ensure_ascii=False, indent=1)
