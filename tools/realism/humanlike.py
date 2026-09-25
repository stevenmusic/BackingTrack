#!/usr/bin/env python3
"""「像不像真人在彈」的尺(跟 MERT 相似度互補)。
MERT 相似度量的是「像不像這個曲風」——AI 生成的 City Pop 量到鼓 224%,它**分不出 AI 與真人**。
這把尺看演奏的語法(`groove.py` 量的):每件樂器一拍四格的出現率、拍點間比拍點鬆多少、
每拍幾個起音、貝斯音長。每一維先用「真歌之間的標準差」標準化(真歌本來就差很多的維度權重低)。
分數 = 跟真歌平均的距離換算成 %:100% = 真歌跟其他真歌的平均距離(留一法),0% = AI 歌的平均距離。
**先驗這把尺分不分得出真歌與 AI**(AUC,1 = 完全分得開、0.5 = 丟銅板),分不開的話分數沒有意義。
  /tmp/abx/bin/python humanlike.py <groove.json 的標籤> ...
AI 樣本:groove.json 裡標籤以「AI」開頭的每一首都算"""
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
        f.append(np.mean(weak) / sd[0] if weak and sd[0] else 1.0)
    f += [r['貝斯每拍幾個起音'], r['其他每拍幾個起音'], (r['貝斯音長'] or 0)]
    return np.array(f, dtype=float)
real = {k: feat(v) for k, v in D['參考曲']['每首'].items()}
ai = {f'{lab}/{k}': feat(v) for lab, d in D.items() if lab.startswith('AI') for k, v in d['每首'].items()}
R = np.array(list(real.values()))
scale = R.std(0) + 1e-3
def dist(f, ref): return float(np.mean(np.abs((f - ref) / scale)))
mean_real = R.mean(0)
real_d = {k: dist(f, np.mean([g for k2, g in real.items() if k2 != k], 0)) for k, f in real.items()}
ai_d = {k: dist(f, mean_real) for k, f in ai.items()}
rv, av = np.array(list(real_d.values())), np.array(list(ai_d.values()))
auc = float(np.mean([[1.0 if a > r else 0.5 if a == r else 0.0 for a in av] for r in rv]))
loo, aim = rv.mean(), av.mean()
print(f'真歌 {len(rv)} 首、AI {len(av)} 首。分得開嗎:AUC {auc:.2f}(1 = 完全分得開、0.5 = 丟銅板)')
print(f'真歌留一法平均距離 {loo:.3f}(=100%)  AI 平均距離 {aim:.3f}(=0%)')
print('  真歌各首:', {k: round(v, 3) for k, v in real_d.items()})
print('  AI 各首:', {k.split('/')[-1]: round(v, 3) for k, v in ai_d.items()})
for lab in sys.argv[1:]:
    d = dist(feat(D[lab]['平均']), mean_real)
    print(f'{lab}: 距離 {d:.3f} → 像真人 {100 * (aim - d) / (aim - loo):.0f}%')
