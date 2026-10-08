"""空間的數學設計:每一軌放到舞台上的哪個距離,一次解出殘響送出量(不是邊聽邊調)。
用法:python3 tools/mix/space.py [style ...] [--write]     (要先有 /tmp/smp 的取樣,見 CLAUDE.md)

1. 量「取樣本身帶了多少空間」:每一軌單獨算(跳過母帶鏈),不加任何空間,量直達/擴散比(DDR)。
   DDR 用左右聲道的相干性估:直達聲(單聲道、擺位)兩聲道完全相干 Γ=1,擴散的殘響兩聲道不相干 Γ≈0
   (我們的兩個 IR 左右相關 0.00 / 0.09),所以 DDR ≈ Γ / (1 − Γ)
   (Thiergart, Del Galdo & Habets 2012, "On the spatial coherence in mixtures of sound fields and its
   application to signal-to-diffuse ratio estimation", JASA 132(4);擴散場相干 = 0 的特例)。
   只看 500Hz–4kHz:低頻的相干性量不準,高頻不是距離感的主要來源。
2. 舞台 = 跟著鼓手的房間走:原聲鼓 = 中距離麥 + 房間麥(−6dB,同一次演奏的真房間),它量到的 DDR 就是「錨」A;
   其他軌寫成相對 A 的距離(styles.json 的 space.stage[軌].rel,dB,越大越近)與 pre-delay(越長越近)。
   電子鼓沒有房間麥,錨用原聲鼓各曲風的中位數,808 也放到同一個距離
3. 解(閉式解,不用試):殘響是我們加的,它的能量直接量得到,全部算擴散;取樣本身的那一份照相干性拆成直達 D 與擴散 R:
   DDR(k) = D / (R + k²·E_wet) = 目標 → k = sqrt((D/目標 − R) / E_wet);取樣本身已經比目標遠 → k = 0
4. 寫回 styles.json 每個風格的 "space": { "sends": {軌: {room, plate}}, "drumRoomDb": dB },
   再用真的送出量算一次(驗證;鼓組壓縮與飽和不是線性的,誤差 1dB 內算過)。
"""
import json, os, re, subprocess, sys, wave, numpy as np
from scipy import signal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
P = os.path.join(ROOT, "styles", "styles.json")
OUT = "/tmp/space"
BARS = "8"
# 每一軌 k = 1 時的送出(styles/player.mjs 的 BUS 預設值;room / plate 的比例照它)
BASE = {"drums": (0.45, 0), "kick": (0.12, 0), "bass": (0.05, 0), "keys": (0.3, 0.35), "keys2": (0.3, 0.35),
        "pad": (0.25, 0.6), "guitar": (0.35, 0.1)}


