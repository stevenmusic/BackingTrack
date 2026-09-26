#!/usr/bin/env python3
"""各樂器「佔多大聲、多刺耳」——先驗證量尺,再跟真歌比(Steven 2026-09-26:「不確定是吉他還是電鋼琴太吵」)。

1. 驗證:我們自己的錄音有真值(REALISM_PROBE 把其他 bus 關掉單獨錄,/tmp/solo/<bus>/),
   拿 demucs 拆 /tmp/solo/full 的結果跟真值比。誤差夠小的特徵才能拿去比真歌(CLAUDE.md:量尺要先證明是對的)
2. 比較:同樣的特徵量真歌(上傳 13 + 合集 13)與 Suno 16 的分軌

特徵(每條分軌):
  佔比dB    = 這條 ÷ 伴奏(鼓 + 貝斯 + 吉他 + 鋼琴 + 其他,人聲不算)
  亮度Hz    = 有聲格子(> 最大 −30dB)的頻譜重心中位數
  刺耳%     = 2–5kHz 佔這條總能量的比例
  嘶%       = 5–10kHz 佔這條總能量的比例

  /tmp/abx/bin/python timbre.py verify      驗證表
  /tmp/abx/bin/python timbre.py compare     我們(/tmp/solo/full 拆軌)vs 真歌 vs Suno
"""
import sys, glob, os, json
import numpy as np, soundfile as sf, librosa

SR = 22050
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other']
BUS = {'drums': 'drumBus', 'bass': 'bassBus', 'guitar': 'combBus', 'piano': 'keysBus', 'other': 'padBus'}


def load(path):
    x, sr = sf.read(path, always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)


def feats(y):
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512)) ** 2
    fr = librosa.fft_frequencies(sr=SR, n_fft=2048)
    tot = S.sum() + 1e-12
    rms = np.sqrt(S.sum(0))
    act = rms > rms.max() * 10 ** (-30 / 20)
    cen = (fr[:, None] * S).sum(0) / (S.sum(0) + 1e-12)
    band = lambda a, b: 100 * S[(fr >= a) & (fr < b)].sum() / tot
    return {'亮度Hz': float(np.median(cen[act])) if act.any() else 0.0,
            '刺耳%': float(band(2000, 5000)), '嘶%': float(band(5000, 10000)), 'ms': float(np.mean(y ** 2))}


def stem_set(get):
    """get(stem) → 音訊;回每條的特徵 + 佔比"""
    ys = {s: get(s) for s in STEMS}
    ys['keys+other'] = ys['piano'] + ys['other']       # demucs 把 Rhodes 歸到 other(驗證表),鍵盤要兩軌合起來看
    tot = sum(np.mean(ys[s] ** 2) for s in STEMS) + 1e-12
    out = {}
    for s, y in ys.items():
        f = feats(y)
        f['佔比dB'] = float(10 * np.log10(f.pop('ms') / tot + 1e-12))
        out[s] = f
    return out


KEYS = ['佔比dB', '亮度Hz', '刺耳%', '嘶%']


def verify():
    rows = [json.loads(l) for l in open('/tmp/solo/full/clips.jsonl')]
    errs = {s: {k: [] for k in KEYS} for s in STEMS}
    solo = {b: {json.loads(l)['prog']: json.loads(l)['id'] for l in open(f'/tmp/solo/{b}/clips.jsonl')} for b in BUS.values()}
    for r in rows:
        cid = r['id']
        truth = stem_set(lambda s: load(f'/tmp/solo/{BUS[s]}/clips/{solo[BUS[s]][r["prog"]]}.wav'))
        sep = stem_set(lambda s: load(f'/tmp/solo/sep/htdemucs_6s/{cid}/{s}.wav'))
        for s in STEMS:
            for k in KEYS:
                errs[s][k].append(sep[s][k] - truth[s][k])
        print(r['prog'][:30])
        for s in STEMS:
            print(f'  {s:7s} 真值 ' + '  '.join(f'{k} {truth[s][k]:7.1f}' for k in KEYS))
            print(f'  {"":7s} 拆軌 ' + '  '.join(f'{k} {sep[s][k]:7.1f}' for k in KEYS))
    print('\n拆軌 − 真值(平均 [最小, 最大],n = %d)' % len(rows))
    for s in STEMS:
        print(f'  {s:7s} ' + '  '.join(f'{k} {np.mean(v):+6.1f} [{min(v):+.1f},{max(v):+.1f}]' for k, v in errs[s].items()))


def compare():
    groups = {'真歌': glob.glob('/tmp/sty/sep_real/htdemucs_6s/*/') + glob.glob('/tmp/sty/sep_realmix/htdemucs_6s/*/'),
              'Suno': glob.glob('/tmp/sty/sep_suno/htdemucs_6s/*/'),
              '我們': glob.glob(os.environ.get('OURS', '/tmp/solo/sep/htdemucs_6s/*/'))}
    res = {}
    for g, dirs in groups.items():
        res[g] = [stem_set(lambda s, d=d: load(os.path.join(d, s + '.wav'))) for d in dirs]
    for s in ['guitar', 'keys+other', 'bass', 'drums']:
        print(f'\n{s}')
        for k in KEYS:
            line = f'  {k:6s}'
            for g, xs in res.items():
                v = [x[s][k] for x in xs]
                line += f'  {g} 中位 {np.median(v):7.1f} [{np.percentile(v, 25):.1f},{np.percentile(v, 75):.1f}] n={len(v)}'
            print(line)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'timbre.json'), 'w'),
              ensure_ascii=False, indent=1, default=float)


{'verify': verify, 'compare': compare}[sys.argv[1] if len(sys.argv) > 1 else 'verify']()
