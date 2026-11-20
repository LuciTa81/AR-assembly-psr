"""Narrated motion presentation from faithful, read-only v14 slide exports."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from deck_shapes import get_shapes, PPT

ROOT=Path(__file__).resolve().parent
MEDIA=Path('C:/Users/fresh/Documents/Codex/AI-Assembly-Video-Prep-20261116/edited/take4-sync')
FF=Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin')
W,H,FPS=1920,1080,30
NAVY='#365880'
ORANGE='#df8125'
PALE='#edf2f8'
SHAPES=get_shapes()
TIMING=json.loads((ROOT/'timing.json').read_text(encoding='utf-8'))
TOTAL=sum(s['duration'] for s in TIMING)
OUTPUT=ROOT/'AI-Assembly-Guide-Full-Motion-KO.mp4'

@lru_cache(maxsize=100)
def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf' if bold else 'C:/Windows/Fonts/malgun.ttf',size)

def ease(t):
    t=max(0,min(1,t))
    return 1-(1-t)**3

def fit_text(draw,text,box,size=25,color=NAVY,bold=False,bg='white',align='left'):
    x,y,w,h=box
    draw.rectangle((x,y,x+w,y+h),fill=bg)
    for s in range(size,12,-1):
        f=font(s,bold)
        lines=[]
        for para in text.split('\n'):
            line=''
            for char in para:
                if draw.textlength(line+char,font=f)>w-10 and line:
                    lines.append(line);line=char
                else:line+=char
            lines.append(line)
        if len(lines)*(s+7)<=h+3:break
    yy=y+(h-len(lines)*(s+7))/2-2
    for line in lines:
        xx=x+4 if align=='left' else x+(w-draw.textlength(line,font=f))/2
        draw.text((xx,yy),line,font=f,fill=color)
        yy+=s+7

def replace_text(im,num,old,new,size=24,bold=False,bg=None):
    match=next((s for s in SHAPES[num] if s['text']==old),None)
    if match is None:raise ValueError((num,old))
    x,y,w,h=match['box']
    bg=bg or im.getpixel((min(W-1,x+1),min(H-1,y+1)))
    fit_text(ImageDraw.Draw(im),new,(x-2,y,w+4,h),size,NAVY,bold,bg)

def source_slide(num):
    im=Image.open(ROOT/'slides'/f'slide-{num:02d}.png').convert('RGB')
    # Only the video copy changes; preserve the source deck and user-confirmed results.
    if num==6:
        d=ImageDraw.Draw(im)
        fit_text(d,'실시간: 시간 증거 + FSM    |    분석: MediaPipe + HMM / Viterbi',
                 (106,940,1708,42),24,bg='white')
    if num==9:
        replace_text(im,9,'12개 틀림','단계 경계에서 지연',22)
        replace_text(im,9,'2학기에는 이 판단을 실시간 구조로 옮겼습니다:  프레임별 시간 증거 게이트  →  HMM · Viterbi 단계 추정 + FSM',
                     '실시간 진행: 시간 증거 게이트 + FSM   |   HMM / Viterbi: 저장 영상 비교 분석',24)
    if num==10:
        replace_text(im,10,'나사 체결 확인 한 뒤 B로 넘어갑니다.','전환 조건 확인 뒤 B를 안내합니다.',23)
        replace_text(im,10,'나사 상태를 확인 한 뒤 다음 단계로','작업 관측과 전환 조건 확인',24,True,bg=PALE)
    if num==16:
        replace_text(im,16,'다른 각도에서도 항상 겹침','거리 · 시점 변화 확인',23,True,bg='white')
    if num==12:
        ImageDraw.Draw(im).rectangle((935,405,942,492),fill=PALE)
    if num in (13,15):
        d=ImageDraw.Draw(im)
        d.rectangle((950,62,1919,132),fill='white')
        title=('잠깐 안 보여도, 한 일은 지우지 않습니다' if num==13 else
               '관제 화면 하나로 연결부터 작업 진행까지 확인합니다')
        fit_text(d,title,(960,66,886,63),30,align='center')
    return im

# Logical regions follow the existing v14 layout, never introduce a new slide template.
REGIONS={
2:[(870,160,1814,267),(870,304,1814,411),(870,448,1814,555),(870,592,1814,699),(870,736,1814,843),(870,880,1814,987)],
3:[(780,155,1830,340),(780,350,1830,535),(780,545,1830,730),(106,765,1830,965)],
4:[(106,477,1814,570),(106,572,1814,666),(106,670,1814,763),(106,768,1814,861),(106,890,1814,975)],
5:[(107,417,274,579),(297,417,465,579),(488,417,655,579),(678,417,846,579),(869,417,1037,579),(106,640,1037,951)],
7:[(106,160,646,931),(686,160,1226,931),(1266,160,1806,931)],
8:[(106,165,510,925),(540,165,944,925),(974,165,1378,925),(1408,165,1814,925)],
9:[(106,204,1814,378),(106,393,1814,567),(106,582,1814,756),(106,810,1814,952)],
10:[(106,204,514,745),(540,204,948,745),(973,204,1381,745),(1406,204,1814,745)],
11:[(106,165,770,650),(818,200,1814,306),(818,337,1814,442),(818,477,1814,566),(106,683,1814,953)],
12:[(935,204,1814,291),(935,305,1814,392),(935,405,1814,492),(935,506,1814,594),(107,668,1814,977)],
13:[(106,666,659,856),(683,666,1237,856),(1262,666,1814,856)],
15:[(1375,234,1782,405),(1375,435,1782,569),(1375,598,1782,734),(1375,764,1782,883)],
16:[(106,150,659,725),(684,150,1236,725),(1262,150,1814,725),(106,775,1814,947)],
17:[(924,177,1814,318),(924,354,1814,495),(924,531,1814,672),(924,716,1814,916)],
18:[(106,200,960,294),(106,300,960,389),(106,395,960,483),(106,510,960,951)],
}

def cue_times(scene,regions):
    num=scene['slide'];parts=scene['parts']
    if num==12:
        p=[x['start'] for x in parts]
        return [p[1],p[1]+5.2,p[2],p[3],p[3]+4.3]
    if num==11:return [1,parts[1]['start'],parts[2]['start'],parts[2]['start']+7,parts[3]['start']]
    if num in (9,16):
        return [1,parts[1]['start'],parts[2]['start'],max(parts[-1]['start']+5,scene['duration']-6)]
    last=max(6,scene['duration']-6)
    return [1+i*(last-1)/max(1,len(regions)-1) for i in range(len(regions))]

def animate_regions(base,scene,t):
    im=base.copy();num=scene['slide'];rects=REGIONS.get(num,[])
    cues=cue_times(scene,rects)
    active=-1
    for i,(r,start) in enumerate(zip(rects,cues)):
        if t>=start:active=i
        a=.86*(1-ease((t-start)/.55))
        if a>0:
            crop=im.crop(r)
            im.paste(Image.blend(crop,Image.new('RGB',crop.size,'white'),a),(r[0],r[1]))
    if active>=0 and num not in (6,14):
        x1,y1,x2,y2=rects[active]
        d=ImageDraw.Draw(im)
        d.rectangle((x1-9,y1,x1-5,y2),fill=ORANGE)
        p=min(1,max(0,(t-cues[active])/.65))
        d.line((x1,y2+3,x1+(x2-x1)*p,y2+3),fill=ORANGE,width=2)
    return im

class Video:
    def __init__(self,name):
        self.cap=cv2.VideoCapture(str(MEDIA/name))
        if not self.cap.isOpened():raise RuntimeError(name)
        self.fps=self.cap.get(cv2.CAP_PROP_FPS)
        self.count=int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.last=-1;self.frame=None
    def get(self,t):
        target=max(0,min(self.count-1,round(t*self.fps)))
        if target==self.last:return self.frame
        if target!=self.last+1:self.cap.set(cv2.CAP_PROP_POS_FRAMES,target)
        ok,f=self.cap.read()
        if not ok:raise RuntimeError(f'Cannot decode frame {target}')
        self.last=target
        self.frame=Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB))
        return self.frame
    def close(self):self.cap.release()

def paste_fit(im,video,rect):
    x1,y1,x2,y2=rect
    im.paste(video.resize((x2-x1,y2-y1),Image.Resampling.BICUBIC),(x1,y1))

def subtitle_cues(scene):
    cues=[]
    for p in scene['parts']:
        metadata=[json.loads(l) for l in Path(p['metadata']).read_text(encoding='utf-8').splitlines() if l]
        for m in metadata:
            if m['type']!='SentenceBoundary':continue
            start=p['start']+m['offset']/1e7
            end=min(p['start']+p['duration'],start+m['duration']/1e7+.12)
            # Spoken Latin names stay readable in the on-screen text.
            text=m['text'].replace('에이아이 어셈블리 가이드','AI Assembly Guide').replace('나사 에이','나사 A').replace('나사 비','나사 B').replace('나사 씨','나사 C').replace('나사 디','나사 D')
            cues.append((start,end,text))
    return cues

def caption(im,scene,t,cues,offset):
    d=ImageDraw.Draw(im)
    text=next((text for a,b,text in cues if a<=t<b),'')
    dark=scene['slide'] in (1,19)
    bg='#101b21' if dark else '#f2f5f9'
    fg='#f1f6f9' if dark else NAVY
    d.rectangle((72,1001,1848,1074),fill=bg)
    if text:fit_text(d,text,(88,1006,1744,59),28,fg,bg=bg,align='center')
    else:
        fit_text(d,scene['title'],(88,1011,1744,45),22,'#8e9dad',bg=bg,align='center')
    d.rectangle((72,1071,72+round(1776*(offset+t)/TOTAL),1074),fill=ORANGE)

def apply_special(im,base,scene,t,clips):
    num=scene['slide']
    if num in (1,19):
        # A slow camera move for the cover/closing; text remains on the original artwork.
        scale=1.0+.013*min(1,t/scene['duration'])
        big=base.resize((round(W*scale),round(H*scale)),Image.Resampling.BICUBIC)
        im=big.crop(((big.width-W)//2,(big.height-H)//2,(big.width+W)//2,(big.height+H)//2))
    elif num==6:
        # Follow data flow without replacing the existing architecture drawing.
        q=min(3,int(max(0,t-2)/(scene['duration']/4)))
        rects=[(114,199,390,493),(525,202,1173,465),(880,516,1173,776),(1452,160,1795,918)]
        r=rects[q]
        ImageDraw.Draw(im).rectangle(r,outline=ORANGE,width=3)
    elif num==12 and t>=scene['parts'][3]['start']:
        begin=scene['parts'][3]['start']
        source=66+t-begin
        video=clips['composite'].get(source)
        paste_fit(im,video,(107,189,887,628))
        sbs=clips['sbs'].get(source)
        left=sbs.crop((0,0,1920,1080));right=sbs.crop((1920,0,3840,1080))
        paste_fit(im,left,(107,711,557,964))
        paste_fit(im,right,(581,711,1031,964))
        a=np.asarray(left.resize((450,253)),dtype=np.float32)
        b=np.asarray(right.resize((450,253)),dtype=np.float32)
        # Preserve both silhouettes; use an additive comparison, not geometric warping.
        a*=np.array([.2,1,.9]);b*=np.array([1,.65,.15])
        combined=Image.fromarray(np.clip(a+b,0,255).astype(np.uint8))
        im.paste(combined,(1055,711))
        d=ImageDraw.Draw(im)
        for x,label in [(117,'왼눈'),(591,'오른눈'),(1065,'겹쳐 보기')]:
            d.rounded_rectangle((x,923,x+110,954),radius=5,fill='white')
            d.text((x+7,925),label,font=font(18,True),fill=NAVY)
        fit_text(d,'카메라 시점 재구성 · Unity 출력 사용',(107,631,780,30),18,color='#7c8da6')
    elif num==13:
        src=35+min(8,max(0,t-2))
        paste_fit(im,clips['composite'].get(src),(107,257,635,554))
    elif num==14:
        src=min(121.46,max(0,t-1))
        paste_fit(im,clips['composite'].get(src),(107,156,1451,912))
        d=ImageDraw.Draw(im)
        fit_text(d,'카메라 시점 재구성 · Unity 출력 사용',(107,924,1344,32),20,color='#7c8da6')
        times=[0,13,26.9,49.7,71.6,101,119]
        labels=['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인']
        helptext=['상자를 놓아주세요','뚜껑을 덮어주세요','나사 A를 조여주세요','나사 B를 조여주세요','나사 C를 조여주세요','나사 D를 조여주세요','조립 상태를 확인해주세요']
        active=max(i for i,v in enumerate(times) if src>=v)
        d.rectangle((1480,217,1820,926),fill='white')
        for i,(v,label,sub) in enumerate(zip(times,labels,helptext)):
            yy=222+i*101
            if i==active:
                d.rectangle((1480,yy,1820,yy+94),fill=PALE)
                d.rectangle((1480,yy,1485,yy+94),fill=ORANGE)
            stamp=f'{int(v)//60}:{int(round(v))%60:02d}'
            d.text((1490,yy+22),stamp,font=font(29,True),fill=ORANGE if i==active else '#a2b7d1')
            d.text((1570,yy+3),label,font=font(31,True),fill=NAVY)
            d.text((1570,yy+49),sub,font=font(19),fill='#7b8798')
            d.line((1487,yy+95,1814,yy+95),fill='#ccd5e2',width=1)
        d.text((109,965),'시연 설정: 초록 안내 후 2초 뒤 다음 나사로 전환',font=font(18),fill='#8a96a7')
    return im

def frame(base,scene,t,cues,offset,clips):
    im=animate_regions(base,scene,t)
    im=apply_special(im,base,scene,t,clips)
    # Short white fades between explanatory pages; no flashy wipes over the demo.
    if scene['slide'] not in (1,19):
        alpha=ease(t/.32)*ease((scene['duration']-t)/.28)
        if alpha<1:im=Image.blend(Image.new('RGB',(W,H),'white'),im,alpha)
    else:
        alpha=ease(t/.9)*ease((scene['duration']-t)/.8)
        if alpha<1:im=Image.blend(Image.new('RGB',(W,H),'black'),im,alpha)
    caption(im,scene,t,cues,offset)
    return im

def stamp(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');ap.add_argument('--slides',nargs='*',type=int)
    args=ap.parse_args()
    for name in ('segments','preview'):(ROOT/name).mkdir(exist_ok=True)
    offset=0;allsubs=[];chapters=[]
    for scene in TIMING:
        num=scene['slide'];length=scene['duration']
        cues=subtitle_cues(scene)
        allsubs.extend((a+offset,b+offset,text) for a,b,text in cues)
        chapters.append(dict(slide=num,title=scene['title'],start=offset,end=offset+length))
        if args.slides and num not in args.slides:offset+=length;continue
        output=ROOT/'segments'/f'{num:02d}.mp4'
        if output.exists() and not args.preview:offset+=length;continue
        base=source_slide(num);clips={}
        if num in (12,13,14):clips['composite']=Video('06-camera-composite-full.mp4')
        if num==12:clips['sbs']=Video('04-unity-sbs-synchronized.mp4')
        if args.preview:
            for f in (.15,.52,.87):
                t=length*f
                frame(base,scene,t,cues,offset,clips).save(ROOT/'preview'/f'{num:02d}-{int(f*100):02d}.jpg',quality=94)
            for clip in clips.values():clip.close()
            offset+=length
            continue
        frames=round(length*FPS)
        cmd=[str(FF/'ffmpeg.exe'),'-hide_banner','-loglevel','error','-y',
             '-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-',
             '-i',scene['audio'],'-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast',
             '-crf','19','-threads','6','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
             '-ar','48000','-ac','2','-t',str(length),'-movflags','+faststart',str(output)]
        error_path=ROOT/'segments'/f'{num:02d}.stderr.txt'
        with error_path.open('wb') as err:
            proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=err)
            try:
                for n in range(frames):
                    t=n/FPS
                    im=frame(base,scene,t,cues,offset,clips)
                    if n==frames//2:im.save(ROOT/'preview'/f'{num:02d}-rendered.jpg',quality=92)
                    proc.stdin.write(im.tobytes())
                    if n and n%900==0:print(f'Render {num:02d}: {n/FPS:.0f}/{length:.0f}s',flush=True)
                proc.stdin.close()
                if proc.wait()!=0:raise RuntimeError(error_path.read_text(errors='replace'))
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                for clip in clips.values():clip.close()
        print(f'Completed slide {num:02d} ({length:.1f}s)',flush=True)
        offset+=length
    (ROOT/'chapters.json').write_text(json.dumps(chapters,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'AI-Assembly-Guide-KO.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{text}' for i,(a,b,text) in enumerate(allsubs))+'\n',encoding='utf-8')
    (ROOT/'narration-ko.md').write_text('# AI Assembly Guide 내레이션\n\n'+'\n\n'.join(f'## {s["slide"]:02d}. {s["title"]}\n\n'+'\n\n'.join(p['text'] for p in s['parts']) for s in TIMING),encoding='utf-8')
    if args.preview or args.slides:return
    listing=ROOT/'concat.txt'
    listing.write_text('\n'.join(f"file 'segments/{s['slide']:02d}.mp4'" for s in TIMING),encoding='utf-8')
    metadata=ROOT/'chapters.ffmetadata'
    metadata.write_text(';FFMETADATA1\ntitle=AI Assembly Guide\nartist=Choi Minjun\n'+''.join(
        f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['start']*1000)}\nEND={round(c['end']*1000)}\ntitle={c['slide']:02d} {c['title']}\n" for c in chapters),encoding='utf-8')
    subprocess.run([str(FF/'ffmpeg.exe'),'-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(metadata),'-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',str(OUTPUT)],check=True)
    original=json.loads((ROOT/'source-manifest.json').read_text(encoding='utf-8'))
    unchanged=hashlib.sha256(PPT.read_bytes()).hexdigest()==original['source_sha256']
    assert unchanged,'Source PPT changed during render'
    (ROOT/'render-manifest.json').write_text(json.dumps(dict(output=str(OUTPUT),duration=TOTAL,width=W,height=H,fps=FPS,source_unchanged=unchanged,source_sha256=original['source_sha256'],voice=original['voice'],chapters=chapters),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'FINAL {OUTPUT} ({TOTAL:.2f}s)',flush=True)

if __name__=='__main__':main()
