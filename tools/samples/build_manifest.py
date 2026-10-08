"""從各取樣庫的實際檔案列表產生 styles/samples.json(不照公式推檔名)。

用法:先把取樣庫 blobless clone 到 /tmp/smp(見 CLAUDE.md「驗收與量測」),再跑
    python3 tools/samples/build_manifest.py /tmp/smp
"""
import json, re, subprocess, sys, os

SMP = sys.argv[1] if len(sys.argv) > 1 else "/tmp/smp"
PC = {"c": 0, "db": 1, "c#": 1, "d": 2, "eb": 3, "d#": 3, "e": 4, "f": 5, "gb": 6, "f#": 6,
      "g": 7, "ab": 8, "g#": 8, "a": 9, "bb": 10, "a#": 10, "b": 11}


def tree(repo, path):
    out = subprocess.run(["git", "-C", os.path.join(SMP, repo), "ls-tree", "-r", "--name-only", "HEAD", path],
                         capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l]


def show(repo, path):
    return subprocess.run(["git", "-C", os.path.join(SMP, repo), "show", f"HEAD:{path}"],
                          capture_output=True, text=True, check=True).stdout


def note(name, octave_offset):
    m = re.fullmatch(r"([a-gA-G][#b]?)(-?\d)", name)
    return (int(m.group(2)) + octave_offset) * 12 + PC[m.group(1).lower()]


def parse_sfz(text):
    """最小的 sfz 解析:<global>/<master>/<group>/<region> 的 opcode 一層層繼承;音名用 c4 = 60"""
    text = re.sub(r"//[^\n]*", "", text.replace("\r", ""))
    regions, level = [], {"global": {}, "master": {}, "group": {}}
    cur = level["global"]  # 沒有標頭就寫進 global
    for tok in re.finditer(r"<(\w+)>|(\w+)=(.*?)(?=\s+\w+=|\s*<|\s*$)", text, re.S | re.M):
        if tok.group(1):
            h = tok.group(1)
            if h == "region":
                cur = {**level["global"], **level["master"], **level["group"]}; regions.append(cur)
            elif h in level:
                if h == "global": level = {"global": {}, "master": {}, "group": {}}
                if h == "master": level["master"], level["group"] = {}, {}
                if h == "group": level["group"] = {}
                cur = level[h]
        else:
            cur[tok.group(2)] = tok.group(3).strip()
    return regions

def sfz_key(v):
    if v is None: return None
    if re.fullmatch(r"-?\d+", v): return int(v)
    m = re.fullmatch(r"([a-gA-G][#b]?)(-?\d)", v)
    return (int(m.group(2)) + 1) * 12 + PC[m.group(1).lower()]

def sfz_zones(regions, prefix="", keep=lambda r: True):
    """region → zones(同一音、同一力度的 round robin 合在一起)與力度分界"""
    by, edges = {}, []
    for r in regions:
        if "sample" not in r or not keep(r): continue
        key = sfz_key(r.get("pitch_keycenter") or r.get("key") or r.get("lokey"))
        v = [int(r.get("lovel", 1)) or 1, int(r.get("hivel", 127))]
        if v not in edges: edges.append(v)
        by.setdefault((key, tuple(v)), []).append(prefix + r["sample"].replace("\\", "/"))
    edges.sort()
    zones = [{"key": k, "layer": edges.index(list(v)), "files": sorted(set(f))} for (k, v), f in sorted(by.items())]
    return zones, edges


def src(gh, branch, path):
    return [f"https://cdn.jsdelivr.net/gh/{gh}@{branch}/{path}",
            f"https://raw.githubusercontent.com/{gh}/{branch}/{path}"]


def vel_split(n):
    """n 層力度平均鋪在 1–127"""
    edges = [round(1 + i * 127 / n) for i in range(n + 1)]
    return [[edges[i], edges[i + 1] - 1 if i < n - 1 else 127] for i in range(n)]


out = {}

