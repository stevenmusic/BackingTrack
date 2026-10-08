"""混音的數學檢查(用 tools/samples/render_styles.mjs 算出的分軌與全混音 WAV)。
用法:python3 tools/mix/analyze.py <WAV 資料夾> <style> [...]
檔名:<style>__high_8.wav(全混音)、<style>__high_8__dry.wav(不加殘響)、<style>__high_8_<軌>.wav(分軌)

1. 響度:ITU-R BS.1770-4 的 K-weighting + 400ms 區塊 + 絕對 / 相對門檻 → LUFS;各軌相對全混音幾 LU
2. 頻率飽滿:1/3 八度頻帶能量(Welch PSD),對 63Hz–8kHz 擬合一條斜線,偏離 ±6dB 以上的頻帶標出來;
   另外看 2–5kHz 相對斜線(伴奏要讓給主旋律)
3. 遮蔽:每個頻帶各軌占全混音能量的比例,兩軌在同一頻帶都 ≥ 30% 而且那個頻帶夠大聲 → 互相蓋住
4. 空間:左右相關係數、單聲道損失;殘響能量比(全混音 − 乾)/ 乾
"""
import sys, os, wave, numpy as np
from scipy import signal

def load(path):
    with wave.open(path) as w:
        sr = w.getframerate(); n = w.getnframes()
        x = np.frombuffer(w.readframes(n), np.int16).astype(np.float64) / 32768
    return x.reshape(-1, 2).T, sr

def kweight(x, sr):
    # BS.1770-4 的兩段濾波,係數照標準的類比原型用雙線性轉換算(跟 pyloudnorm 同一套公式)
    def shelf(f0=1681.974450955533, G=3.999843853973347, Q=0.7071752369554196):
        K = np.tan(np.pi * f0 / sr); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416
        a0 = 1 + K / Q + K * K
        b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
        a = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
        return b, a
    def hp(f0=38.13547087602444, Q=0.5003270373238773):
        K = np.tan(np.pi * f0 / sr); a0 = 1 + K / Q + K * K
        return [1, -2, 1], [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    b1, a1 = shelf(); b2, a2 = hp()
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=-1), axis=-1)

def lufs(x, sr):
    y = kweight(x, sr)
    blk, hop = int(0.4 * sr), int(0.1 * sr)
    ms = np.array([np.mean(y[:, i:i + blk] ** 2, axis=1).sum() for i in range(0, y.shape[1] - blk, hop)])
    ms = ms[ms > 0]
    l = -0.691 + 10 * np.log10(ms)
    g = ms[l > -70]
    if not len(g): return -np.inf
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = g[(-0.691 + 10 * np.log10(g)) > rel]
    return -0.691 + 10 * np.log10(g2.mean())

CENTERS = [25 * 2 ** (i / 3) for i in range(30)]  # 25Hz – 12.7kHz
def bands(x, sr):
    f, p = signal.welch(x.mean(axis=0), sr, nperseg=8192)
    out = []
    for c in CENTERS:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        m = (f >= lo) & (f < hi)
        out.append(np.trapezoid(p[m], f[m]) if m.any() else 0)
    return np.array(out)

def db(x): return 10 * np.log10(np.maximum(x, 1e-20))

