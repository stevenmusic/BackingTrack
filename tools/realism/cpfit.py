#!/usr/bin/env python3
"""段落庫的 City Pop 進行,每一步根音走法在 12 首真歌裡出現在幾首(db/chords.json)。
一步 = 根音換了才算,整圈繞回開頭那一步也算。<3 首的走法標出來。
  python3 tools/realism/cpfit.py index.html"""
import json, re, sys, os, collections
D = json.load(open(os.path.join(os.path.dirname(__file__), 'db/chords.json')))
N = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
RN = ['I', '♭II', 'II', '♭III', 'III', 'IV', '♯IV', 'V', '♭VI', 'VI', '♭VII', 'VII']
ALIAS = {'C#': 'Db', 'D#': 'Eb', 'F#': 'Gb', 'G#': 'Ab', 'A#': 'Bb'}
def root(c):
    m = re.match(r'([A-G][#b]?)', c); r = m.group(1); return N.index(ALIAS.get(r, r))
songs = collections.defaultdict(set)
for s, v in D.items():
    seq = []
    for b in v['blocks']:
        for bar in b['bars']:
            for ch in bar.split():
                r = root(ch)
                if not seq or seq[-1] != r: seq.append(r)
    for a, b in zip(seq, seq[1:]): songs[(a, b)].add(s)
html = open(sys.argv[1]).read()
rows = []
for m in re.finditer(r'\{ text: "([^"]*)",\s*feel: "citypop"[^}]*role: "(\w+)"', html):
    text, role = m.groups()
    toks = [t for t in re.split(r'[\s\-|]+', text) if t and t not in ('/', '.')]
    rs = []
    for t in toks:
        r = root(t.split('/')[0])
        if not rs or rs[-1] != r: rs.append(r)
    if len(rs) > 1 and rs[0] == rs[-1]: rs = rs[:-1]
    steps = [(rs[i], rs[(i + 1) % len(rs)]) for i in range(len(rs))] if len(rs) > 1 else []
    n = [len(songs[s]) for s in steps]
    weak = [f'{RN[a]}→{RN[b]}({len(songs[(a, b)])})' for a, b in steps if len(songs[(a, b)]) < 3]
    rows.append((sum(n) / max(1, len(n)), min(n) if n else 0, role, text, weak))
for avg, mn, role, text, weak in sorted(rows, key=lambda r: (r[1], r[0])):
    print(f'平均 {avg:4.1f} 首 最少 {mn:2d}  {role:6s} {text:48s} {"弱:" + ", ".join(weak) if weak else ""}')