# ── 平台鋼琴:Salamander Grand Piano V3(CC BY 3.0),16 層全收,力度分界照原作者 sfz ──
sfz = show("SalamanderGrandPiano", "Data/notes.txt")  # 16 組力度分界寫在這裡,主 sfz 只是 #include
vel_edges = [[int(a), int(b)] for a, b in re.findall(r'vel_\d+\.txt" lovel=(\d+) hivel=(\d+)', sfz)][:16]
files = {p.split("/")[-1] for p in tree("SalamanderGrandPiano", "Samples")}
zones, rel = [], []
for f in sorted(files):
    m = re.fullmatch(r"([A-G]#?)(\d)v(\d+)\.flac", f)
    if m:
        zones.append({"key": note(m.group(1) + m.group(2), 1), "layer": int(m.group(3)) - 1, "files": [f]})
    m = re.fullmatch(r"rel(\d+)\.flac", f)
    if m:  # 放鍵的制音聲:hammer.txt 的 key = 20 + n、volume −37dB、amp_veltrack 82
        rel.append({"key": 20 + int(m.group(1)), "layer": 0, "files": [f]})
out["piano"] = {"src": src("sfzinstruments/SalamanderGrandPiano", "master", "Samples/"),
                "vel": vel_edges, "veltrack": 0.73, "release": 1.0, "zones": zones,
                "releaseNoise": {"db": -37, "veltrack": 0.82, "zones": sorted(rel, key=lambda z: z["key"])},
                "license": "CC BY 3.0 — Salamander Grand Piano V3 by Alexander Holm"}

# ── Rhodes:jRhodes3d 完整長度、立體聲、無交叉淡化版(取樣 CC BY-NC 4.0,用來做音樂是 CC0;免費網站可用)──
# 每 4 個白鍵錄一個音(相鄰最多 6 半音)× 5 層力度:找不到更密的免費 Rhodes,列為取樣密度標準的唯一例外(見 styles/README.md)
regs = parse_sfz(show("jr3d", "jRhodes3d-st-no-xfade.sfz"))
z, e = sfz_zones(regs)
out["rhodes"] = {"src": src("sfzinstruments/jlearman.jRhodes3d", "master", "jRhodes3d-st/"), "vel": e, "release": 0.3, "zones": z,
                 "license": "jRhodes3d by Jeff Learman — samples CC BY-NC 4.0, music made with it CC0"}

# ── 原聲鼓組:Virtuosity Drums(CC0),近麥克風 ──
vd = tree("virtuosity_drums", "Samples/mid")
def drum(prefix, pick=None):
    by = {}
    for p in vd:
        f = p.split("/")[-1]
        m = re.fullmatch(re.escape(prefix) + r"_vl(\d+)(?:_rr\d+)?\.flac", f)
        if m:
            by.setdefault(int(m.group(1)), []).append(p.replace("Samples/mid/", ""))
    vls = sorted(by)
    if pick:
        vls = [vls[round(i * (len(vls) - 1) / (pick - 1))] for i in range(pick)]
    return {"vel": vel_split(len(vls)), "layers": [sorted(by[v]) for v in vls]}
out["acoustic_kit"] = {
    "src": src("sfzinstruments/virtuosity_drums", "master", "Samples/mid/"),
    "license": "CC0 1.0 — Virtuosity Drums (Versilian Studios / Karoryfer)",
    "pieces": {
        "kick": drum("mid_kick_snon"), "snare": drum("mid_snare_center", 6),
        "rim": drum("mid_snare_crossstick", 4), "clap": drum("mid_snare_rimshot", 3),
        "hat": drum("mid_hh_closed"), "openhat": drum("mid_hh_open"),
        "crash": drum("mid_crash_crash"), "htom": drum("mid_htom_center", 4), "ltom": drum("mid_ltom_center", 4),
    },
}
# 房間麥:同一次演奏、同一個房間的另一對麥克風(Samples/room/,檔名 mid_ → room_,一對一)。
# 跟中距離麥同時播,鼓的空間來自真的房間,不靠人工殘響
room = set(tree("virtuosity_drums", "Samples/room"))
for P in out["acoustic_kit"]["pieces"].values():
    for files in P["layers"]:
        for f in files:
            r = "Samples/room/" + f.replace("/mid_", "/room_")
            assert r in room, f"房間麥缺檔:{r}"
