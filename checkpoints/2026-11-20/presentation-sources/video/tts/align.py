"""ASR 단어 시각 + 대본 글자 맞추기로 줄 경계를 찾고, 가까운 쉼 한가운데에서 자른다"""
import json, re, sys, difflib, subprocess
from seg import silences, dur
def norm(s): return re.sub(r'[^가-힣A-Za-z0-9]','',s)
def align(mp3, txt):
    lines=[l for l in open(txt).read().split('\n') if l.strip()]
    W=json.load(open(mp3.replace('.mp3','_words.json')))
    exp=[]; owner=[]
    for k,l in enumerate(lines):
        for ch in norm(l): exp.append(ch); owner.append(k)
    asr=[]; at=[]
    for a,b,w in W:
        cs=norm(w)
        for i,ch in enumerate(cs): asr.append(ch); at.append(a+(b-a)*(i+0.5)/max(1,len(cs)))
    sm=difflib.SequenceMatcher(None,''.join(exp),''.join(asr),autojunk=False)
    t_of={}
    for blk in sm.get_matching_blocks():
        for i in range(blk.size): t_of[blk.a+i]=at[blk.b+i]
    first=[None]*len(lines); last=[None]*len(lines)
    for i,k in enumerate(owner):
        if i in t_of:
            if first[k] is None: first[k]=t_of[i]
            last[k]=t_of[i]
    cover=[sum(1 for i,k in enumerate(owner) if k==kk and i in t_of)/max(1,sum(1 for k in owner if k==kk)) for kk in range(len(lines))]
    D=dur(mp3); S=silences(mp3,-40,0.08)
    cuts=[]
    for k in range(len(lines)-1):
        e=last[k]; s=first[k+1]
        # 두 줄 사이 쉼 중 가장 긴 것
        best=None
        for a,b in S:
            if b>e-0.15 and a<s+0.15:
                if best is None or (b-a)>(best[1]-best[0]): best=(a,b)
        cuts.append(((best[0]+best[1])/2, best) if best else ((e+s)/2, None))
    return lines, first, last, cover, cuts, D, S
if __name__=='__main__':
    mp3,txt=sys.argv[1],sys.argv[2]
    lines,first,last,cover,cuts,D,S=align(mp3,txt)
    for k,l in enumerate(lines):
        c=cuts[k][0] if k<len(cuts) else D
        print(f'{k+1:2d} {first[k] or -1:7.2f}-{last[k] or -1:7.2f} cov{cover[k]:.2f} cut {c:7.2f} {"" if k>=len(cuts) or cuts[k][1] else "NO-SIL"}  {l[:30]}')
