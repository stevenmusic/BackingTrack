#!/usr/bin/env python3
"""從真歌萃取「彈法庫」(RealTracks 的做法):Basic Pitch 轉出來的音符 → 半小節(2 拍、8 格十六分)的型。
  貝斯:每一下記 [格, 離這半小節根音幾個半音, 撐幾格, 力度(0–1)];
        半小節最後兩格、離**下一個半小節的根音** ±2 半音以內的,記成 [格, "n"+半音, …](接下一顆的經過音)
  吉他:同時起音(30ms 內)的一群當一下刷弦,記 [格, 撐幾格, 力度, 幾顆音]
小節頭:試 0–3 拍的相位,挑「貝斯換根音落在小節頭」最多的那個
  /tmp/abx/bin/python phrasegram.py  → db/phrases_citypop.json"""
import json, os, collections, numpy as np, soundfile as sf, librosa
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = '/tmp/ref6/sep/htdemucs_6s'
B = json.load(open('/tmp/bp/bass.json')); G = json.load(open('/tmp/bp/guitar.json'))
def beats_of(song, off, secs=120):
    sr = 22050
    y = 0
    for s in ('drums', 'bass'):
        x, r = sf.read(f'{SEP}/{song}/{s}.wav', always_2d=True, dtype='float32')
        x = x.mean(1)[int(off * r):int((off + secs) * r)]
        y = y + librosa.resample(x, orig_sr=r, target_sr=sr)
    tempo, bt = librosa.beat.beat_track(y=y, sr=sr, start_bpm=105, tightness=200, units='time')
    return np.array(bt)
def roots_per_half(notes, halves):
    out = []
    for a, b in halves:
        w = collections.Counter()
        for n in notes:
            ov = min(n[1], b) - max(n[0], a)
            if ov > 0: w[n[2] % 12] += ov * n[3] * (2.0 if abs(n[0] - a) < 0.08 else 1.0)
        out.append(w.most_common(1)[0][0] if w else None)
    return out
