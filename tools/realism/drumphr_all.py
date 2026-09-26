#!/usr/bin/env python3
"""Groove MIDI Dataset(Google Magenta,CC BY 4.0)→ Pop / Funk / Blues / Swing 的真人鼓片段庫。
City Pop 那一份是 drumphr.py 做的(另外照 12 首真歌的落點分布挑過),這支做其餘 4/4 的曲風。

每一小節存成 [[拍位置×1000(整數,含微時值), 鼓件, 力度0–127], …],**不量化、力度照原樣**。
連續通過條件的小節整串保留(同一個鼓手一路打下去的呼吸);過門從 fill 檔挑。
  1. 下載 https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip 解到 /tmp/ds/groove
  2. python3 drumphr_all.py            → db/drums_<feel>.json
  3. python3 drumphr_all.py --embed    → 把結果寫進 index.html 的 DRUM_PHR(City Pop 那份不動)
"""
import csv, json, os, sys, collections
import pretty_midi
GMD = '/tmp/ds/groove'
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MAP = {36: 'k', 38: 's', 40: 's', 37: 'x', 42: 'h', 22: 'h', 44: 'p', 46: 'o', 26: 'o',
       43: 'l', 58: 'l', 45: 't', 47: 't', 48: 't', 50: 't', 49: 'c', 55: 'c', 57: 'c', 52: 'c',
       51: 'r', 59: 'r', 53: 'r'}

