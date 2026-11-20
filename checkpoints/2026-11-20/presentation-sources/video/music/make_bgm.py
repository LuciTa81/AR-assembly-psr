"""배경음악 만들기.
Sunshine(처음 ~ 결과 장면 끝, 같은 마디 구간에서 이어 붙여 반복) → 결과 장면 끝 2.4초 동안 줄여 끝냄
Have a Seat! Have a Scone!(Expected Impact 시작 ~ 영상 끝, 뒤 무음만 잘라 96.0초)
python3 music/make_bgm.py  → music/bgm.wav (영상 길이와 같음), 구간 정보 출력"""
import subprocess, numpy as np, json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); V=os.path.dirname(HERE)
U='/root/.claude/uploads/4fac0cd5-f422-520e-8442-1ee31d5d580d/'
SUN=U+'05eaed51-OneRepublic_Sunshine_Instrumental_-_Artists_Big_Hits.mp3'
SCO=U+'dd24fd6a-27_Have_a_Seat_Have_a_Scone.mp3'
SR=48000; FPS=30
def load(p):
    b=subprocess.run(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','2','-ar',str(SR),'-'],capture_output=True,check=True).stdout
    return np.frombuffer(b,np.float32).reshape(-1,2).copy()
def frames(f): return int(subprocess.check_output(['ffprobe','-v','error','-count_packets','-select_streams','v:0','-show_entries','stream=nb_read_packets','-of','csv=p=0',f]).decode().strip())
sc=[l.split("'")[1][:-4] for l in open(V+'/out/full.txt') if l.strip()]
fr={s:frames(f'{V}/out/{s}.mp4') for s in sc}; off={}; o=0
for s in sc: off[s]=o; o+=fr[s]
TOT=o; O16=off['s16_impact']
print('total frames',TOT,TOT/FPS,'s16 at',O16/FPS,'s16->end',(TOT-O16)/FPS)
sun=load(SUN); sco=load(SCO)
# 이어 붙이는 지점(초): 같은 마디가 반복되는 곳끼리 (분석으로 찾은 값)
JUMPS={131.796:28.979, 149.351:58.561}
def refine(a,b):
    # a 지점에서 b 지점으로 건너뛸 때 파형이 가장 잘 맞도록 ±40ms 안에서 b 를 미세 조정
    m=sun.mean(1); w=int(0.6*SR); ia=int(a*SR); best=(-1,0)
    for lag in range(-int(0.04*SR),int(0.04*SR)+1,24):
        ib=int(b*SR)+lag; x=m[ia:ia+w]; y=m[ib:ib+w]
        c=np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-9)
        if c>best[0]: best=(c,lag)
    return b+best[1]/SR, best[0]
J={a:refine(a,b) for a,b in JUMPS.items()}
for a,(b,c) in J.items(): print(f'jump {a:.3f} -> {b:.4f} (corr {c:.3f})')
# 순서: 0 → 131.8 ⇒ 29.0 → 149.35 ⇒ 58.6 → 131.8 ⇒ 29.0 → 149.35 ⇒ ...
need=O16*SR//FPS+SR; XF=int(0.12*SR)
out=[]; pos=0.0; n=0; order=[131.796,149.351]; k=0; segs=[]
while n<need:
    end=order[k%2]; e=int(end*SR); s=int(pos*SR)
    seg=sun[s:e+XF].copy(); segs.append((round(pos,3),end))
    if out:
        prev=out[-1]; t=np.linspace(0,np.pi/2,XF)[:,None]
        prev[-XF:]=prev[-XF:]*np.cos(t)+seg[:XF]*np.sin(t); seg=seg[XF:]
    out.append(seg); n=sum(len(x) for x in out)-XF; pos=J[end][0]; k+=1
sunL=np.concatenate(out)[:O16*SR//FPS]
print('sunshine segments',segs)
# 처음 1초 키우기, 결과 장면 끝 2.4초 줄이기
fi=int(1.0*SR); sunL[:fi]*=np.linspace(0,1,fi)[:,None]
fo=int(2.4*SR); x=np.linspace(0,1,fo); sunL[-fo:]*=(1-x*x*(3-2*x))[:,None]
# Scone: 96.0초(뒤 무음만 잘림), 시작 30ms · 끝 0.3초 정리
L16=(TOT-O16)*SR//FPS; scoL=sco[:L16].copy()
if len(scoL)<L16: scoL=np.vstack([scoL,np.zeros((L16-len(scoL),2),np.float32)])
a=int(0.03*SR); scoL[:a]*=np.linspace(0,1,a)[:,None]; b=int(0.3*SR); scoL[-b:]*=np.linspace(1,0,b)[:,None]
# 크기: 두 곡을 같은 크기(약 -25 LUFS)로. 원곡 측정값 Sunshine -11.9, Scone -13.3 LUFS
g=lambda db:10**(db/20)
sunL*=g(-25+11.9); scoL*=g(-25+13.3)
bgm=np.vstack([sunL,scoL]).astype(np.float32)
assert len(bgm)==TOT*SR//FPS, (len(bgm),TOT*SR//FPS)
print('peak',float(np.abs(bgm).max()))
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i','-','-c:a','pcm_s16le',HERE+'/bgm.wav'],input=bgm.tobytes(),check=True)
json.dump({'fps':FPS,'total_frames':TOT,'offsets':off,'frames':fr},open(HERE+'/layout.json','w'),indent=1)
print('ok bgm.wav',len(bgm)/SR,'s')
