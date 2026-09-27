#!/usr/bin/env python3
"""從 index.html 抽出混音 / 母帶的積木 → tools/webmix/webmix.js(可以整份搬到別的 Web Audio 專案)。
**index.html 是唯一的原稿**:改積木改 index.html,再跑這支重新產生,不要直接改 webmix.js。
  python3 tools/webmix/build.py          # 產生
  python3 tools/webmix/build.py --check  # 只檢查 webmix.js 跟 index.html 一致(不一致回 1)
"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, '..', '..', 'index.html'), encoding='utf-8').read()


def between(a, b):
    i = SRC.index(a); j = SRC.index(b, i)
    return SRC[i:j].rstrip() + '\n'


def func(name):
    i = SRC.index('function ' + name + '(')
    depth = 0; k = SRC.index('{', i)
    for p in range(k, len(SRC)):
        if SRC[p] == '{': depth += 1
        elif SRC[p] == '}':
            depth -= 1
            if depth == 0: return SRC[i:p + 1] + '\n'


parts = [
    func('mulberry32'),
    func('buildImpulseResponse').replace('function buildImpulseResponse(seconds, decayPow){', 'function buildImpulseResponse(ctx, seconds, decayPow){'),
    func('softCurve'), func('shelf'), func('makeChorus'),
    between('const LIMITER_SRC = `', 'let trueLimiter = null'),
    between('/* ══ 混音 / 母帶的積木', 'function installTrueLimiter'),
]
body = '\n'.join(parts)
head = open(os.path.join(HERE, 'head.js'), encoding='utf-8').read()
tail = open(os.path.join(HERE, 'tail.js'), encoding='utf-8').read()
out = head + '\n/* ─────────── 以下由 build.py 從 index.html 抽出來,不要直接改 ─────────── */\n\n' + body + \
      '\n/* ─────────── 抽出來的到這裡 ─────────── */\n\n' + tail
dst = os.path.join(HERE, 'webmix.js')
if '--check' in sys.argv:
    same = os.path.exists(dst) and open(dst, encoding='utf-8').read() == out
    print('一致' if same else 'webmix.js 跟 index.html 不一致:跑 python3 tools/webmix/build.py'); sys.exit(0 if same else 1)
open(dst, 'w', encoding='utf-8').write(out); print('寫好', dst, len(out), 'bytes')
