"""Narrated motion presentation from faithful, read-only v14 slide exports."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from deck_shapes import get_shapes, PPT
from storyboard import DISPLAY_WORDS

ROOT=Path(__file__).resolve().parent
OLD=ROOT.with_name('AI-Assembly-Full-Video-20261117')
MEDIA=Path('C:/Users/fresh/Documents/Codex/AI-Assembly-Video-Prep-20261116/edited/take4-sync')
FF=Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin')
W,H,FPS=1920,1080,30
NAVY='#365880'
ORANGE='#df8125'
PALE='#edf2f8'
SHAPES=get_shapes()
TIMING=json.loads((ROOT/'timing.json').read_text(encoding='utf-8'))
TOTAL=sum(s['duration'] for s in TIMING)
OUTPUT=ROOT/'AI-Assembly-Guide-Full-Motion-KO-v2.mp4'

@lru_cache(maxsize=100)
def font(size,bold=False):
    name='Pretendard-Bold.ttf' if bold else 'Pretendard-Regular.ttf'
    return ImageFont.truetype('C:/Users/fresh/AppData/Local/Microsoft/Windows/Fonts/'+name,size)

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
        width=draw.textlength(line,font=f)
        xx=x+4 if align=='left' else (x+w-width-4 if align=='right' else x+(w-width)/2)
        draw.text((xx,yy),line,font=f,fill=color)
        yy+=s+7

def replace_text(im,num,old,new,size=24,bold=False,bg=None):
    match=next((s for s in SHAPES[num] if s['text']==old),None)
    if match is None:raise ValueError((num,old))
    x,y,w,h=match['box']
    bg=bg or im.getpixel((min(W-1,x+1),min(H-1,y+1)))
    fit_text(ImageDraw.Draw(im),new,(x-2,y,w+4,h),size,NAVY,bold,bg)

def source_slide(num):
    im=Image.open(OLD/'slides'/f'slide-{num:02d}.png').convert('RGB')
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
        d=ImageDraw.Draw(im)
        d.rectangle((950,66,1919,131),fill='white')
        fit_text(d,'숫자와 기록으로 확인했습니다',(960,66,886,63),32,align='right')
        for text,box in [
            ('카메라와 눈의 시점 차이로 어긋남',(762,508,474,50)),
            ('가림 이후 작업을 다시 시작',(1340,508,474,50)),
            ('거리와 시점 변화에 따른 일치율',(684,672,552,39)),
            ('가림 후에도 진행한 단계에서 계속',(1262,672,552,39))]:
            fit_text(d,text,box,27,bold=box[1]==672)
    if num==8:
        d=ImageDraw.Draw(im)
        bodies=[
            'Unity로 만든 Quest 3 앱에서\n조립 영상을 일정 간격으로 저장했습니다.',
            'ArUco 마커를 기준으로 정면 보정해\n같은 작업 영역을 비교했습니다.',
            '드라이버, 손잡이, 나사에 라벨을\n붙이고 YOLOv11을 학습했습니다.',
            '도구 끝과 나사의 거리, 영역 점수,\n손 위치를 작업 특징으로 추출했습니다.']
        for x,text in zip([106,540,973,1406],bodies):
            fit_text(d,text,(x,481,408,119),24,color='#353535')
    if num==12:
        d=ImageDraw.Draw(im)
        d.rectangle((935,405,942,492),fill=PALE)
        fit_text(d,'실물의 깊이에 맞춰\n하나로 겹쳐 보입니다.',(1552,902,261,80),25)
    if num in (13,15):
        d=ImageDraw.Draw(im)
        d.rectangle((950,62,1919,132),fill='white')
        title=('잠깐 안 보여도, 한 일은 지우지 않습니다' if num==13 else
               '관제 화면 하나로 연결부터 작업 진행까지 확인합니다')
        fit_text(d,title,(960,66,886,63),32,align='center')
    if num==13:
        d=ImageDraw.Draw(im)
        fit_text(d,'손이 마커를 가리면 안내가 꺼지고,\n진행 상태도 함께 사라졌습니다.',
                 (138,765,496,78),26,color='#353535')
        fit_text(d,'마커를 잠깐 못 본 상태와 작업 중단을\n구분하지 않고 처리했습니다.',
                 (714,765,496,78),26,color='#353535')
    if num==15:
        d=ImageDraw.Draw(im)
        fit_text(d,'작업 영상, 현재 단계, 다음 행동을\n한 화면에서 확인합니다.\n작업 시작과 종료도 여기서 합니다.',
                 (1374,280,410,122),24,color='#353535',bg=PALE)
        fit_text(d,'안경 카메라와 화면 연결을 확인하고,\n추적이 끊긴 이유를 살펴봅니다.',
                 (1374,652,410,82),24,color='#353535',bg=PALE)
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
    parts=scene['parts'];num=scene['slide']
    maps={2:[0,0,1,1,1,1],3:[0,0,1,2],4:[0,0,1,1,2],
          5:[1,1,1,1,2,2],7:[0,1,2],8:[0,1,2,3],9:[0,1,2,3],
          10:[0,1,2,3],11:[0,1,2,2,3],12:[0,1,2,4,3],
          13:[0,1,2],15:[0,1,1,2],16:[0,1,2,3],17:[0,1,2,2],18:[0,1,1,2]}
    return [parts[min(i,len(parts)-1)]['start'] for i in maps.get(num,range(len(regions)))]

def animate_regions(base,scene,t):
    im=base.copy();num=scene['slide'];rects=REGIONS.get(num,[])
    cues=cue_times(scene,rects)
    # All information remains readable; reveal is brief, never held until narration.
    for i,r in enumerate(rects):
        a=.35*(1-ease((t-.18-i*.10)/.45))
        if a>0:
            crop=base.crop(r)
            bg=Image.new('RGB',crop.size,'white')
            im.paste(Image.blend(crop,bg,a),(r[0],r[1]))
    active=[i for i,start in enumerate(cues) if start<=t]
    if active and num not in (2,5,12,17,18):
        latest=max(cues[i] for i in active)
        for i in active:
            if cues[i]!=latest:continue
            x1,y1,x2,y2=rects[i]
            p=ease((t-cues[i])/.45)
            # A short accent on the existing region, not an extra enclosing card.
            ImageDraw.Draw(im).line((x1,y2+5,x1+min(94,x2-x1)*p,y2+5),fill=ORANGE,width=3)
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
        words=[];cursor=0
        for m in metadata:
            if m['type']!='WordBoundary':continue
            text=m['text'];pos=p['text'].find(text,cursor)
            if pos>=0:
                end=pos+len(text)
                while end<len(p['text']) and p['text'][end] in '.,?!:':end+=1
                text=p['text'][pos:end];cursor=end
            start=p['start']+m['offset']/1e7
            words.append([start,start+m['duration']/1e7,text])
        # Keep technology names together before forming readable phrase captions.
        for spoken,display in DISPLAY_WORDS.items():
            n=len(spoken.split());i=0
            while i+n<=len(words):
                text=' '.join(w[2] for w in words[i:i+n])
                if text.startswith(spoken):
                    words[i:i+n]=[[words[i][0],words[i+n-1][1],display+text[len(spoken):]]]
                i+=1
        group=[]
        for i,word in enumerate(words):
            group.append(word)
            text=' '.join(w[2] for w in group)
            nextlen=len(words[i+1][2])+1 if i+1<len(words) else 0
            stop=(word[2].endswith(('.', '?', '!')) or
                  (word[2].endswith(',') and len(text)>=17) or
                  len(text)+nextlen>42 or word[1]-group[0][0]>4.8 or i==len(words)-1)
            if stop:
                end=min(p['start']+p['duration'],word[1]+.16)
                if i+1<len(words):end=min(end,words[i+1][0])
                cues.append((group[0][0],end,text));group=[]
    return cues

def caption(im,scene,t,cues,offset):
    text=next((text for a,b,text in cues if a<=t<b),'')
    if not text:return
    d=ImageDraw.Draw(im);f=font(32)
    width=d.textlength(text,font=f)
    assert width<1720, (scene['slide'],text,width)
    x=(W-width)/2
    d.rounded_rectangle((x-20,1029,x+width+20,1075),radius=6,fill='#17232e')
    d.text((x,1035),text,font=f,fill='#ffffff')

def apply_special(im,base,scene,t,clips):
    num=scene['slide']
    if num==6:
        q=max([i for i,p in enumerate(scene['parts']) if t>=p['start']] or [0])
        rects=[(114,199,390,493),(525,202,815,465),(880,202,1173,465),
               (525,516,815,776),(1452,160,1795,918)]
        x1,y1,x2,y2=rects[q]
        if t>=scene['parts'][q]['start']:
            p=ease((t-scene['parts'][q]['start'])/.5)
            ImageDraw.Draw(im).line((x1,y2+8,x1+(x2-x1)*p,y2+8),fill=ORANGE,width=3)
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
            d.text((x+7,926),label,font=font(21,True),fill=NAVY)
        fit_text(d,'카메라 시점 재구성 · Unity 출력 사용',(107,631,780,24),17,color='#7c8da6')
    elif num==13:
        src=35+min(8,max(0,t-2))
        paste_fit(im,clips['composite'].get(src),(107,257,635,554))
        d=ImageDraw.Draw(im)
        label='가림 구간 재생' if 2<=t<10 else '가림 구간 화면'
        fit_text(d,label+' · 확인한 진행은 유지',(107,558,528,31),20,color='#7c8da6')
        x=782+(1796-782)*src/121.5
        d.line((x,281,x,500),fill=ORANGE,width=2)
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
    if t<.35 and clips.get('previous') is not None:
        im=Image.blend(clips['previous'],im,ease(t/.35))
    if scene['slide']==1 and t<.7:
        im=Image.blend(Image.new('RGB',(W,H),'black'),im,ease(t/.7))
    if scene['slide']==19 and t>scene['duration']-.7:
        im=Image.blend(Image.new('RGB',(W,H),'black'),im,ease((scene['duration']-t)/.7))
    caption(im,scene,t,cues,offset)
    return im

def static_key(scene,t,cues):
    if scene['slide'] in (12,13,14) or t<2 or t>scene['duration']-.8:return None
    starts=[p['start'] for p in scene['parts']]
    q=max([i for i,v in enumerate(starts) if v<=t] or [0])
    if t-starts[q]<.55:return None
    return q,next((text for a,b,text in cues if a<=t<b),'')

def stamp(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');ap.add_argument('--slides',nargs='*',type=int)
    args=ap.parse_args()
    for name in ('segments','preview'):(ROOT/name).mkdir(exist_ok=True)
    offset=0;allsubs=[];chapters=[];previous=None
    for scene in TIMING:
        num=scene['slide'];length=scene['duration']
        cues=subtitle_cues(scene)
        allsubs.extend((a+offset,b+offset,text) for a,b,text in cues)
        chapters.append(dict(slide=num,title=scene['title'],start=offset,end=offset+length))
        if args.slides and num not in args.slides:offset+=length;continue
        output=ROOT/'segments'/f'{num:02d}.mp4'
        if output.exists() and not args.preview:
            cap=cv2.VideoCapture(str(output))
            cap.set(cv2.CAP_PROP_POS_FRAMES,max(0,int(cap.get(cv2.CAP_PROP_FRAME_COUNT))-1))
            ok,last=cap.read()
            cap.release()
            previous=Image.fromarray(cv2.cvtColor(last,cv2.COLOR_BGR2RGB)) if ok else source_slide(num)
            offset+=length
            continue
        base=source_slide(num);clips={}
        if previous is not None:clips['previous']=previous
        if num in (12,13,14):clips['composite']=Video('06-camera-composite-full.mp4')
        if num==12:clips['sbs']=Video('04-unity-sbs-synchronized.mp4')
        if args.preview:
            for f in (.15,.52,.87):
                t=length*f
                frame(base,scene,t,cues,offset,clips).save(ROOT/'preview'/f'{num:02d}-{int(f*100):02d}.jpg',quality=94)
            for clip in clips.values():
                if isinstance(clip,Video):clip.close()
            previous=frame(base,scene,length-1,cues,offset,{}) if num not in (12,13,14) else base
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
                lastkey=None;raw=None
                for n in range(frames):
                    t=n/FPS
                    key=static_key(scene,t,cues)
                    if key is None or key!=lastkey:
                        im=frame(base,scene,t,cues,offset,clips)
                        raw=im.tobytes()
                    lastkey=key
                    if n==frames//2:im.save(ROOT/'preview'/f'{num:02d}-rendered.jpg',quality=92)
                    proc.stdin.write(raw)
                    if n and n%900==0:print(f'Render {num:02d}: {n/FPS:.0f}/{length:.0f}s',flush=True)
                proc.stdin.close()
                if proc.wait()!=0:raise RuntimeError(error_path.read_text(errors='replace'))
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                previous=im.copy()
                for clip in clips.values():
                    if isinstance(clip,Video):clip.close()
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
