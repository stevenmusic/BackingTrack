"""從 analysis.json 算出各曲風的音量校正(dB),寫進 styles.json 的 mix 欄位。
用法:python3 tools/mix/solve_balance.py <analysis.json> [--write]
目標(相對;整體音量交給之後的母帶):
- 鼓 = 貝斯(兩者是骨架)
- 鍵盤 = 鼓(節奏型曲風);抒情曲(華語、K-pop 抒情)鍵盤 +2
- 弦樂鋪底 = 鍵盤 −3、第二鍵盤 = 鍵盤 −5、吉他切音 = 鍵盤 −7
目前的校正值會一起算進去(analysis 量的是加了舊校正的結果)
"""
import json, sys, re, os
A = json.load(open(sys.argv[1]))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
P = os.path.join(ROOT, "styles", "styles.json")
data = json.load(open(P))
BALLAD = {"mandopop_ballad", "kpop_ballad"}
REL = {"pad": -3, "keys2": -5, "guitar": -7}
new = {}
for style, r in A.items():
    s = r["stems"]
    st = next(x for x in data["styles"] if x["id"] == style)
    cur = st.get("mix", {})
    anchor = s["drums"]
    tgt = {"drums": anchor, "bass": anchor, "keys": anchor + (2 if style in BALLAD else 0)}
    for t, d in REL.items():
        if t in s: tgt[t] = tgt["keys"] + d
    off = {t: round(cur.get(t, 0) + tgt[t] - s[t], 1) for t in tgt if t in s}
    new[style] = off
    print(style, {t: f"{s[t]:+.1f}→{tgt[t]:+.1f}" for t in tgt if t in s}, "校正", off)
if "--write" in sys.argv:
    txt = open(P).read()
    for style, off in new.items():
        i = txt.index(f'"id": "{style}"')
        nxt = txt.find('"id": "', i + 1)
        j = txt.find('"instruments":', i)
        if j < 0 or (nxt > 0 and j > nxt):
            print(style, "是繼承的風格,沿用上層的 mix(要分開調就在它自己的區塊加 instruments)")
            continue
        block = txt[i:j]
        line = '"mix": ' + json.dumps(off) + ',\n      '
        if '"mix":' in block:
            k = txt.index('"mix":', i); e = txt.index('\n', k) + 1
            txt = txt[:k] + line.rstrip(' ') .rstrip('\n') + '\n' + txt[e:]
        else:
            txt = txt[:j] + line + txt[j:]
    open(P, "w").write(txt)
    json.loads(txt)
    print("寫入", P)