out["acoustic_kit"]["room"] = {"src": src("sfzinstruments/virtuosity_drums", "master", "Samples/room/"), "from": "/mid_", "to": "/room_"}

# ── 電子鼓組:Dirt-Samples 的 808(實機取樣;授權待確認,見 docs/LICENSES.md)──
one = lambda f: {"vel": [[1, 127]], "layers": [[f]]}
out["electronic_kit"] = {
    "src": src("tidalcycles/Dirt-Samples", "master", ""),
    "license": "tidalcycles/Dirt-Samples 808 — license unstated",
    "pieces": {"kick": one("808bd/BD0025.WAV"), "snare": one("808sd/SD0010.WAV"), "clap": one("cp/HANDCLP0.wav"),
               "rim": one("808/RS.WAV"), "hat": one("808hc/HC00.WAV"), "openhat": one("808oh/OH10.WAV"),
               "crash": one("808cy/CY0050.WAV"), "htom": one("808mc/MC00.WAV"), "ltom": one("808lc/LC00.WAV")},
}

# ── 電貝斯:Black And Blue Basses darkblack(CC0),4 層力度 × round robin ──
dyn = ["p", "mp", "mf", "f"]
by = {}
for p in tree("bb", "Samples/darkblack/reg"):
    m = re.fullmatch(r"darkblack_([a-g]b?)(\d)_(p|mp|mf|f)_rr\d\.wav", p.split("/")[-1])
    by.setdefault((note(m.group(1) + m.group(2), 0), dyn.index(m.group(3))), []).append(p.split("/")[-1])
out["electric_bass"] = {"src": src("sfzinstruments/karoryfer.black-and-blue-basses", "main", "Samples/darkblack/reg/"),
                        "vel": vel_split(4), "release": 0.08,
                        "zones": [{"key": k, "layer": l, "files": sorted(v)} for (k, l), v in sorted(by.items())],
                        "license": "CC0 1.0 — Black And Blue Basses (Karoryfer)"}

# ── 弦樂合奏:VSCO-2-CE 小提琴 / 中提琴 / 大提琴聲部 sustain vibrato(CC0)──
zones = []
for sec, d in [("violin", "Strings/Violin Section/susVib"), ("viola", "Strings/Viola Section/susvib"),
               ("cello", "Strings/Cello Section/susvib")]:
    for p in tree("VSCO-2-CE", d):
        f = p.split("/")[-1]
        m = re.search(r"_([A-G]#?)(\d)_v(\d)", f)
        if not m or f.endswith("_2.wav"):
            continue
        zones.append({"key": note(m.group(1) + m.group(2), 2), "layer": 0 if m.group(3) == "1" else 1,
                      "section": sec, "files": [p]})
out["strings"] = {"src": src("sgossner/VSCO-2-CE", "master", ""), "vel": [[1, 80], [81, 127]],
                  "attack": 0.25, "release": 0.8, "zones": zones,
                  "license": "CC0 1.0 — VSCO-2 Community Edition (Versilian Studios)"}

# ── 乾淨電吉他(切音):Black And Green Guitars green staccato(CC0)──
by = {}
for p in tree("karoryfer.black-and-green-guitars", "Samples/green/stac"):
    m = re.fullmatch(r"staccato_([a-g]b?)(\d)_rr\d\.wav", p.split("/")[-1])
    by.setdefault(note(m.group(1) + m.group(2), 0), []).append(p.split("/")[-1])
out["clean_guitar"] = {"src": src("sfzinstruments/karoryfer.black-and-green-guitars", "main", "Samples/green/stac/"),
                       "vel": [[1, 127]], "release": 0.05,
                       "zones": [{"key": k, "layer": 0, "files": sorted(v)} for k, v in sorted(by.items())],
                       "license": "CC0 1.0 — Black And Green Guitars (Karoryfer)"}