def bars_of(path, bpm):
    pm = pretty_midi.PrettyMIDI(path)
    spb = 60 / bpm
    hits = sorted((n.start / spb, MAP[n.pitch], n.velocity)
                  for ins in pm.instruments for n in ins.notes if n.pitch in MAP)
    if not hits: return []
    nb = int(hits[-1][0] // 4) + 1
    bars = [[] for _ in range(nb)]
    for b, p, v in hits:
        i = int((b + 0.12) // 4)          # 小節線前 0.12 拍以內搶進來的算下一小節(拍位置是負的)
        if 0 <= i < nb: bars[i].append((round(b - i * 4, 3), p, v))
    return bars

def near(pos, t, w=0.12): return abs(pos - t) <= w
def cnt(bar, ps): return [h for h in bar if h[1] in ps]
def backbeat(bar):
    s = [h for h in bar if h[1] == 's' and h[2] >= 55]
    return any(near(h[0], 1) for h in s) and any(near(h[0], 3) for h in s)
def kick_one(bar): return any(near(h[0], 0) for h in cnt(bar, 'k'))
def crash_ok(bar): return all(near(h[0], 0) for h in cnt(bar, 'c'))

# 每個曲風:挑哪些風格的檔、速度範圍、一小節要長怎樣。條件照 CLAUDE.md「鼓」那節的打法
def ok_pop(b):       # 八分 hi-hat、backbeat、大鼓踩 1
    return (kick_one(b) and backbeat(b) and 1 <= len(cnt(b, 'k')) <= 5 and 6 <= len(cnt(b, 'ho')) <= 10
            and not cnt(b, 'tl') and len(cnt(b, 'r')) <= 2 and crash_ok(b))
def ok_funk(b):      # 十六分 hi-hat、backbeat、大鼓切分
    return (kick_one(b) and backbeat(b) and 2 <= len(cnt(b, 'k')) <= 7 and 10 <= len(cnt(b, 'ho')) <= 18
            and not cnt(b, 'tl') and len(cnt(b, 'r')) <= 2 and crash_ok(b))
def ok_blues(b):     # shuffle:backbeat、hi-hat 或 ride 走三連音的八分
    return (backbeat(b) and 1 <= len(cnt(b, 'k')) <= 6 and 5 <= len(cnt(b, 'hor')) <= 14
            and not cnt(b, 'tl') and crash_ok(b))
def ok_swing(b):     # ride 在走、沒有 2/4 的 backbeat 小鼓(爵士的小鼓在 comping)
    s = [h for h in b if h[1] == 's' and h[2] >= 70]
    return (len(cnt(b, 'r')) + len(cnt(b, 'h')) >= 4 and len(cnt(b, 'r')) >= 2 and len(s) <= 3 and not (any(near(h[0], 1) for h in s) and any(near(h[0], 3) for h in s))
            and len(cnt(b, 'k')) <= 5 and not cnt(b, 'tl') and crash_ok(b))

FEELS = {
    'straight': dict(styles=('pop', 'rock', 'soul', 'country'), bpm=(75, 135), ok=ok_pop, excl=('rock/indie', 'rock/prog')),
    'funk':     dict(styles=('funk', 'soul', 'hiphop'), bpm=(80, 125), ok=ok_funk, excl=()),
    'blues':    dict(styles=('blues', 'neworleans', 'rock', 'soul', 'jazz'), bpm=(60, 140), ok=ok_blues, excl=(), shuffle=True, minrun=2),
    'swing':    dict(styles=('jazz',), bpm=(90, 240), ok=ok_swing, excl=('jazz/funk', 'jazz/fusion', 'jazz/linear', 'jazz/march', 'jazz/klezmer'), minrun=2),
}
MAX_RUNS, MAX_RUN_BARS = 16, 16

def swung(bar):
    """八分的後半落在拍的 0.6–0.72 之間(三連音)才算 shuffle / swing"""
    offs = [h[0] % 1 for h in bar if h[1] in 'hor' and 0.3 < h[0] % 1 < 0.9]
    return len(offs) >= 2 and sum(0.58 <= o <= 0.74 for o in offs) >= 0.7 * len(offs)

def build(key, cfg, rows):
    runs, fills = [], []
    for x in rows:
        st = x['style']
        if x['time_signature'] != '4-4' or st.split('/')[0] not in cfg['styles'] or st in cfg['excl']: continue
        bpm = int(x['bpm'])
        if not cfg['bpm'][0] <= bpm <= cfg['bpm'][1]: continue
        bars = bars_of(f"{GMD}/{x['midi_filename']}", bpm)
        need_swing = cfg.get('shuffle') or key == 'swing'
        good = lambda b: cfg['ok'](b) and (not need_swing or swung(b)) and (need_swing or not swung(b))
        if x['beat_type'] == 'beat':
            cur = []
            for b in bars + [None]:
                if b is not None and good(b): cur.append(b); continue
                if len(cur) >= cfg.get('minrun', 4): runs.append({'drummer': x['drummer'], 'style': st, 'bpm': bpm, 'bars': cur[:MAX_RUN_BARS]})
                cur = []
        else:
            for b in bars:
                dense = [h for h in b if h[1] in 'stl' and h[0] >= 2]
                head = [h for h in b if h[0] < 2]
                if len(dense) >= 4 and head and len(b) <= 40 and (not need_swing or swung(head + b[:0]) or key == 'swing'):
                    fills.append({'style': st, 'bar': b}); break
    # 挑:長的優先,但每個鼓手最多 5 串,讓音色與手感有變化
    runs.sort(key=lambda r: -len(r['bars']))
    per, pick = collections.Counter(), []
    for r in runs:
        if per[r['drummer']] >= 5: continue
        per[r['drummer']] += 1; pick.append(r)
        if len(pick) >= MAX_RUNS: break
    return pick, fills[:12]

def enc(b): return [[int(round(p * 1000)), c, v] for p, c, v in b]

def main():
    rows = list(csv.DictReader(open(f'{GMD}/info.csv')))
    for key, cfg in FEELS.items():
        runs, fills = build(key, cfg, rows)
        nb = sum(len(r['bars']) for r in runs)
        print(f"{key}: {len(runs)} 串 {nb} 小節、過門 {len(fills)};鼓手 {sorted(set(r['drummer'] for r in runs))};"
              f"風格 {collections.Counter(r['style'] for r in runs).most_common(4)}")
        out = {'runs': [[enc(b) for b in r['bars']] for r in runs], 'fills': [enc(f['bar']) for f in fills],
               'meta': [{'drummer': r['drummer'], 'style': r['style'], 'bpm': r['bpm']} for r in runs],
               'license': 'Groove MIDI Dataset, Google LLC, CC BY 4.0'}
        json.dump(out, open(os.path.join(HERE, 'db', f'drums_{key}.json'), 'w'))

def embed():
    p = os.path.join(ROOT, 'index.html')
    lines = open(p, encoding='utf-8').read().split('\n')
    i = next(k for k, l in enumerate(lines) if l.startswith('const DRUM_PHR = {'))
    dec = json.JSONDecoder()
    s = lines[i]
    city, _ = dec.raw_decode(s[s.index('citypop:') + 8:].lstrip())
    parts = ['citypop: ' + json.dumps(city, separators=(',', ':'))]
    for key in FEELS:
        d = json.load(open(os.path.join(HERE, 'db', f'drums_{key}.json')))
        if d['runs']: parts.append(f"{key}: " + json.dumps({'runs': d['runs'], 'fills': d['fills']}, separators=(',', ':')))
    lines[i] = 'const DRUM_PHR = { ' + ', '.join(parts) + ' };'
    open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    print('寫進 index.html:', len(lines[i]), 'bytes')

if __name__ == '__main__':
    embed() if '--embed' in sys.argv else main()
