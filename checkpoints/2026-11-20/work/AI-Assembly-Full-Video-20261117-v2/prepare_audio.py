"""Stock male voice with deliberate phrase pauses and nonoverlapping timing."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OLD = ROOT.with_name('AI-Assembly-Full-Video-20261117')
sys.path.insert(0, str(OLD / 'vendor'))
import edge_tts
from storyboard import SCENES, DEMO_STARTS

FF = Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin')
PPT = Path('C:/Users/fresh/OneDrive/Desktop/회사/Claude/AI Assembly Guide_구조테스트_v14.pptx')
VOICE = 'ko-KR-HyunsuMultilingualNeural'
RATE = '+0%'

def duration(path):
    return float(subprocess.check_output([str(FF/'ffprobe.exe'), '-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True))

async def synth(text, voice, path):
    meta=path.with_suffix('.jsonl')
    if not path.exists() or path.stat().st_size<1000:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text,voice,rate=RATE,boundary='WordBoundary').save(str(path),str(meta))
                break
            except Exception:
                if attempt==2: raise
                await asyncio.sleep(2+attempt*2)
    return meta

async def main():
    (ROOT/'audio').mkdir(exist_ok=True)
    sample='같은 나사라도 왼눈과 오른눈에 표시할 위치는 다릅니다. 두 화면이 실물 위에서 하나로 겹치도록, 눈별 좌표를 실시간으로 계산했습니다. 이제 실제 작업 모습을 보겠습니다.'
    for name in ('ko-KR-InJoonNeural',VOICE):
        await synth(sample,name,ROOT/'audio'/f'sample-{name}.mp3')
    if '--samples' in sys.argv:return
    plans=[]
    for num,title,min_duration,paragraphs in SCENES:
        parts=[]
        cursor=.65
        for j,text in enumerate(paragraphs):
            path=ROOT/'audio'/f'{num:02d}-{j:02d}.mp3'
            meta=await synth(text,VOICE,path)
            dur=duration(path)
            start=max(DEMO_STARTS[j]+.5,cursor) if num==14 else cursor
            parts.append(dict(file=str(path),start=start,duration=dur,text=text,metadata=str(meta)))
            cursor=start+dur+.42
            print(f'Voice {num:02d}/{j+1}: {dur:.1f}s',flush=True)
        length=max(min_duration,cursor+.7)
        length=round(length*30)/30
        audio=ROOT/'audio'/f'slide-{num:02d}.wav'
        cmd=[str(FF/'ffmpeg.exe'),'-v','error','-y']
        for part in parts:cmd+=['-i',part['file']]
        filters=[]
        for j,p in enumerate(parts):
            ms=round(p['start']*1000)
            filters.append(f'[{j}:a]highpass=f=65,adelay={ms}|{ms}[a{j}]')
        filters.append(''.join(f'[a{j}]' for j in range(len(parts)))+f'amix=inputs={len(parts)}:normalize=0,apad,atrim=duration={length},loudnorm=I=-17:TP=-1.5:LRA=9[a]')
        cmd+=['-filter_complex',';'.join(filters),'-map','[a]','-ar','48000','-ac','2',str(audio)]
        subprocess.run(cmd,check=True)
        plans.append(dict(slide=num,title=title,duration=length,audio=str(audio),parts=parts))
        (ROOT/'timing.json').write_text(json.dumps(plans,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(source=str(PPT),source_sha256=hashlib.sha256(PPT.read_bytes()).hexdigest(),voice=VOICE,rate=RATE,duration=sum(p['duration'] for p in plans),slides=len(plans))
    (ROOT/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(main())