# ── 下面是 2026-10-08 找齊的音色(Steven:「沒有找到的音色都要找到才行」)──
# 尼龍弦古典吉他:Philharmonia Orchestra 的取樣(CC BY-SA 3.0),用 ScrollScore 處理好的版本(guitar/classical/:
# 對齊起音、音準量好寫在 tune(音分)、響度對齊 −20 LUFS,力度交給 amp_veltrack 96)— Reggaeton 的「鋼琴或尼龍吉他」
# (FreePats 西班牙古典吉他:只有 1 層力度、Steven 在 ScrollScore 評過「缺音且錄音差」,不用)
SS = os.environ.get("SCROLLSCORE", "/home/user/stevenmusic/scrollscore")
pm = json.load(open(os.path.join(SS, "guitar/classical/manifest.json")))
out["nylon_guitar"] = {"src": src("stevenmusic/ScrollScore", "main", "guitar/classical/"), "vel": pm["velRanges"],
                       "veltrack": pm["ampVeltrack"] / 100, "release": 0.6,
                       "zones": sorted([{"key": v["root"], "layer": v["L"] - 1, "files": [k + ".flac"], "tune": round(-v["tune"] / 100, 3)}
                                        for k, v in pm["samples"].items()], key=lambda z: (z["key"], z["layer"])),
                       "license": "CC BY-SA 3.0 — Philharmonia Orchestra sound samples (processed in stevenmusic/ScrollScore)"}

# Slap 貝斯:Project16 Rickenbacker 4001 Slap1 + Slap2 Short(兩組錄音當 round robin;CC BY-NC-SA 3.0,作者另外允許用於音樂作品)
regs = parse_sfz(show("Project16Rickenbacker4001", "Slapped/Slap1_Short.sfz")) + parse_sfz(show("Project16Rickenbacker4001", "Slapped/Slap2_Short.sfz"))
z, e = sfz_zones(regs)
out["slap_bass"] = {"src": src("sfzinstruments/Project16Rickenbacker4001", "master", "Slapped/"), "vel": e, "release": 0.06,
                    "zones": z, "license": "CC BY-NC-SA 3.0 (modified: free for music productions) — Project16 Rickenbacker 4001 by Olivier Loiseau"}

# 低音提琴撥弦:Karoryfer Meatbass pizz(CC0)— Lo-fi 的「低沉 upright bass」
regs = parse_sfz(show("karoryfer.meatbass", "Programs/pizz_basic_map.sfz"))
z, e = sfz_zones(regs, keep=lambda r: "perc" not in r.get("sample", ""))
for zz in z: zz["files"] = [f.replace("../", "") for f in zz["files"]]
out["upright_bass"] = {"src": src("sfzinstruments/karoryfer.meatbass", "master", ""), "vel": e, "release": 0.15,
                       "zones": z, "license": "CC0 1.0 — Meatbass (Karoryfer, D. Smolken)"}

# 電吉他乾聲(DI):Karoryfer Emilyguitar(CC0)— J-pop high 的破音吉他:乾聲 → 音箱模擬(re-amp)
regs = parse_sfz(show("karoryfer.emilyguitar", "emily_clean.sfz"))
z, e = sfz_zones(regs, keep=lambda r: r.get("sample", "").startswith("notes"))
out["di_guitar"] = {"src": src("sfzinstruments/karoryfer.emilyguitar", "master", ""), "vel": e, "release": 0.12,
                    "zones": z, "license": "CC0 1.0 — Emilyguitar (Karoryfer, D. Smolken)"}

# 黑膠底噪:Ben Burnes「Micro Pack - Record Fuzzies / Classic Record Fuzz」(CC0)— Lo-fi
out["vinyl_noise"] = {"src": src("lavenderdotpet/CC0-Public-Domain-Sounds", "main", "Micro Pack - Record Fuzzies/"),
                      "loop": "Classic Record Fuzz.wav", "license": "CC0 1.0 — Ben Burnes (Abstraction), Record Fuzzies micro pack"}

dst = os.path.join(os.path.dirname(__file__), "..", "..", "styles", "samples.json")
with open(dst, "w") as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
print({k: len(v.get("zones", v.get("pieces", []))) for k, v in out.items()}, os.path.getsize(dst), "bytes")
