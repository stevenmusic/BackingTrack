#!/usr/bin/env python3
"""人聲滲漏實驗(REVIEW.md B1):在我們的伴奏上混一條「像人聲」的旋律,再拆軌、再量風格尺的和聲類特徵。
旋律照伴奏自己的和弦寫:每拍用鋼琴+吉他分軌判出的和弦(含七和弦模板),強拍落和弦音、弱拍走 C 大調/A 小調音階的鄰音
(真的人聲旋律本來就有經過音與延伸音)。音色:鋸齒波 → 三顆母音共振峰帶通(/a/:800 / 1150 / 2900Hz)+ 5.5Hz 顫音 ±30 音分。
音量:旋律 RMS = 伴奏 RMS − 3dB(流行歌的人聲跟伴奏差不多大)。
  /tmp/abx/bin/python leak_melody.py <伴奏 wav 資料夾> <伴奏分軌資料夾 htdemucs_6s> <輸出資料夾>"""
import sys, glob, os, numpy as np, soundfile as sf, librosa, scipy.signal as ss
src, sep, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
SCALE = [0, 2, 4, 5, 7, 9, 11]   # C 大調 / A 小調:我們的段落庫全部在這個調(CLAUDE.md「段落庫」),測試片段也是
# 判和弦用「÷ 音數」,跟 style.py 的「÷ √音數」不一樣(第一輪審查建議 6)。刻意不改:REVIEW.md B1 的數字是用這一版產生的,
# 改了就重現不了。這裡只用來決定旋律落哪個音,不影響量測本身
TEMPL = {'maj': (0, 4, 7), 'min': (0, 3, 7), 'maj7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10), '7': (0, 4, 7, 10), 'm7b5': (0, 3, 6, 10)}
def chord_at(c):
    best = max(((sum(c[(r + i) % 12] for i in iv) / len(iv), r, iv) for r in range(12) for iv in TEMPL.values()))
    return best[1], best[2]
rng = np.random.default_rng(7)
for f in sorted(glob.glob(os.path.join(src, '*.wav'))):
    tag = os.path.splitext(os.path.basename(f))[0]
    x, sr = sf.read(f, always_2d=True)
    d = os.path.join(sep, tag)
    h = sum(librosa.to_mono(sf.read(os.path.join(d, s + '.wav'), always_2d=True)[0].T) for s in ('piano', 'guitar', 'other'))
    hs = sf.info(os.path.join(d, 'piano.wav')).samplerate
    y22 = librosa.resample(h, orig_sr=hs, target_sr=22050)
    tempo, beats = librosa.beat.beat_track(y=librosa.resample(x.mean(1), orig_sr=sr, target_sr=22050), sr=22050)
    bt = librosa.frames_to_time(beats, sr=22050)
    C = librosa.feature.chroma_cqt(y=y22, sr=22050)
    ct = librosa.frames_to_time(np.arange(C.shape[1]), sr=22050)
    mel = np.zeros(len(x))
    prev = 69
    for i in range(len(bt) - 1):
        t0, t1 = bt[i], bt[i + 1]
        c = C[:, (ct >= t0) & (ct < t1)].mean(1)
        r, iv = chord_at(c)
        tones = [(r + k) % 12 for k in iv]
        for half in (0, 1):                                   # 一拍兩個八分
            ta = t0 + half * (t1 - t0) / 2; tb = ta + (t1 - t0) / 2
            if half == 0 or rng.random() < 0.5:
                cand = [m for m in range(60, 78) if m % 12 in tones]
            else:
                cand = [m for m in range(60, 78) if m % 12 in SCALE]   # 經過音 / 延伸音
            m = min(cand, key=lambda q: abs(q - prev) + rng.random() * 3)
            prev = m
            if rng.random() < 0.15:                           # 換氣
                continue
            n0, n1 = int(ta * sr), int(tb * sr)
            tt = np.arange(n1 - n0) / sr
            f0 = 440 * 2 ** ((m - 69) / 12) * 2 ** (30 / 1200 * np.sin(2 * np.pi * 5.5 * tt))
            ph = 2 * np.pi * np.cumsum(f0) / sr
            w = 2 * ((ph / (2 * np.pi)) % 1) - 1
            env = np.minimum(1, tt / 0.04) * np.minimum(1, (tt[-1] - tt + 1e-3) / 0.06)
            mel[n0:n1] += w * env
    v = np.zeros_like(mel)
    for fc, g in ((800, 1.0), (1150, 0.6), (2900, 0.25)):
        b, a = ss.butter(2, [fc * 0.85 / (sr / 2), fc * 1.15 / (sr / 2)], btype='band')
        v += g * ss.lfilter(b, a, mel)
    acc = np.sqrt(np.mean(x ** 2)); vr = np.sqrt(np.mean(v ** 2)) + 1e-9
    v *= acc / vr * 10 ** (-3 / 20)
    y = x + v[:, None] * np.array([0.5, 0.5])[None, :] * 2 ** 0.5
    y /= max(1.0, np.abs(y).max() / 0.95)
    sf.write(os.path.join(out, tag + '.wav'), y, sr)
    print(tag, 'ok', flush=True)
