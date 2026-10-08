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

# ── Rhodes:jRhodes3c(散布取樣 CC BY-NC-SA 4.0,上架前要換),照原作者 sfz 的力度分界 ──
sfz = show("jr", "jRhodes3c-looped-flac-sfz/_jRhodes-stereo-looped.sfz")  # 立體聲版(原作者也有錄)
regions = re.split(r"<region>", sfz)[1:]
vel_edges, zones = [], []
for r in regions:
    kv = dict(re.findall(r"^(\w+)=(\S+)", r, re.M))
    lo, hi = int(kv.get("lovel", 1)), int(kv.get("hivel", 127))
    if [lo, hi] not in vel_edges:
        vel_edges.append([lo, hi])
    key = int(re.match(r"As_0*(\d+)__", kv["sample"]).group(1))
    zones.append({"key": key, "layer": vel_edges.index([lo, hi]), "files": [kv["sample"]]})
out["rhodes"] = {"src": src("sfzinstruments/jlearman.jRhodes3c", "master", "jRhodes3c-looped-flac-sfz/"),
                 "vel": vel_edges, "release": 0.3, "zones": zones,
                 "license": "jRhodes3c by Jeff Learman — samples CC BY-NC-SA 4.0 (non-commercial)"}

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

dst = os.path.join(os.path.dirname(__file__), "..", "..", "styles", "samples.json")
with open(dst, "w") as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
print({k: len(v.get("zones", v.get("pieces", []))) for k, v in out.items()}, os.path.getsize(dst), "bytes")