bassLib = collections.Counter(); bassSongs = collections.defaultdict(set); perSong = collections.defaultdict(list); rej = collections.Counter()
gtrLib = collections.Counter(); gtrSongs = collections.defaultdict(set)
for song in B:
    off = B[song]['offset']; bt = beats_of(song, off)
    if len(bt) < 16: continue
    spb = float(np.median(np.diff(bt)))
    bn = [n for n in B[song]['notes'] if 28 <= n[2] <= 60]
    if not bn: continue
    amp_med = np.median([n[3] for n in bn])
    # 相位:每 2 拍一個半小節,試 4 種小節頭
    best = None
    for ph in range(4):
        halves = [(bt[i], bt[i + 2]) for i in range(ph, len(bt) - 2, 2)]
        rts = roots_per_half(bn, halves)
        score = sum(1 for i in range(2, len(rts), 2) if rts[i] is not None and rts[i] != rts[i - 1]) \
              - sum(1 for i in range(1, len(rts), 2) if rts[i] is not None and rts[i] != rts[i - 1])
        if best is None or score > best[0]: best = (score, ph, halves, rts)
    _, ph, halves, rts = best
    for hi, (a, b) in enumerate(halves):
        r = rts[hi]; nxt = rts[hi + 1] if hi + 1 < len(rts) else None
        if r is None: continue
        g16 = (b - a) / 8
        ns = [n for n in bn if a - g16 * 0.5 <= n[0] < b - g16 * 0.5]
        if not ns or len(ns) > 8: rej['數量'] += 1; continue
        # 根音那一顆的實際音高:這半小節裡音級 = r 的最低那顆;沒有就用最低音
        rp = [n[2] for n in ns if n[2] % 12 == r]
        base = min(rp) if rp else min(n[2] for n in ns)
        pat = []
        ok = True
        for n in ns:
            sl = int(round((n[0] - a) / g16))
            if sl < 0 or sl > 7: ok = False; break
            dur = max(1, min(8, int(round((n[1] - n[0]) / g16))))
            vel = round(float(min(1.0, n[3] / (amp_med * 1.6))), 1)
            iv = n[2] - base
            if sl >= 6 and nxt is not None and nxt != r:
                d = ((n[2] % 12) - nxt) % 12
                d = d - 12 if d > 6 else d
                if abs(d) <= 2 and d != 0: pat.append([sl, 'n%+d' % d, dur, vel]); continue
            if iv < -12 or iv > 36: ok = False; break
            # Basic Pitch 常把貝斯的泛音(+19 = 八度加五度、+24、+17…)當成音:超過八度的一律往下折
            while iv > 12: iv -= 12
            pat.append([sl, iv, dur, vel])
        if not ok or not pat: rej['超出範圍'] += 1; continue
        # 同一格只留一顆(轉譜偶爾把一顆拆成兩顆),照格子排好
        seen = set(); pat = [p for p in sorted(pat, key=lambda q: q[0]) if not (p[0] in seen or seen.add(p[0]))]
        # 音長:Basic Pitch 對貝斯的收音抓得太早(量到 1–2 格;能量量的是 0.68 拍 ≈ 2.7 格)。
        # 撐到下一顆之前的 75%,最多 4 格
        for k, p in enumerate(pat):
            nxt = pat[k + 1][0] if k + 1 < len(pat) else 8
            p[2] = int(min(4, max(p[2], round(0.75 * (nxt - p[0])))))
        # 乾淨的才收:第一拍有音、非和弦音(不是 0/3/4/7/10/11/12 與 n±)不超過一顆
        odd = sum(1 for p in pat if not isinstance(p[1], str) and (p[1] % 12) not in (0, 3, 4, 7, 10, 11))
        if odd > 1: rej['太多非和弦音'] += 1; continue
        key = json.dumps(pat)
        bassLib[key] += 1; bassSongs[key].add(song); perSong[song].append(pat)
    # 吉他:同一個相位與半小節
    gn = [n for n in G.get(song, {}).get('notes', []) if 45 <= n[2] <= 88]
    if not gn: continue
    gamp = np.median([n[3] for n in gn])
    gn.sort()
    strums = []; i = 0
    while i < len(gn):
        j = i
        while j + 1 < len(gn) and gn[j + 1][0] - gn[i][0] < 0.03: j += 1
        grp = gn[i:j + 1]
        strums.append((grp[0][0], float(np.median([n[1] - n[0] for n in grp])), float(sum(n[3] for n in grp)), len(grp)))
        i = j + 1
    for a, b in halves:
        g16 = (b - a) / 8
        ss = [s for s in strums if a - g16 * 0.5 <= s[0] < b - g16 * 0.5]
        if not ss or len(ss) > 8: continue
        pat = []
        for s in ss:
            sl = int(round((s[0] - a) / g16))
            if sl < 0 or sl > 7: continue
            pat.append([sl, max(1, min(8, int(round(s[1] / g16)))), round(float(min(1.0, s[2] / (gamp * 4))), 1), min(4, s[3])])
        # 同一格只留一下
        seen = set(); pat = [p for p in pat if not (p[0] in seen or seen.add(p[0]))]
        if not pat: continue
        key = json.dumps([[p[0], p[1]] for p in pat])       # 型用「格 + 長度」比,力度另外平均
        gtrLib[key] += 1; gtrSongs[key].add(song)
def top(lib, songs, n, minsongs):
    rows = [(len(songs[k]), c, k) for k, c in lib.items() if len(songs[k]) >= minsongs]
    rows.sort(reverse=True)
    return [{'pat': json.loads(k), 'count': c, 'songs': s} for s, c, k in rows[:n]]
# 貝斯:真人幾乎不會彈兩次一模一樣,所以不要求重複——每首平均挑(最多 8 個、2–6 顆的、不同的型)
pick = []
for song, pats in perSong.items():
    uniq = []
    for pt in pats:
        if 2 <= len(pt) <= 6 and pt not in uniq: uniq.append(pt)
    step = max(1, len(uniq) // 8)
    pick += [{'pat': pt, 'song': song} for pt in uniq[::step][:8]]
print('擋掉的原因', dict(rej))
out = {'bass': pick, 'guitar': top(gtrLib, gtrSongs, 40, 2),
       'n_bass_halves': sum(bassLib.values()), 'n_gtr_halves': sum(gtrLib.values())}
json.dump(out, open(os.path.join(HERE, 'db', 'phrases_citypop.json'), 'w'), ensure_ascii=False, indent=1)
print('貝斯半小節', out['n_bass_halves'], '個,不同的型', len(bassLib), ';跨 ≥2 首的', len(out['bass']))
for r in out['bass'][:20]: print('  B', r['song'], r['pat'])
print('吉他半小節', out['n_gtr_halves'], '個,不同的型', len(gtrLib), ';跨 ≥2 首的', len(out['guitar']))
for r in out['guitar'][:15]: print('  G', r['songs'], '首', r['count'], '次', r['pat'])
