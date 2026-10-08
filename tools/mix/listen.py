"""自動「聽」:同一段的改之前 / 改之後,響度對齊後逐項檢查耳朵會抓到的問題,並畫頻譜圖給人(與 Claude)看。
用法:python3 tools/mix/listen.py <之前的資料夾> <之後的資料夾> [圖的輸出資料夾]
      (資料夾裡是 render_styles.mjs 算的 <style>__auto_16.wav)

逐項(全部先把兩邊都對齊到 −14 LUFS,比的是「同樣大聲時」聽起來的差別):
1. 壞掉的東西(一定要 0):削波、爆音(線性預測殘差裡孤立的尖峰,> 12σ 且 > −40dBFS:鼓的瞬態是一整串,爆音是一兩個取樣)、
   中途斷音(50ms 低於 −50dBFS)
2. 頻率:低頻 40–80 / 80–160Hz、悶(200–500Hz)、刺(2–5kHz,伴奏要讓給主旋律)相對整體斜線
3. 空間:左右相關(200Hz 以上)、單聲道損失、殘響尾巴長度(最後一個音之後掉 30dB 要多久)
4. 動態:響度範圍 LRA(EBU Tech 3342)、峰值/響度比 PLR、短時響度的起伏
5. 頻譜圖(對數頻率):兩邊並排存成 PNG,上排整段、下排放大 4 秒
"""
import sys, os, glob, numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import load, lufs, kweight

TARGET = -14.0


def norm(x, sr):
    return x * 10 ** ((TARGET - lufs(x, sr)) / 20)


def clicks(x, sr):
    """線性預測(16 階、20ms 一框)的殘差裡,超過 8σ 而且前後 3 個取樣都小於 3σ 的孤立尖峰"""
    n = 0
    for ch in x:
        hop = int(0.02 * sr)
        for i in range(0, len(ch) - hop, hop):
            f = ch[i:i + hop]
            if np.abs(f).max() < 1e-4: continue
            r = np.correlate(f, f, "full")[hop - 1:hop + 16]
            try: a = np.linalg.solve(np.array([[r[abs(p - q)] for q in range(16)] for p in range(16)]) + 1e-9 * np.eye(16), r[1:17])
            except np.linalg.LinAlgError: continue
            e = f[16:] - np.array([f[k - 16:k][::-1] @ a for k in range(16, hop)])
            s = e.std() + 1e-12
            # 聽得到的才算:尖峰本身要 > −40dBFS(安靜處 1e-4 的數值雜訊不算),而且 12σ 以上
            big = np.where((np.abs(e) > 12 * s) & (np.abs(e) > 0.01))[0]
            for k in big:
                nb = np.r_[e[max(0, k - 3):k], e[k + 1:k + 4]]
                if len(nb) and np.abs(nb).max() < 3 * s: n += 1
    return n


def dropouts(x, sr):
    m = x.mean(0); w = int(0.05 * sr)
    rms = np.sqrt(np.convolve(m ** 2, np.ones(w) / w, "valid")[::w])
    db = 20 * np.log10(rms + 1e-12)
    on = np.where(db > -40)[0]
    if not len(on): return 0
    # 跳過預備拍(只有 hi-hat 四下,中間本來就安靜;16 小節、速度 ≥ 70 的預備拍 ≤ 3.5 秒)
    mid = db[max(on[0], int(3.5 / 0.05)):on[-1]]
    return int((mid < -50).sum())


def bands(x, sr):
    """1/3 八度頻帶,對 63Hz–8kHz 擬合斜線;每一段取那幾個頻帶相對斜線的平均(dB)"""
    f, p = signal.welch(x.mean(0), sr, nperseg=16384)
    cs = 1000 * 2 ** (np.arange(-15, 11) / 3)
    lv = np.array([10 * np.log10(p[(f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))].sum() + 1e-20) for c in cs])
    fit = (cs >= 63) & (cs <= 8000)
    k, c0 = np.polyfit(np.log2(cs[fit]), lv[fit], 1)
    dev = lv - (k * np.log2(cs) + c0)
    rel = lambda lo, hi: float(dev[(cs >= lo) & (cs < hi)].mean())
    return {"40–80": rel(40, 80), "80–160": rel(80, 160), "悶200–500": rel(200, 500), "刺2–5k": rel(2000, 5000)}


