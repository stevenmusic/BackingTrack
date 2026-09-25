"""錄好的音檔裡,每一顆和弦那段時間**實際聽得到**哪些音級(含殘響、延遲、上一顆的尾巴)。
用法:chroma.py <clips 資料夾> ;每段的和弦從 clips.jsonl 的 prog 算"""
import sys, json, numpy as np, soundfile as sf, re
N=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
PC={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
def root(ch):
    m=re.match(r'([A-G])(b|#)?',ch); return (PC[m[1]]+{'b':-1,'#':1}.get(m[2],0))%12
QUAL={'7':[0,4,7,10],'m7':[0,3,7,10],'maj7':[0,4,7,11],'m7b5':[0,3,6,10],'':[0,4,7],'m':[0,3,7]}
def pcs(ch):
    r=root(ch); q=re.sub(r'^[A-G](b|#)?','',ch); return [(r+i)%12 for i in QUAL.get(q,[0,4,7,10])]
d=sys.argv[1]
for l in open(d+'/clips.jsonl'):
    r=json.loads(l); chords=[c.strip() for c in r['prog'].split(' - ')]
    x,sr=sf.read(f"{d}/clips/{r['id']}.wav",always_2d=True,dtype='float32'); x=x.mean(1)
    spb=60/r['bpm']; fb=r.get('fromBeat',32); nb=len(chords)
    n=8192; f=np.fft.rfftfreq(n,1/sr); sel=(f>250)&(f<2100)
    midi=69+12*np.log2(f[sel]/440); pcbin=np.round(midi).astype(int)%12
    def barE(bar, a, b):
        t0=(bar*4-fb)*spb
        seg=x[int(max(0,t0+a*spb)*sr):int((t0+b*spb)*sr)]
        if len(seg)<n: return None
        P=np.zeros(len(f))
        for i in range(0,len(seg)-n,n//2): P+=np.abs(np.fft.rfft(seg[i:i+n]*np.hanning(n)))**2
        return np.bincount(pcbin,weights=P[sel],minlength=12)
    bars=range(int(fb//4), int(fb//4)+int(len(x)/sr/spb/4))
    # 預備拍讓小節號錯開:試 0–3 小節的位移,挑「和弦音佔最多能量」的那個
    best=None
    for off in range(4):
        fr=[]
        for bar in bars:
            E=barE(bar,0.05,3.9)
            if E is None: continue
            fr.append(E[pcs(chords[(bar-off)%nb])].sum()/E.sum())
        if fr and (best is None or np.mean(fr)>best[1]): best=(off,np.mean(fr))
    off=best[0]
    print('==',r['label'],r['style'],r['prog'],'| 位移',off,'小節,和弦音佔 %.0f%%'%(best[1]*100))
    for ci,ch in enumerate(chords):
        C=np.zeros(12); early=np.zeros(12)
        for bar in bars:
            if (bar-off)%nb!=ci: continue
            for part,(a,b) in (('early',(0.05,0.6)),('all',(0.05,3.9))):
                E=barE(bar,a,b)
                if E is None: continue
                if part=='all': C+=E
                else: early+=E
        if C.sum()==0: continue
        C=10*np.log10(C/C.max()+1e-9); early=10*np.log10(early/early.max()+1e-9)
        ct=pcs(ch); out=[(N[i],round(float(C[i]),1),round(float(early[i]),1)) for i in range(12) if i not in ct and C[i]>-12]
        print(f'  {ch:7} 和弦外、在最強音級 -12dB 以內(整小節 / 換和弦後前半拍):', out)
