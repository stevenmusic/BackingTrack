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
# 三拍(Groove MIDI 的 3-4、6-8 段落;資料少,所有曲風併在一起,變化機率再打五折)
vary34 = json.load(open(os.path.join(DS, "gmd_vary_34.json")))
vary68 = json.load(open(os.path.join(DS, "gmd_vary_68.json")))

# 風格 → Groove MIDI 的曲風(依樂手名單與唱片的節奏組來源;見 docs/SOURCES.md「律動資料」)
GENRES = {
    "pop": ["pop", "rock"], "mandopop_ballad": ["pop", "soul"], "jpop": ["rock", "pop"],
    "citypop": ["funk", "soul"], "kpop_dance": ["dance"], "kpop_ballad": ["pop", "soul"],
    "rnb_neosoul": ["soul", "hiphop"], "lofi": ["hiphop"], "reggaeton": ["dance"],
}
PIECES = ["kick", "snare", "hat", "openhat", "rim"]
VARY_SCALE = 0.35  # Groove MIDI 是即興錄音(每小節 55–80% 跟基本律動不同),伴奏要穩:取它的 35%
REF = {"kick": [0], "snare": [4, 12], "hat": [0, 4, 8, 12], "openhat": [2, 6, 10, 14], "rim": [4, 12]}

def drums_feel(V, gs, bar, ref, scale=1.0):
    """V:gmd_vary 的輸出;gs:要併的曲風;bar:一小節幾格;ref:每顆鼓拿來當基準的位置"""
    def merged(field, key):
        vals, w = [], []
        for g in gs:
            v = V[g][field].get(key)
            if v is None: continue
            vals.append(v[0] if isinstance(v, list) else v); w.append(V[g]["bars"])
        return sum(a * b for a, b in zip(vals, w)) / sum(w) if w else None
    wavg = lambda f: sum(V[g][f] * V[g]["bars"] for g in gs) / sum(V[g]["bars"] for g in gs)
    hatJ = merged("jitterSdMs", "hat")
    D = {"genres": gs, "drift": {"sdRel": round(wavg("driftSdMs") / hatJ, 3), "phi": round(wavg("driftLag1"), 3)},
         "jitterRel": {}, "sysRel": {}, "accent": {}, "add": {}, "drop": {}, "phrase": {}}
    for pc in PIECES:
        j = merged("jitterSdMs", pc)
        if j is None: continue
        D["jitterRel"][pc] = round(j / hatJ, 3)
        D["sysRel"][pc] = [round((merged("sysMs", f"{pc}:{i}") or 0) / hatJ, 3) for i in range(bar)]
        vel = [merged("vel", f"{pc}:{i}") for i in range(bar)]
        r = stt.mean([vel[i] for i in ref.get(pc, []) if i < bar and vel[i]] or [v for v in vel if v] or [1])
        D["accent"][pc] = [round(min(1.15, max(0.5, v / r)), 3) if v else 1 for v in vel]
        D["add"][pc] = [round(VARY_SCALE * scale * (merged("pAdd", f"{pc}:{i}") or 0), 4) for i in range(bar)]
        D["drop"][pc] = [round(VARY_SCALE * scale * (merged("pDrop", f"{pc}:{i}") or 0), 4) for i in range(bar)]
        ph = [merged("pVaryByPhraseBar", f"{pc}:{i}") or 0 for i in range(4)]
        m = stt.mean(ph) or 1
        D["phrase"][pc] = [round(x / m, 3) for x in ph]
    return D

REF34 = {"kick": [0], "snare": [4, 8], "hat": [0, 4, 8], "openhat": [2, 6, 10], "rim": [4, 8]}
REF68 = {"kick": [0], "snare": [6], "hat": [0, 6], "openhat": [4, 10], "rim": [6]}
METER_FEEL = {"3/4": drums_feel(vary34, ["3-4"], 12, REF34, 0.5), "6/8": drums_feel(vary68, ["6-8"], 12, REF68, 0.5)}

out = {"_source": "Groove MIDI Dataset (Magenta, CC BY 4.0); POP909 (MIT); GuitarSet (CC BY 4.0)", "styles": {}}
for style, gs in GENRES.items():
    out["styles"][style] = {"drums": drums_feel(vary, gs, 16, REF),
                            "meters": {m: {"drums": d} for m, d in METER_FEEL.items()}}

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
