#!/usr/bin/env python3
"""多測幾次:每一段錄音各自算跟三首參考曲的相似度(%),再給平均、標準差、最低最高。
尺跟 simcp.py 一樣:100% = 真歌之間、0% = 全合成版本。
  /tmp/abx/bin/python simmulti.py <分軌資料夾 glob> <標籤>"""
import sys, os, glob, json, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
pat, label = sys.argv[1], sys.argv[2]
sys.argv = ['x', 'none']
exec(open(os.path.join(H, 'simcp.py')).read().split("GROUPS = {")[0])   # 拿 emb / windows / STEMS
refs = sorted(glob.glob('/tmp/refcp/sep/htdemucs/*')); syn = sorted(glob.glob('/tmp/synthcp/sep/htdemucs/syn_*'))
mine = sorted(glob.glob(pat))
meta = {}
for d in os.path.dirname(os.path.dirname(os.path.dirname(pat))).split(','):
    pass
out = {'label': label, 'n': len(mine)}
for name, stems in STEMS.items():
    R = {os.path.basename(f): windows(f, stems) for f in refs}
    S = [windows(f, stems, start=0) for f in syn]
    pool_all = np.array([v for l in R.values() for v in l])
    def sim(vs, excl=None):
        pool = np.array([v for k, l in R.items() if k != excl for v in l]) if excl else pool_all
        return float(np.mean([(pool @ v).max() for v in vs]))
    ref_self = np.mean([sim(v, k) for k, v in R.items()]); s_syn = np.mean([sim(v) for v in S])
    per = {os.path.basename(f): 100 * (sim(windows(f, stems)) - s_syn) / (ref_self - s_syn) for f in mine}
    v = np.array(list(per.values()))
    out[name] = {'平均%': round(float(v.mean()), 1), '標準差': round(float(v.std(ddof=1)), 1) if len(v) > 1 else 0,
                 '最低': round(float(v.min()), 1), '最高': round(float(v.max()), 1), '每段': {k: round(x, 1) for k, x in per.items()}}
    print(name, {k: out[name][k] for k in ('平均%', '標準差', '最低', '最高')}, flush=True)
p = os.path.join(H, 'db', 'simmulti.json'); allr = json.load(open(p)) if os.path.exists(p) else {}
allr[label] = out; json.dump(allr, open(p, 'w'), ensure_ascii=False, indent=1)