def load(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        return x.reshape(-1, 2).T, w.getframerate()


def parts(x, sr):
    """500Hz–4kHz 的能量拆成直達 D 與擴散 R(用相干性的大小:間隔式立體聲麥的時間差不會被當成殘響)"""
    f, sxy = signal.csd(x[0], x[1], sr, nperseg=4096)
    _, sxx = signal.welch(x[0], sr, nperseg=4096)
    _, syy = signal.welch(x[1], sr, nperseg=4096)
    b = (f >= 500) & (f <= 4000)
    w = np.sqrt(sxx[b] * syy[b]) + 1e-30
    g = np.sqrt((np.abs(sxy[b]) ** 2 / (sxx[b] * syy[b] + 1e-30) * w).sum() / w.sum())
    e = (sxx[b] + syy[b]).sum() / 2
    return g * e, (1 - g) * e, e


def db(d, r):
    return 10 * np.log10(max(d, 1e-30) / max(r, 1e-30))


def render(jobs):
    jobs = [j for j in jobs if not os.path.exists(os.path.join(OUT, re.sub(r"[:,/=+]", "_", j) + ".wav"))]
    if jobs:
        subprocess.run(["node", os.path.join(ROOT, "tools/samples/render_styles.mjs"), OUT, *jobs], check=True)


def wav(job):
    return load(os.path.join(OUT, re.sub(r"[:,/=+]", "_", job) + ".wav"))


def resolve(data, sid):
    st = next(s for s in data["styles"] if s["id"] == sid)
    if not st.get("inherits"): return st
    return {**resolve(data, st["inherits"]), **{k: v for k, v in st.items() if k != "inherits"}}


def tracks_of(data, sid):
    st = resolve(data, sid)
    return st, [t for t, v in st["tracks"].items() if v is not None]


def main():
    data = json.load(open(P))
    stage = data["space"]["stage"]
    ROOM_DB = data["space"].get("drumRoomDb", -6)
    ids = [s["id"] for s in data["styles"]]
    styles = [a for a in sys.argv[1:] if not a.startswith("--")] or ids
    os.makedirs(OUT, exist_ok=True)
    result, anchors, pending = {}, {}, []
    # 原聲鼓的先算(錨),電子鼓的最後算
    order = sorted(styles, key=lambda x: tracks_of(data, x)[0]["instruments"]["drums"] != "acoustic_kit")
    if any(tracks_of(data, x)[0]["instruments"]["drums"] != "acoustic_kit" for x in styles):
        order = [x for x in ids if tracks_of(data, x)[0]["instruments"]["drums"] == "acoustic_kit" and x not in order] + order
    for sid in order:
        st, tracks = tracks_of(data, sid)
        acoustic = st["instruments"]["drums"] == "acoustic_kit"
        on = "on=" + "+".join(t for t in tracks if (st["tracks"][t] or {}).get("optional"))
        fl = lambda *f: "/".join([*f] + ([on] if on != "on=" else []))
        J = lambda t, *f: f"{sid}::high:{BARS}:{t}:{fl(*f)}"
        jobs = [J(t, *f) for t in tracks for f in (("raw",), ("raw", "wet"))]
        if acoustic: jobs.append(J("drums", "raw", "dry"))
        render(jobs)
        sp = {"sends": {}}
        cur = st.get("space", {})
        if acoustic:                                   # 錨:中距離麥 + 房間麥 −6dB
            full, sr = wav(J("drums", "raw")); wet, _ = wav(J("drums", "raw", "wet")); close, _ = wav(J("drums", "raw", "dry"))
            room = (full - wet - close) * 10 ** ((ROOM_DB - cur.get("drumRoomDb", -12)) / 20)
            d, r, _ = parts(close + room, sr)
            A = anchors[sid] = db(d, r)
            sp["drumRoomDb"] = ROOM_DB
            sp["sends"]["drums"] = {"room": 0, "plate": 0}
            sp["sends"]["kick"] = {"room": 0, "plate": 0}
            dc, rc, _ = parts(close, sr)
            rows = [("drums", db(dc, rc), A, A, f"房間麥 {ROOM_DB:+d} dB(真房間),不送人工殘響")]
        else:
            A = float(np.median([anchors[x] for x in anchors]))
            rows = []
        for t in tracks:
            if t == "drums" and acoustic: continue
            full, sr = wav(J(t, "raw")); wet, _ = wav(J(t, "raw", "wet"))
            dry = full - wet
            d, r, _ = parts(dry, sr)
            sends0 = cur.get("sends", {}).get(t) or dict(zip(("room", "plate"), BASE[t]))
            k0 = (sends0["room"] / BASE[t][0]) if BASE[t][0] else 1.0
            ew = parts(wet, sr)[2] / max(k0, 1e-9) ** 2      # k = 1 時殘響的能量
            # 電子鼓(808)比真鼓近 3dB(鼓機本來就沒有房間,舞曲的鼓要緊);大鼓不送殘響(低頻留乾、留中間,跟貝斯同一條規則)
            tgt = A + stage["drums_electronic" if t == "drums" else t]["rel"]
            T = 10 ** (tgt / 10)
            k = float(np.sqrt(max(d / T - r, 0) / ew)) if ew > 0 else 0.0
            sp["sends"][t] = {"room": round(BASE[t][0] * k, 3), "plate": round(BASE[t][1] * k, 3)}
            if t == "drums": sp["sends"]["kick"] = {"room": 0, "plate": 0}
            rows.append((t, db(d, r), db(d, r + k * k * ew), tgt, f"送出 ×{k:.2f} → room {sp['sends'][t]['room']}, plate {sp['sends'][t]['plate']}"))
        if sid in styles: result[sid] = sp
        print(f"\n== {sid}(錨 A = {A:+.1f} dB,{'原聲鼓' if acoustic else '電子鼓,用原聲鼓的中位數'})")
        print(f"  {'軌':8s} {'取樣本身':>8s} {'解完':>8s} {'目標':>7s}")
        for t, a, b, c, txt in rows: print(f"  {t:8s} {a:+8.1f} {b:+8.1f} {c:+7.1f}   {txt}")
    if "--write" in sys.argv:
        txt = open(P).read()
        for sid, sp in result.items():
            i = txt.index(f'"id": "{sid}",\n')
            e = txt.index("\n", i) + 1
            nxt = txt.find('"id": "', e)
            block_end = nxt if nxt > 0 else len(txt)
            line = '      "space": ' + json.dumps(sp, ensure_ascii=False) + ",\n"
            m = re.compile(r'      "space": .*,\n').search(txt, e, block_end)
            txt = txt[:m.start()] + line + txt[m.end():] if m else txt[:e] + line + txt[e:]
        json.loads(txt)
        open(P, "w").write(txt)
        print("寫入", P)


if __name__ == "__main__":
    main()
