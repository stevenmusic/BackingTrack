#!/usr/bin/env python3
"""12 首真 City Pop 的和弦統計(讀 db/chords.json,已轉成 C 大調)。
自動辨識不是採譜:只信根音與「重複出現的段落」,性質(7 / maj7)只當傾向看。
  python3 tools/realism/chordstats.py"""
import json, collections, re, os
D = json.load(open(os.path.join(os.path.dirname(__file__), 'db/chords.json')))
N = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
RN = ['I', '♭II', 'II', '♭III', 'III', 'IV', '♯IV', 'V', '♭VI', 'VI', '♭VII', 'VII']
def split(c):
    m = re.match(r'([A-G]b?)(.*)', c); return N.index(m.group(1)), m.group(2)
def rn(c):
    r, q = split(c); base = RN[r]
    if q.startswith('m') and not q.startswith('maj'): base = base.lower()
    return base + {'': '', 'm': '', '7': '7', 'maj7': 'M7', 'm7': '7', 'm7b5': 'ø7', '7sus4': '7sus4'}.get(q, q)
deg = collections.Counter(); qual = collections.defaultdict(collections.Counter)
big = collections.Counter(); two = [0, 0]; songsWith = collections.defaultdict(set)
blocksAll = []
for song, v in D.items():
    seq = []
    for b in v['blocks']:
        for bar in b['bars']:
            cs = bar.split(); two[0] += 1; two[1] += len(cs) > 1
            for c in cs:
                if not seq or seq[-1] != c: seq.append(c)
        blocksAll.append((song, b['role'], tuple(rn(c) for bar in b['bars'] for c in [bar.split()[0]])))
    for c in seq:
        r, q = split(c); deg[r] += 1; qual[r][q] += 1; songsWith[r].add(song)
    for a, b2 in zip(seq, seq[1:]):
        ra, rb = split(a)[0], split(b2)[0]
        if ra != rb: big[(ra, rb)] += 1
tot = sum(deg.values())
print('== 級數出現比例(12 首,和弦換了才算一次)')
for r, n in deg.most_common():
    qs = ', '.join(f'{rn(N[r] + q)} {c}' for q, c in qual[r].most_common(3))
    print(f'  {RN[r]:5s} {100 * n / tot:5.1f}%  出現在 {len(songsWith[r]):2d}/12 首   常見:{qs}')
print(f'\n== 和弦節奏:一小節兩顆的比例 {100 * two[1] / two[0]:.0f}%')
print('\n== 根音怎麼走(最常見的 20 種,不看性質)')
for (a, b2), n in big.most_common(20):
    iv = (b2 - a) % 12
    mv = {5: '往上四度(=下五度,屬→主的方向)', 7: '往上五度', 2: '上二度', 10: '下二度', 1: '上半音', 11: '下半音', 3: '上小三度', 9: '下小三度', 4: '上大三度', 8: '下大三度'}.get(iv, '三全音')
    print(f'  {RN[a]:4s} → {RN[b2]:4s} {n:3d}   {mv}')
print('\n== 每首歌裡重複最多次的四小節(只看每小節第一顆的級數;重複 = 比較可信)')
for song in D:
    c = collections.Counter((role, blk) for s, role, blk in blocksAll if s == song)
    rep = [(n, role, blk) for (role, blk), n in c.items() if n >= 2]
    rep.sort(key=lambda x: -x[0])
    print(f'  {song} ({D[song]["key"]} 調, {D[song]["bpm"]} BPM)')
    for n, role, blk in rep[:3]: print(f'     ×{n} {role}: ' + ' - '.join(blk))
    if not rep: print('     (沒有完全重複的四小節)')

# ── 一小節兩顆是真的換和弦,還是同一顆根音被猜成兩種性質(雜訊)?
diffroot = sameroot = 0; pair = collections.Counter(); pairSongs = collections.defaultdict(set)
for song, v in D.items():
    for b in v['blocks']:
        for bar in b['bars']:
            cs = bar.split()
            if len(cs) < 2: continue
            if split(cs[0])[0] == split(cs[1])[0]: sameroot += 1; continue
            diffroot += 1; k = rn(cs[0]) + ' ' + rn(cs[1]); pair[k] += 1; pairSongs[k].add(song)
tb = two[0]
print(f'\n== 一小節兩顆:根音不同(真的換和弦)佔全部小節 {100 * diffroot / tb:.0f}%、根音相同(多半是性質猜錯){100 * sameroot / tb:.0f}%')
print('   最常見的「一小節兩顆」(至少 4 首歌都有):')
for k, n in sorted(pair.items(), key=lambda x: (-len(pairSongs[x[0]]), -x[1])):
    if len(pairSongs[k]) < 4: break
    print(f'     {k:14s} {n:3d} 次、{len(pairSongs[k])} 首')

# ── 跨歌曲都出現的連續和弦(只看根音,換了才算;至少 5 首)
def ngrams(n):
    c = collections.defaultdict(set); cnt = collections.Counter()
    for song, v in D.items():
        seq = []
        for b in v['blocks']:
            for bar in b['bars']:
                for ch in bar.split():
                    r = split(ch)[0]
                    if not seq or seq[-1] != r: seq.append(r)
        for i in range(len(seq) - n + 1):
            g = tuple(seq[i:i + n]); c[g].add(song); cnt[g] += 1
    return c, cnt
for n in (3, 4):
    c, cnt = ngrams(n)
    print(f'\n== 連續 {n} 顆根音,出現在最多首歌的(真歌共用的「句型」)')
    for g, ss in sorted(c.items(), key=lambda x: (-len(x[1]), -cnt[x[0]]))[:14]:
        print(f'     {" → ".join(RN[r] for r in g):28s} {len(ss):2d} 首、{cnt[g]:3d} 次')
