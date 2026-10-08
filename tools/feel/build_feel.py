"""把三個資料庫的統計整理成 styles/feel.json(引擎的人性化與每小節變化用)。
用法:python3 tools/feel/build_feel.py /tmp/ds
  需要先跑 gmd_vary.py、gmd_stats.py、pop909_stats.py、guitarset_stats.py(輸出放在同一個資料夾)

只從資料取「形狀」(哪個位置大聲、哪顆鼓偏前偏後、哪裡常加花、整團一起飄),
整體大小錨在規格的人性化 σ(styles.json 的 humanize.timingSigmaMs),理由見 styles/README.md。
"""
import json, os, sys, statistics as stt

DS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ds"
vary = json.load(open(os.path.join(DS, "gmd_vary.json")))
p909 = json.load(open(os.path.join(DS, "pop909_stats.json")))
gset = json.load(open(os.path.join(DS, "guitarset_stats.json")))
phr = json.load(open(os.path.join(DS, "pop909_phrase.json")))

# 風格 → Groove MIDI 的曲風(依樂手名單與唱片的節奏組來源;見 docs/SOURCES.md「律動資料」)
GENRES = {
    "pop": ["pop", "rock"], "mandopop_ballad": ["pop", "soul"], "jpop": ["rock", "pop"],
    "citypop": ["funk", "soul"], "kpop_dance": ["dance"], "kpop_ballad": ["pop", "soul"],
    "rnb_neosoul": ["soul", "hiphop"], "lofi": ["hiphop"], "reggaeton": ["dance"],
}
PIECES = ["kick", "snare", "hat", "openhat", "rim"]
VARY_SCALE = 0.35  # Groove MIDI 是即興錄音(每小節 55–80% 跟基本律動不同),伴奏要穩:取它的 35%
REF = {"kick": [0], "snare": [4, 12], "hat": [0, 4, 8, 12], "openhat": [2, 6, 10, 14], "rim": [4, 12]}

def merged(genres, field, key):
    vals, w = [], []
    for g in genres:
        v = vary[g][field].get(key)
        if v is None: continue
        vals.append(v[0] if isinstance(v, list) else v); w.append(vary[g]["bars"])
    return sum(a * b for a, b in zip(vals, w)) / sum(w) if w else None

def wavg(genres, field):
    """曲風層級的數字,依小節數加權"""
    return sum(vary[g][field] * vary[g]["bars"] for g in genres) / sum(vary[g]["bars"] for g in genres)

out = {"_source": "Groove MIDI Dataset (Magenta, CC BY 4.0); POP909 (MIT); GuitarSet (CC BY 4.0)", "styles": {}}
for style, gs in GENRES.items():
    hatJ = merged(gs, "jitterSdMs", "hat")
    D = {"genres": gs,
         "drift": {"sdRel": round(wavg(gs, "driftSdMs") / hatJ, 3), "phi": round(wavg(gs, "driftLag1"), 3)},
         "jitterRel": {}, "sysRel": {}, "accent": {}, "add": {}, "drop": {}, "phrase": {}}
    for pc in PIECES:
        j = merged(gs, "jitterSdMs", pc)
        if j is None: continue
        D["jitterRel"][pc] = round(j / hatJ, 3)
        sys_ = [merged(gs, "sysMs", f"{pc}:{i}") for i in range(16)]
        D["sysRel"][pc] = [round((x or 0) / hatJ, 3) for x in sys_]
        vel = [merged(gs, "vel", f"{pc}:{i}") for i in range(16)]
        ref = stt.mean([vel[i] for i in REF[pc] if vel[i]] or [v for v in vel if v] or [1])
        D["accent"][pc] = [round(min(1.15, max(0.5, v / ref)), 3) if v else 1 for v in vel]
        D["add"][pc] = [round(VARY_SCALE * (merged(gs, "pAdd", f"{pc}:{i}") or 0), 4) for i in range(16)]
        D["drop"][pc] = [round(VARY_SCALE * (merged(gs, "pDrop", f"{pc}:{i}") or 0), 4) for i in range(16)]
        ph = [merged(gs, "pVaryByPhraseBar", f"{pc}:{i}") or 0 for i in range(4)]
        m = stt.mean(ph) or 1
        D["phrase"][pc] = [round(x / m, 3) for x in ph]
    out["styles"][style] = {"drums": D}

# 鍵盤:POP909 的時間是量化過的(量到和弦內時間差 0ms、抖動 0.29ms),不能當彈法的時間來源,只取力度的位置強弱。
# 和弦各音的先後改照文獻:Goebl 2001(JASA 110(1),"Melody lead in piano performance"):
# 真人彈和弦各音不同時落下,頂音通常最先、最大聲,先後與力度差有關。伴奏取保守值:頂音先、全距約 10ms、頂音 +6
vp = p909["velByPos"]; ref = stt.mean(vp[i] for i in (0, 4, 8, 12))
KEYS = {"spreadMs": {"median": 10}, "lowFirstShare": 0.0, "topVel": 6,
        "accent": [round(min(1.15, max(0.6, v / ref)), 3) for v in vp],
        "sysRel": [0] * 16, "anticipation": phr["anticipation"],
        "_note": "accent: POP909 velocity by 16th position; timing follows the drummer (POP909 timing is quantized); chord spread per Goebl 2001"}
# 樂句裡第幾小節的力度:POP909 量到 0.998–1.002(沒有差別),所以不做樂句漸強
# 吉他(GuitarSet Funk:City Pop 的切音)
f = gset["Funk"]
GTR = {"spreadMs": f["strumSpreadMs"], "downShare": f["downShare"], "durCells": f["durCells"]["median"]}
for s in out["styles"].values():
    s["keys"] = KEYS
    s["guitar"] = GTR
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "styles", "feel.json")
json.dump(out, open(dst, "w"), ensure_ascii=False, separators=(",", ":"))
print("wrote", dst, os.path.getsize(dst))
