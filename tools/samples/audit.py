"""取樣夠不夠(Steven 2026-10-08:「只要取樣數量太少,就不要用」)。
標準:①相鄰取樣音高差 ≤ 4 半音(移調 ≤ ±2)②力度 ≥ 2 層,或 round robin ≥ 3 ③鼓、貝斯每層 round robin ≥ 2
(808 鼓機例外:那台機器本來每一下都一樣;黑膠底噪不是有音高的樂器)
用法:python3 tools/samples/audit.py [styles/samples.json]
"""
import json, sys
m = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "styles/samples.json"))
REPEAT = {"electric_bass", "slap_bass", "upright_bass"}
# 唯一的例外:jRhodes(找不到取樣更密的免費 Rhodes;Steven 2026-10-08 選「保留並換完整長度版」)
EXCEPT = {"rhodes": "找不到更密的免費 Rhodes,列為例外"}
ok_all = True
for name, I in m.items():
    if "zones" in I and I["zones"] and "key" in I["zones"][0]:
        keys = sorted({z["key"] for z in I["zones"]})
        gap = max(b - a for a, b in zip(keys, keys[1:])) if len(keys) > 1 else 99
        layers = len(I.get("vel", [[1, 127]]))
        rr = min(len(z["files"]) for z in I["zones"])
        bad = []
        if gap > 4: bad.append(f"音高間距 {gap} 半音")
        if layers < 2 and rr < 3: bad.append(f"力度 {layers} 層、round robin {rr}")
        if name in REPEAT and rr < 2: bad.append(f"round robin {rr}")
        if bad and name in EXCEPT: bad = [f"例外:{EXCEPT[name]}({'、'.join(bad)})"]; note_only = True
        else: note_only = False
        print(f"{name:15s} 音 {len(keys):3d}({keys[0]}–{keys[-1]})間距 ≤{gap:2d}  力度 {layers:2d} 層  rr ≥{rr}  {'✗ ' + '、'.join(bad) if bad else '✓'}")
        ok_all &= not bad or note_only
    elif "pieces" in I:
        for pc, P in I["pieces"].items():
            rr = min(len(l) for l in P["layers"])
            bad = name != "electronic_kit" and rr < 2 and len(P["layers"]) < 3
            print(f"{name + '.' + pc:15s} 力度 {len(P['layers'])} 層  rr ≥{rr}  {'✗' if bad else '✓'}")
            ok_all &= not bad
print("全部通過" if ok_all else "有不通過的")
