import sys, numpy as np, librosa
PC={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
def tones(ch):
    r=PC[ch[0]]; q=ch[1:]
    iv={'maj7':[0,4,7,11],'7':[0,4,10,7],'m7':[0,3,7,10]}[q]
    return set((r+i)%12 for i in iv)
prog=['Fmaj7','E7','Am7','C7']; bpm=110; bar=4*60/bpm
def score(path):
    y,sr=librosa.load(path,sr=22050,mono=True)
    C=librosa.feature.chroma_cqt(y=y,sr=sr,hop_length=512); t=librosa.frames_to_time(np.arange(C.shape[1]),sr=sr,hop_length=512)
    best=None
    for off in range(4):
        fr=[]
        for i in range(int(len(y)/sr/bar)):
            m=(t>=i*bar+0.1)&(t<(i+1)*bar-0.1); c=C[:,m].mean(1)
            ts=tones(prog[(i+off)%4]); fr.append(sum(c[p] for p in ts)/c.sum())
        s=np.mean(fr)
        if best is None or s>best[0]: best=(s,off,[round(x,2) for x in fr])
    return best
for p in sys.argv[1:]: print(p.split('/')[-1][:14], 'chord-tone share %.2f off %d per-bar %s'%score(p))
