"""從 Conner's Impulse Response Library(MIT 授權,github.com/itsmusician/IR-Library)做 styles/ir/ 的兩個殘響。
用法:git clone --filter=blob:none --no-checkout https://github.com/itsmusician/IR-Library /tmp/irsrc/IR-Library
      python3 tools/mix/make_ir.py /tmp/irsrc/IR-Library

room  = Arroyo House Living Room Mid A(真實房間,RT60 ≈ 0.6 秒,跟 Virtuosity 鼓的房間麥同一個衰減長度)
plate = Conner Plate I(真實的板式殘響),衰減照指數修到 RT60 約 1.8 秒(目標寫 2.2,Schroeder 量起來 1.8)(原本 3–4 秒,伴奏用太長)
兩個都:拿掉直達聲之前的空白與直達聲本身(送出式殘響只要反射)、轉 44.1kHz、能量正規化、16-bit
"""
import sys, os, subprocess, io, numpy as np, soundfile as sf
from scipy import signal

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/irsrc/IR-Library"
OUT = os.path.join(os.path.dirname(__file__), "../../styles/ir")
SR = 44100
FILES = {
    "room": ("Rooms/Residential/Arroyo House/Arroyo House Living Room Mid A.wav", None),
    "plate": ("Plates/Conner Plate I/Conner Plate I Sweeps/Conner Plate I 1s -42.wav", 2.2),
}

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
    rt0 = rt60(x.mean(1), SR)
    if target:                                       # 指數修衰減:每秒多掉 60/target − 60/rt0 dB
        t = np.arange(len(x)) / SR
        x *= (10 ** (-(60 / target - 60 / rt0) * t / 20))[:, None]
    rt1 = rt60(x.mean(1), SR)
    n = int(min(len(x), (rt1 * 1.25) * SR))          # 留到 −75dB 左右
    x = x[:n]; x[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))[:, None]
    x /= np.sqrt((x ** 2).sum() / 2)                 # 能量正規化(跟原本的 impulse() 一樣)
    x *= 0.25 / np.abs(x).max()                      # 存檔用的大小;播放端會再正規化
    sf.write(os.path.join(OUT, name + ".wav"), x, SR, subtype="PCM_16")
    print(f"{name}: {path.split('/')[-1]}  RT60 {rt0:.2f} → {rt1:.2f} s  {n / SR:.2f} s  L/R 相關 {np.corrcoef(x[:, 0], x[:, 1])[0, 1]:.2f}")