RESULT = {}
for style in sys.argv[2:]:
    D = sys.argv[1]
    base = os.path.join(D, f"{style}__high_8")
    mix, sr = load(base + ".wav")
    dry, _ = load(base + "__dry.wav")
    stems = {}
    for t in ["drums", "bass", "keys", "keys2", "pad", "guitar"]:
        p = f"{base}_{t}.wav"
        if os.path.exists(p):
            x, _ = load(p)
            if np.abs(x).max() > 1e-4: stems[t] = x
    L = lufs(mix, sr)
    print(f"\n=== {style}  全混音 {L:.1f} LUFS  peak {np.abs(mix).max():.2f}")
    print("  各軌(相對全混音):", "  ".join(f"{t} {lufs(x, sr) - L:+.1f}" for t, x in stems.items()))
    B = bands(mix, sr); Bd = db(B)
    fc = np.array(CENTERS); sel = (fc >= 63) & (fc <= 8000)
    k, c0 = np.polyfit(np.log2(fc[sel]), Bd[sel], 1)
    dev = Bd - (k * np.log2(fc) + c0)
    print(f"  頻譜斜率 {k:+.1f} dB/八度(粉紅雜訊 = −3;用 1/3 八度頻帶能量算)")
    # 200Hz 以下用一個八度寬判斷:貝斯的基頻是離散的音(例如 C 調多半落在 65Hz 與 98Hz),
    # 1/3 八度那一格剛好沒有音就會像一個洞,其實低頻並不缺
    lowdev = []
    for lo, hi in [(40, 80), (80, 160)]:
        m = (fc >= lo) & (fc < hi)
        e = db(B[m].sum()) - db((10 ** ((k * np.log2(fc[m]) + c0) / 10)).sum())
        lowdev.append((f"{lo}–{hi}Hz", round(float(e), 1)))
    print("  低頻(一個八度寬)相對斜線:", lowdev)
    holes = [(round(c), round(d, 1)) for c, d, s in zip(CENTERS, dev, sel) if s and c >= 200 and abs(d) > 6]
    holes += [(n, d) for n, d in lowdev if abs(d) > 6]
    print("  偏離斜線 >6dB 的頻帶:", holes or "沒有")
    mid = (fc >= 2000) & (fc <= 5000)
    print(f"  2–5kHz 相對斜線 {dev[mid].mean():+.1f} dB")
    # 遮蔽
    SB = {t: bands(x, sr) for t, x in stems.items()}
    loud = Bd > Bd.max() - 30
    pairs = []
    names = list(SB)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            hit = [round(c) for n, c in enumerate(CENTERS) if loud[n] and SB[a][n] / B[n] >= 0.3 and SB[b][n] / B[n] >= 0.3]
            if hit: pairs.append(f"{a}×{b} {hit[0]}–{hit[-1]}Hz({len(hit)} 帶)")
    print("  互相蓋住:", pairs or "沒有")
    l, r = mix
    corr = np.corrcoef(l, r)[0, 1]
    # 低頻照慣例放中間(大鼓、貝斯是單聲道),全頻段的相關會被它拉高;寬度另外看 200Hz 以上
    sos = signal.butter(4, 200, "highpass", fs=sr, output="sos")
    hl, hr = signal.sosfilt(sos, l), signal.sosfilt(sos, r)
    corr_hi = np.corrcoef(hl, hr)[0, 1]
    mono = db(np.mean(((l + r) / 2) ** 2)) - db((np.mean(l ** 2) + np.mean(r ** 2)) / 2)
    wet = np.mean((mix - dry) ** 2)  # 同一組事件、同一個種子:相減就是殘響本身
    print(f"  左右相關 {corr:.2f}(200Hz 以上 {corr_hi:.2f})  單聲道損失 {mono:+.1f} dB  殘響/乾 {db(wet / np.mean(dry ** 2)):+.1f} dB")
    print("  乾的左右相關 {:.2f}".format(np.corrcoef(*dry)[0, 1]))
    RESULT[style] = {"lufs": L, "stems": {t: lufs(x, sr) - L for t, x in stems.items()}, "slope": k,
                     "dev": dict(zip([round(c) for c in CENTERS], [round(float(d), 1) for d in dev])),
                     "mid2to5": float(dev[mid].mean()), "corr": float(corr), "corrHi": float(corr_hi), "mono": float(mono),
                     "wet": float(db(wet / np.mean(dry ** 2)))}
import json
json.dump(RESULT, open(os.path.join(sys.argv[1], "analysis.json"), "w"), indent=1)
