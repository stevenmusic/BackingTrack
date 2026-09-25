#!/usr/bin/env python3
"""從真歌抽和弦進行(分軌之後只用貝斯 + 其他,拿掉人聲與鼓):
逐拍算 chroma,每兩拍比對和弦樣板(大三/小三/屬七/大七/小七/半減/sus4),
貝斯那一軌的最低音當根音的加權;全曲 chroma 判調(Krumhansl);輸出轉成 C 大調(或 A 小調)的級數。
段落:以 4 小節為一塊,算人聲能量 → 人聲最大的那幾塊當副歌、有人聲但較小的當主歌。
**自動辨識不是採譜**:和弦性質(7 / maj7 / sus)錯的機會不小,根音與大小調比較可靠
  /tmp/abx/bin/python chords.py <4 軌資料夾 glob>"""
import sys, glob, os, json, numpy as np, soundfile as sf, librosa, collections
SR = 22050
N = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
Q = {'': [0, 4, 7], 'm': [0, 3, 7], '7': [0, 4, 7, 10], 'maj7': [0, 4, 7, 11], 'm7': [0, 3, 7, 10],
     'm7b5': [0, 3, 6, 10], '7sus4': [0, 5, 7, 10], 'dim7': [0, 3, 6, 9]}
def load(d, s):
    x, sr = sf.read(os.path.join(d, s + '.wav'), always_2d=True, dtype='float32')
    return librosa.resample(x.mean(1), orig_sr=sr, target_sr=SR)
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
def key_of(ch):
    best = max(((np.corrcoef(np.roll(MAJ, k), ch)[0, 1], k) for k in range(12)))
    return best[1]
T = []
for r in range(12):
    for q, iv in Q.items():
        v = np.zeros(12); v[[(r + i) % 12 for i in iv]] = 1; v[r] += 0.5
        T.append((r, q, v / np.linalg.norm(v)))
res = {}
for d in sorted(glob.glob(sys.argv[1])):
    name = os.path.basename(d)
    harm = load(d, 'other') + load(d, 'bass') * 0.6
    bass, voc = load(d, 'bass'), load(d, 'vocals')
    tempo, beats = librosa.beat.beat_track(y=load(d, 'drums') + harm, sr=SR, start_bpm=105, tightness=200)
    ch = librosa.feature.chroma_cqt(y=harm, sr=SR, hop_length=512)
    chb = librosa.feature.chroma_cqt(y=bass, sr=SR, hop_length=512, fmin=librosa.note_to_hz('C1'), n_octaves=4)
    cs = librosa.util.sync(ch, beats, aggregate=np.median); bs = librosa.util.sync(chb, beats, aggregate=np.median)
    rv = librosa.feature.rms(y=voc, hop_length=512)[0]; vs = librosa.util.sync(rv[None], beats, aggregate=np.mean)[0]
    k = key_of(ch.sum(1))
    seq = []
    for i in range(0, cs.shape[1] - 1, 2):                 # 每兩拍一個和弦
        c = cs[:, i:i + 2].mean(1); b = bs[:, i:i + 2].mean(1)
        c = c / (np.linalg.norm(c) + 1e-9); bn = b / (b.max() + 1e-9)
        # sus4 的樣板四顆音、又跟很多九度和弦重疊,不打折的話到處都是 7sus4(第一版踩過)
        # 減七是對稱的(四個音哪一顆都可以當根音),根音只能靠貝斯分;打一點折扣,不然會搶走半減七
        sc = [((float(v @ c) + 0.25 * bn[r]) * (0.9 if 'sus' in q else 0.95 if q == 'dim7' else 1.0), r, q) for r, q, v in T]
        _, r, q = max(sc)
        seq.append(N[(r - k) % 12] + q)                      # 轉成 C 大調的級數寫法
    # 小節線:試 0 / 1 個「兩拍」的位移,挑「和弦換在小節開頭」最多的那個
    def changes_at_start(off):
        return sum(1 for i in range(off, len(seq) - 1, 2) if i > 0 and seq[i] != seq[i - 1]) - \
               sum(1 for i in range(off + 1, len(seq) - 1, 2) if seq[i] != seq[i - 1])
    off = max((0, 1), key=changes_at_start)
    seq = seq[off:]
    # 每小節(4 拍 = 2 個兩拍)
    bars = [seq[i:i + 2] for i in range(0, len(seq) - 1, 2)]
    barv = [float(np.mean(vs[i * 4:(i + 1) * 4])) for i in range(len(bars))]
    blocks = []
    for i in range(0, len(bars) - 3, 4):
        blocks.append({'bars': [' '.join(b) if b[0] != b[1] else b[0] for b in bars[i:i + 4]], 'voc': float(np.mean(barv[i:i + 4]))})
    vv = np.array([b['voc'] for b in blocks]); thr_hi = np.percentile(vv, 75); thr_lo = np.percentile(vv, 30)
    for b in blocks: b['role'] = '副歌' if b['voc'] >= thr_hi else ('主歌' if b['voc'] >= thr_lo else '前奏/間奏')
    res[name] = {'key': N[k], 'bpm': round(float(np.atleast_1d(tempo)[0]), 1), 'blocks': blocks}
    print(f'== {name}  原調 {N[k]} 大調(以下轉成 C)  {round(float(np.atleast_1d(tempo)[0]))} BPM')
    for role in ('主歌', '副歌'):
        cnt = collections.Counter(' | '.join(b['bars']) for b in blocks if b['role'] == role)
        for s, n in cnt.most_common(3): print(f'   {role} ×{n}: {s}')
p = os.environ.get('CHORDS_OUT') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'chords.json')
json.dump(res, open(p, 'w'), ensure_ascii=False, indent=1)
