"""파트 음성을 문장(줄) 단위로 자른다: 쉼 후보 + 문장 길이 예상(음절 수)으로 최적 경계 찾기"""
import subprocess, re, sys, json, numpy as np
def silences(f, db=-40, d=0.10):
    out=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',f,'-af',f'silencedetect=n={db}dB:d={d}','-f','null','-'],capture_output=True,text=True).stderr
    st=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',out)]; en=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',out)]
    return list(zip(st,en))
def dur(f): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]).decode())
def syl(s): return len(re.findall(r'[가-힣]',s))+0.55*len(re.findall(r'[A-Za-z0-9]',s))
def segment(f, lines):
    D=dur(f); S=silences(f)
    head=S[0][1] if S and S[0][0]<0.05 else 0.0
    tail=S[-1][0] if S and S[-1][1]>D-0.05 else D
    cands=[(a,b) for a,b in S if a>head+0.3 and b<tail-0.3]
    n=len(lines); K=n-1; sy=np.array([syl(l) for l in lines]); 
    speech=tail-head-sum(b-a for a,b in cands)*0.6
    rate=sy.sum()/speech
    pts=[head]+[(a+b)/2 for a,b in cands]+[tail]; L=[0]+[b-a for a,b in cands]+[0]
    m=len(pts); INF=1e18
    # dp[i][k]: 마지막 경계가 pts[i], 줄 k개 끝냄
    dp=np.full((m,n+1),INF); bk=np.zeros((m,n+1),int); dp[0][0]=0
    for k in range(1,n+1):
        for i in range(1,m):
            if k<n and i==m-1: continue
            if k==n and i!=m-1: continue
            for j in range(0,i):
                if dp[j][k-1]>=INF: continue
                seg=pts[i]-pts[j]; pred=sy[k-1]/rate+0.25
                cost=(seg-pred)**2/max(pred,1.0) - (2.0*L[i] if k<n else 0)
                if dp[j][k-1]+cost<dp[i][k]: dp[i][k]=dp[j][k-1]+cost; bk[i][k]=j
    idx=[m-1]; k=n
    while k>0: idx.append(bk[idx[-1]][k]); k-=1
    idx=idx[::-1]
    segs=[]
    for k in range(n):
        a=pts[idx[k]]; b=pts[idx[k+1]]
        # 경계의 쉼 안쪽으로 붙여 자르기: 시작은 쉼 끝, 끝은 쉼 시작
        sa = cands[idx[k]-1][1]-0.05 if idx[k]>0 else max(0,head-0.05)
        eb = cands[idx[k+1]-1][0]+0.08 if idx[k+1]<m-1 else min(D,tail+0.1)
        segs.append([round(sa,3),round(eb,3)])
    return segs, rate, D
if __name__=='__main__':
    f,txt=sys.argv[1],sys.argv[2]
    lines=[l for l in open(txt).read().split('\n') if l.strip()]
    segs,rate,D=segment(f,lines)
    print('dur',D,'rate',round(rate,2),'lines',len(lines))
    for (a,b),l in zip(segs,lines): print(f'{a:7.2f} {b:7.2f} {b-a:5.2f} {syl(l)/(b-a):4.1f}  {l}')
    json.dump(segs,open(f.replace('.mp3','_segs.json'),'w'))