def space(x, sr):
    sos = signal.butter(4, 200, "highpass", fs=sr, output="sos")
    l, r = signal.sosfilt(sos, x[0]), signal.sosfilt(sos, x[1])
    corr = np.corrcoef(l, r)[0, 1]
    mono = 10 * np.log10(np.mean(((x[0] + x[1]) / 2) ** 2) / ((np.mean(x[0] ** 2) + np.mean(x[1] ** 2)) / 2))
    # 尾巴:最後 3 秒是殘響收尾(render_styles 多算 3 秒),量從最後一個音的位置掉 30dB 要多久
    m = x.mean(0); w = int(0.01 * sr)
    env = 10 * np.log10(np.convolve(m ** 2, np.ones(w) / w, "same") + 1e-20)
    tail = env[-int(3.2 * sr):]
    i0 = int(np.argmax(tail > tail.max() - 6))   # 最後一個大聲的地方
    after = np.where(tail[i0:] < tail[i0] - 30)[0]
    t30 = after[0] / sr if len(after) else float("nan")
    return corr, mono, t30


def dynamics(x, sr):
    y = kweight(x, sr)
    blk, hop = int(3 * sr), int(0.1 * sr)   # EBU Tech 3342:3 秒短時響度
    st = np.array([-0.691 + 10 * np.log10(np.mean(y[:, i:i + blk] ** 2, axis=1).sum() + 1e-20) for i in range(0, y.shape[1] - blk, hop)])
    st = st[st > -70]; st = st[st > lufs(x, sr) - 20]
    lra = np.percentile(st, 95) - np.percentile(st, 10)
    up = signal.resample_poly(x, 4, 1, axis=-1)
    plr = 20 * np.log10(np.abs(up).max()) - lufs(x, sr)
    return lra, plr


def spectro(ax, x, sr, title):
    seg = 4096 if x.shape[1] > 10 * sr else 2048
    f, t, S = signal.stft(x.mean(0), sr, nperseg=seg, noverlap=seg * 7 // 8)
    S = 20 * np.log10(np.abs(S) + 1e-9)
    ax.pcolormesh(t, f, S, shading="auto", vmin=S.max() - 80, vmax=S.max(), cmap="magma")
    ax.set_yscale("symlog", linthresh=200); ax.set_ylim(30, 16000); ax.set_title(title, fontsize=9)


def main():
    A, B = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    rows = []
    for fb in sorted(glob.glob(os.path.join(B, "*__auto_16.wav"))):
        name = os.path.basename(fb); fa = os.path.join(A, name)
        if not os.path.exists(fa): continue
        style = name.split("__")[0]
        xa, sr = load(fa); xb, _ = load(fb)
        r = {}
        for tag, x in (("前", xa), ("後", xb)):
            raw = x
            x = norm(x, sr)
            r[tag] = {"削波": int((np.abs(raw) >= 0.999).sum()), "爆音": clicks(x, sr), "斷音": dropouts(x, sr),
                      **bands(x, sr), "corr": space(x, sr)[0], "mono": space(x, sr)[1], "尾巴": space(x, sr)[2],
                      "LRA": dynamics(x, sr)[0], "PLR": dynamics(x, sr)[1]}
        rows.append((style, r))
        if out:
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            # 上排整段;下排放大 4 秒(第 8–12 秒):融合看的是音與音之間——殘響有沒有把空隙接起來、尾巴糊不糊
            fig, axs = plt.subplots(2, 2, figsize=(12, 6.4), sharey=True)
            for col, (x, tag) in enumerate(((norm(xa, sr), "before"), (norm(xb, sr), "after"))):
                spectro(axs[0][col], x, sr, f"{style} {tag}")
                spectro(axs[1][col], x[:, int(8 * sr):int(12 * sr)], sr, f"{style} {tag} (8-12 s)")
            fig.tight_layout(); os.makedirs(out, exist_ok=True); fig.savefig(os.path.join(out, f"{style}.png"), dpi=80); plt.close(fig)
    keys = ["削波", "爆音", "斷音", "40–80", "80–160", "悶200–500", "刺2–5k", "corr", "mono", "尾巴", "LRA", "PLR"]
    print("(全部對齊到 −14 LUFS 之後比;頻帶是相對整體斜線的 dB)")
    print(f"{'曲風':16s}" + "".join(f"{k:>14s}" for k in keys))
    for style, r in rows:
        print(f"{style:16s}" + "".join(f"{r['前'][k]:>6.2f}→{r['後'][k]:<7.2f}" if isinstance(r['前'][k], float) else f"{r['前'][k]:>6d}→{r['後'][k]:<7d}" for k in keys))
    bad = [(s, k) for s, r in rows for k in ("削波", "爆音", "斷音") if r["後"][k] > r["前"][k]]
    print("\n壞掉的東西變多:", bad or "沒有")


if __name__ == "__main__":
    main()
