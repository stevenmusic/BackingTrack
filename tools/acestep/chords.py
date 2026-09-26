import numpy as np, librosa, sys
N=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
Q={'maj7':[0,4,7,11],'7':[0,4,7,10],'m7':[0,3,7,10],'':[0,4,7],'m':[0,3,7]}
PC={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
exp=[(5,[0,4,7,11]),(4,[0,4,7,10]),(9,[0,3,7,10]),(0,[0,4,7,10])]
for p in sys.argv[1:]:
    y,sr=librosa.load(p,sr=22050); C=librosa.feature.chroma_cqt(y=y,sr=sr); t=librosa.frames_to_time(np.arange(C.shape[1]),sr=sr)
    bar=4*60/110; out=[]; sh=[]
    for i in range(int(len(y)/sr/bar)):
        c=C[:,(t>=i*bar+.1)&(t<(i+1)*bar-.1)].mean(1)
        out.append(max(((sum(c[(r+k)%12] for k in iv)/len(iv),N[r]+q) for r in range(12) for q,iv in Q.items()))[1])
        r,iv=exp[(i+2)%4]; sh.append(sum(c[(r+k)%12] for k in iv)/c.sum())
    print(p.split('/')[-2][:10], '和弦音佔比 %.2f'%np.mean(sh), ' '.join(out))
