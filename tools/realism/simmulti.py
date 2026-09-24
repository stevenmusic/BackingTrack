#!/usr/bin/env python3
"""多測幾次:每一段錄音各自算跟三首參考曲的相似度(%),再給平均、標準差、最低最高。
尺跟 simcp.py 一樣:100% = 真歌之間、0% = 全合成版本。
  /tmp/abx/bin/python simmulti.py <分軌資料夾 glob> <標籤> [<glob> <標籤> ...]
參考曲與全合成那一組的嵌入**只算一次**、存在 /tmp/simcache.npz(一次要算半小時 CPU,
每個版本都重算的話消去法七組要跑三個多小時)。參考曲換了就把那個檔案刪掉"""
import sys, os, glob, json, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
jobs = list(zip(sys.argv[1::2], sys.argv[2::2]))
sys.argv = ['x', 'none']
exec(open(os.path.join(H, 'simcp.py')).read().split("GROUPS = {")[0])   # 拿 emb / windows / STEMS
refs = sorted(glob.glob('/tmp/refcp/sep/htdemucs/*')); syn = sorted(glob.glob('/tmp/synthcp/sep/htdemucs/syn_*'))
CACHE = '/tmp/simcache.npz'
cache = dict(np.load(CACHE, allow_pickle=True)) if os.path.exists(CACHE) else {}
BASE = {}
for name, stems in STEMS.items():
    if 'R_' + name in cache:
        R = cache['R_' + name].item(); S = cache['S_' + name].item()
    else:
        R = {os.path.basename(f): windows(f, stems) for f in refs}
        S = {os.path.basename(f): windows(f, stems, start=0) for f in syn}
        cache['R_' + name] = np.array(R, dtype=object); cache['S_' + name] = np.array(S, dtype=object)
        np.savez(CACHE, **cache)
    pool_all = np.array([v for l in R.values() for v in l])
    def sim(vs, excl=None, R=R, pool_all=pool_all):
        pool = np.array([v for k, l in R.items() if k != excl for v in l]) if excl else pool_all
        return float(np.mean([(pool @ v).max() for v in vs]))
    BASE[name] = (sim, np.mean([sim(v, k) for k, v in R.items()]), np.mean([sim(v) for v in S.values()]))
p = os.path.join(H, 'db', 'simmulti.json'); allr = json.load(open(p)) if os.path.exists(p) else {}
for pat, label in jobs:
    mine = sorted(glob.glob(pat))
    out = {'label': label, 'n': len(mine)}
    print('==', label, len(mine), flush=True)
    for name, stems in STEMS.items():
        sim, ref_self, s_syn = BASE[name]
        per = {os.path.basename(f): 100 * (sim(windows(f, stems)) - s_syn) / (ref_self - s_syn) for f in mine}
        v = np.array(list(per.values()))
        out[name] = {'平均%': round(float(v.mean()), 1), '標準差': round(float(v.std(ddof=1)), 1) if len(v) > 1 else 0,
                     '最低': round(float(v.min()), 1), '最高': round(float(v.max()), 1), '每段': {k: round(x, 1) for k, x in per.items()}}
        print(name, {k: out[name][k] for k in ('平均%', '標準差', '最低', '最高')}, flush=True)
    allr[label] = out; json.dump(allr, open(p, 'w'), ensure_ascii=False, indent=1)
