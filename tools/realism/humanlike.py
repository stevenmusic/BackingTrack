#!/usr/bin/env python3
"""「像不像真人在彈」的尺(跟 MERT 相似度互補)。
MERT 相似度量的是「像不像這個曲風」——一首 AI 生成的 City Pop 量到鼓 224%、伴奏 83%,
它**分不出 AI 與真人**。這把尺改看演奏的語法(`groove.py` 量的):
每件樂器一拍四格的出現率、拍點與拍點之間的時間鬆緊比、貝斯與其他樂器每拍幾個起音、貝斯音長。
分數 = 跟三首真歌平均的距離,換算成 %:100% = 一首真歌跟另外兩首的距離(留一法),0% = AI 那首的距離。
  /tmp/abx/bin/python humanlike.py <groove.json 的標籤> ...   (標籤要先用 groove.py 量過)"""
import sys, json, os, numpy as np
H = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(H, 'db', 'groove.json')))
INST = ['大鼓', '小鼓', '鈸', '貝斯', '其他']
def feat(r):
    f = []
    for k in INST:
        f += [r[k][s]['出現率'] for s in '0123']
        sd = [r[k][s]['偏移SD'] for s in '0123']
        weak = [x for x in sd[1:] if x > 0]
        f.append((np.mean(weak) / sd[0] if weak and sd[0] else 1.0) / 2)       # 拍點間比拍點鬆多少(÷2 放到 0–1 附近)
    f += [r['貝斯每拍幾個起音'] / 2, r['其他每拍幾個起音'] / 2, (r['貝斯音長'] or 0)]
    return np.array(f)
real = {k: feat(v) for k, v in D['參考曲']['每首'].items()}
mean_real = np.mean(list(real.values()), 0)
dist = lambda f, ref: float(np.mean(np.abs(f - ref)))
loo = np.mean([dist(f, np.mean([g for k2, g in real.items() if k2 != k], 0)) for k, f in real.items()])
ai = dist(feat(D['AI生成']['平均']), mean_real)
print(f'真歌留一法距離 {loo:.3f}(=100%)  AI 距離 {ai:.3f}(=0%)')
for lab in sys.argv[1:]:
    d = dist(feat(D[lab]['平均']), mean_real)
    print(f'{lab}: 距離 {d:.3f} → 像真人 {100 * (ai - d) / (ai - loo):.0f}%')
