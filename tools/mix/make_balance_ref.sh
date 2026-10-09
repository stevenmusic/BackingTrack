#!/bin/bash
# 產生 tools/mix/balance_ref.json:參考版本(預設 main 5adb7c5,Steven 長期在聽的那一版)各軌相對鼓的響度。
# 量法跟 tools/mix/analyze.py 一樣:high 密度 8 小節、跳過母帶鏈(raw)的分軌,BS.1770。
# 參考版本的 player.mjs 沒有 raw 選項,這裡在暫時的 worktree 裡補一行(跟現在 player.mjs 的 raw 同一個做法),量完刪掉。
# 用法:bash tools/mix/make_balance_ref.sh [commit]
set -e
REF=${1:-5adb7c5}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
W=/tmp/bt-balance-ref
OUT=/tmp/bt-balance-ref-wav
rm -rf "$OUT"; git -C "$ROOT" worktree remove --force "$W" 2>/dev/null || true
git -C "$ROOT" worktree add -q --detach "$W" "$REF"
python3 - "$W/styles/player.mjs" <<'PY'
import sys
p=sys.argv[1]; s=open(p).read()
a="    const session = p.buildBuses(st), { buses } = session;"
assert a in s
s=s.replace(a,"    if (opt.raw) { p.master.disconnect(); p.master.connect(ctx.destination); }\n"+a,1)
open(p,"w").write(s)
PY
cp "$ROOT/tools/samples/render_styles.mjs" "$W/tools/samples/render_styles.mjs"
sed -i 's/const { buffer, meta, failed, gr } = await p.renderOffline(style, o, +bars);/const { buffer, meta, failed, gr = { drums: [], glue: [] } } = await p.renderOffline(style, o, +bars);/' "$W/tools/samples/render_styles.mjs"
ln -sf "$ROOT/tools/samples/node_modules" "$W/tools/samples/node_modules"
S="pop mandopop_ballad jpop citypop kpop_dance kpop_ballad rnb_neosoul lofi reggaeton"
J=""; for s in $S; do for t in drums bass keys keys2 pad guitar; do J="$J $s::high:8:$t:raw"; done; done
(cd "$W" && node tools/samples/render_styles.mjs "$OUT" $J > /dev/null)
python3 - "$OUT" "$REF" "$ROOT/tools/mix/balance_ref.json" <<'PY'
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(sys.argv[3]))
from analyze import load, lufs
D, REF, OUTF = sys.argv[1:4]
res = {"_說明": f"各軌相對鼓的響度(LU,BS.1770,跳過母帶鏈)。參考版本 {REF}(Steven 長期在聽的那一版),high 密度 8 小節,"
       "跟 tools/mix/analyze.py 同一種量法。由 tools/mix/make_balance_ref.sh 產生,不要手改", "ref": REF, "styles": {}}
for s in "pop mandopop_ballad jpop citypop kpop_dance kpop_ballad rnb_neosoul lofi reggaeton".split():
    L = {}
    for t in ("drums", "bass", "keys", "keys2", "pad", "guitar"):
        f = f"{D}/{s}__high_8_{t}_raw.wav"
        if os.path.exists(f):
            x, sr = load(f)
            if np.abs(x).max() > 1e-4: L[t] = lufs(x, sr)
    res["styles"][s] = {t: round(v - L["drums"], 1) for t, v in L.items() if t != "drums"}
json.dump(res, open(OUTF, "w"), ensure_ascii=False, indent=1)
print(json.dumps(res["styles"], ensure_ascii=False))
PY
git -C "$ROOT" worktree remove --force "$W"; rm -rf "$OUT"
