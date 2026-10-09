"""從 analysis.json 算出各曲風的音量校正(dB),寫進 styles.json 的 mix 欄位。
用法:python3 tools/mix/solve_balance.py <analysis.json> [--write]
目標:各軌相對鼓的響度 = tools/mix/balance_ref.json(它的 "ref" 寫的版本,現在是 5adb7c5;Steven 長期在聽、沒有說不好的那一版;
high 密度、跳過母帶鏈量的,由 tools/mix/make_balance_ref.sh 產生)。2026-10-08 改:以前的目標是「鼓 = 貝斯 = 鍵盤」,但 BS.1770 的 K-weighting 低頻算得輕,
響度一樣的貝斯聽起來偏弱(Steven:「bass 聲音很扁」),鍵盤拉高後 Rhodes 的 200–500Hz 讓整體變悶。
balance_ref 沒寫的軌照舊規則(鋪底 = 鍵盤 −3、第二鍵盤 = 鍵盤 −5、吉他 = 鍵盤 −7)
目前的校正值會一起算進去(analysis 量的是加了舊校正的結果)
"""
import json, sys, re, os
A = json.load(open(sys.argv[1]))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
P = os.path.join(ROOT, "styles", "styles.json")
data = json.load(open(P))
BALLAD = {"mandopop_ballad", "kpop_ballad"}
REF = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "balance_ref.json")))["styles"]
REL = {"pad": -3, "keys2": -5, "guitar": -7}
new = {}
for style, r in A.items():
    s = r["stems"]
    st = next(x for x in data["styles"] if x["id"] == style)
    cur = st.get("mix", {})
    anchor = s["drums"]
    R = REF.get(style, {})
    tgt = {"drums": anchor, "bass": anchor + R.get("bass", 0), "keys": anchor + R.get("keys", 2 if style in BALLAD else 0)}
    for t, d in REL.items():
        if t in s: tgt[t] = anchor + R[t] if t in R else tgt["keys"] + d
    off = {t: round(cur.get(t, 0) + tgt[t] - s[t], 1) for t in tgt if t in s}
    new[style] = off
    print(style, {t: f"{s[t]:+.1f}→{tgt[t]:+.1f}" for t in tgt if t in s}, "校正", off)
if "--write" in sys.argv:
    txt = open(P).read()
    for style, off in new.items():
        i = txt.index(f'\n      "id": "{style}"')
        nxt = txt.find('\n      "id": "', i + 1); nxt = nxt if nxt > 0 else len(txt)
        line = '      "mix": ' + json.dumps(off) + ',\n'
        m = re.compile(r'      "mix": .*,\n').search(txt, i, nxt)
        if m: txt = txt[:m.start()] + line + txt[m.end():]
        else:
            e = txt.index('\n', i + 1) + 1                 # id 那一行的下一行
            txt = txt[:e] + line + txt[e:]
    open(P, "w").write(txt)
    json.loads(txt)
    print("寫入", P)
