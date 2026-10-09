"""從 Conner's Impulse Response Library(MIT 授權,github.com/itsmusician/IR-Library)做 styles/ir/ 的兩個殘響。
用法:git clone --filter=blob:none --no-checkout https://github.com/itsmusician/IR-Library /tmp/irsrc/IR-Library
      python3 tools/mix/make_ir.py /tmp/irsrc/IR-Library

room  = Arroyo House Living Room Mid A(真實房間,RT60 ≈ 0.6 秒,跟 Virtuosity 鼓的房間麥同一個衰減長度)
plate = Conner Plate I(真實的板式殘響)。原檔左右很不對稱(T20 左 1.77 秒、右 3.59 秒,能量差 3dB;板子兩個拾音點位置不同),
        不修的話殘響尾巴會飄到右邊。**每個聲道各自**照指數修衰減,迭代到兩聲道的 T20 都是 1.8 秒(±0.03),再把兩聲道能量拉平
兩個都:拿掉直達聲之前的空白與直達聲本身(送出式殘響只要反射)、轉 44.1kHz、**頻譜拉平**、能量正規化、16-bit。
頻譜拉平(2026-10-08,自動聆聽檢查抓到的):真的房間 / 板子有自己的共振——room 在 250Hz +4.6dB、8kHz +7dB,
plate 在 1kHz +12dB——送出去之後整個混音的 314–396Hz 與 1kHz 多了 3–5dB(悶、鼻音)。原本的雜訊 IR 是平的,沒有這個問題。
做法:每個聲道量 1/3 八度的能量,對平坦(白)的目標算出修正量(±15dB 封頂,150Hz 以下與 12kHz 以上不修),
做成線性相位 FIR 再轉最小相位(不會在反射之前多出預回音),跟 IR 卷積。反射的時間結構與衰減不變,只拿掉音色
"""
import sys, os, subprocess, io, numpy as np, soundfile as sf
from scipy import signal

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/irsrc/IR-Library"
OUT = os.path.join(os.path.dirname(__file__), "../../styles/ir")
SR = 44100
FILES = {
    "room": ("Rooms/Residential/Arroyo House/Arroyo House Living Room Mid A.wav", None),
    "plate": ("Plates/Conner Plate I/Conner Plate I Sweeps/Conner Plate I 1s -42.wav", 1.8),
}

def flatten(x, sr):
    """每個聲道的 1/3 八度頻譜拉平(最小相位 FIR,2048 階)"""
    cs = 1000 * 2 ** (np.arange(-13, 12) / 3)
    n = 1 << 16
    fr = np.fft.rfftfreq(n, 1 / sr)
    out = np.zeros_like(x)
    for c in range(x.shape[1]):
        X = np.abs(np.fft.rfft(x[:, c], n)) ** 2
        lv = np.array([10 * np.log10(X[(fr >= f / 2 ** (1 / 6)) & (fr < f * 2 ** (1 / 6))].mean() + 1e-30) for f in cs])
        ref = lv[(cs >= 300) & (cs <= 3000)].mean()
        corr = np.clip(ref - lv, -15, 15)
        corr[cs < 150] = corr[np.argmax(cs >= 150)]; corr[cs > 12000] = corr[np.argmax(cs > 12000) - 1]
        taps = 2049
        gf = np.interp(np.log2(np.maximum(np.linspace(0, sr / 2, 4097), 1)), np.log2(cs), corr)
        # minimum_phase(homomorphic)出來的大小是原本的平方根,所以這裡先給平方(dB 加倍)
        lin = signal.firwin2(taps, np.linspace(0, 1, 4097), 10 ** (gf / 10))
        mp = signal.minimum_phase(lin, method="homomorphic", n_fft=1 << 16)
        out[:, c] = signal.lfilter(mp, 1, x[:, c])
    return out


def rt60(x, sr):
    e = np.cumsum((x ** 2)[::-1])[::-1]; L = 10 * np.log10(e / e[0] + 1e-20)
    i5, i25 = np.argmax(L < -5), np.argmax(L < -25)
    p = np.polyfit(np.arange(i5, i25) / sr, L[i5:i25], 1); return -60 / p[0]

for name, (path, target) in FILES.items():
    raw = subprocess.run(["git", "-C", SRC, "show", "HEAD:" + path], capture_output=True, check=True).stdout
    x, sr = sf.read(io.BytesIO(raw), always_2d=True)
    x = x[:, :2]
    from math import gcd
    g = gcd(SR, sr); x = signal.resample_poly(x, SR // g, sr // g, axis=0)
    m = np.abs(x).sum(1); pk = int(np.argmax(m))
    x = x[pk + int(0.0025 * SR):]                    # 直達聲之後 2.5ms 開始(只留反射)
    x[: int(0.001 * SR)] *= np.linspace(0, 1, int(0.001 * SR))[:, None]
    rt0 = [rt60(x[:, c], SR) for c in range(2)]
    x = flatten(x, SR)                               # 先拉平音色,再修衰減(反過來的話拉平會把衰減弄歪)
    if target:                                       # 每個聲道指數修衰減,迭代到量起來等於目標(Schroeder 不是線性的)
        t = np.arange(len(x)) / SR
        for c in range(2):
            for _ in range(20):
                r = rt60(x[:, c], SR)
                if abs(r - target) < 0.03: break
                x[:, c] *= 10 ** (-(60 / target - 60 / r) * t / 20)
        x[:, 1] *= np.sqrt((x[:, 0] ** 2).sum() / (x[:, 1] ** 2).sum())   # 兩聲道能量拉平
    rt1 = max(rt60(x[:, c], SR) for c in range(2))
    n = int(min(len(x), (rt1 * 1.25) * SR))          # 留到 −75dB 左右
    x = x[:n]; x[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))[:, None]
    x /= np.sqrt((x ** 2).sum() / 2)                 # 能量正規化(跟原本的 impulse() 一樣)
    x *= 0.25 / np.abs(x).max()                      # 存檔用的大小;播放端會再正規化
    sf.write(os.path.join(OUT, name + ".wav"), x, SR, subtype="PCM_16")
    print(f"{name}: {path.split('/')[-1]}  T20 左/右 {rt0[0]:.2f}/{rt0[1]:.2f} → {rt60(x[:, 0], SR):.2f}/{rt60(x[:, 1], SR):.2f} s  "
          f"長 {n / SR:.2f} s  L/R 相關 {np.corrcoef(x[:, 0], x[:, 1])[0, 1]:.2f}  能量差 {10 * np.log10((x[:, 0] ** 2).sum() / (x[:, 1] ** 2).sum()):+.1f} dB")
