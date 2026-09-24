#!/usr/bin/env python3
"""Meta Audiobox Aesthetics 打分:CE(內容享受)/ CU(內容實用)/ PC(製作複雜度)/ PQ(製作品質),1–10。
用法:/tmp/abx/bin/python aes.py [--ckpt /tmp/abx_ckpt/checkpoint.pt] [額外音檔...]
結果寫到 db/aes.jsonl(clip id 或檔名 → 四個分數)。權重與 torch 不進 repo(見 README)。"""
import sys, os, json, glob, argparse
import torch, torchaudio
from audiobox_aesthetics.infer import AesPredictor
H = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--ckpt', default='/tmp/abx_ckpt/checkpoint.pt'); ap.add_argument('extra', nargs='*')
a = ap.parse_args()
p = AesPredictor(checkpoint_pth=a.ckpt, precision='bf16')
out = {}
path = os.path.join(H, 'db', 'aes.jsonl')
if os.path.exists(path):
    for l in open(path):
        r = json.loads(l); out[r['id']] = r
files = [(os.path.basename(f)[:-4], f) for f in sorted(glob.glob(os.path.join(H, 'clips', '*.wav')))]
files += [(os.path.basename(f), f) for f in a.extra]
for cid, f in files:
    if cid in out: continue
    wav, sr = torchaudio.load(f)
    r = p.forward([{'path': wav, 'sample_rate': sr}])[0]
    out[cid] = {'id': cid, **{k: round(v, 3) for k, v in r.items()}}
    print(cid, out[cid], flush=True)
with open(path, 'w') as fo:
    for r in out.values(): fo.write(json.dumps(r, ensure_ascii=False) + '\n')
