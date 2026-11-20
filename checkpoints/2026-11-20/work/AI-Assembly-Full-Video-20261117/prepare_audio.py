import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
import edge_tts
from storyboard import SCENES, DEMO_STARTS

FF = Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin')
PPT = Path('C:/Users/fresh/OneDrive/Desktop/회사/Claude/AI Assembly Guide_구조테스트_v14.pptx')
VOICE = 'ko-KR-InJoonNeural'

def duration(path):
    return float(subprocess.check_output([str(FF/'ffprobe.exe'), '-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True))

async def main():
    (ROOT/'audio').mkdir(exist_ok=True)
    plans=[]
    for num,title,min_duration,paragraphs in SCENES:
        parts=[]
        cursor=1.0
        for j,text in enumerate(paragraphs):
            path=ROOT/'audio'/f'{num:02d}-{j:02d}.mp3'
            meta=path.with_suffix('.jsonl')
            if not path.exists() or path.stat().st_size<1000:
                for attempt in range(3):
                    try:
                        await edge_tts.Communicate(text,VOICE,rate='+4%',boundary='SentenceBoundary').save(str(path),str(meta))
                        break
                    except Exception:
                        if attempt==2: raise
                        await asyncio.sleep(2+attempt*2)
            dur=duration(path)
            start = DEMO_STARTS[j]+1 if num==14 else cursor
            parts.append(dict(file=str(path),start=start,duration=dur,text=text,metadata=str(meta)))
            cursor=start+dur+.65
            print(f'Voice {num:02d}/{j+1}: {dur:.1f}s',flush=True)
        length=max(min_duration,cursor+1.2)
        length=round(length*30)/30
        audio=ROOT/'audio'/f'slide-{num:02d}.wav'
        cmd=[str(FF/'ffmpeg.exe'),'-v','error','-y']
        for part in parts:cmd+=['-i',part['file']]
        filters=[]
        for j,p in enumerate(parts):
            ms=round(p['start']*1000)
            filters.append(f'[{j}:a]adelay={ms}|{ms}[a{j}]')
        filters.append(''.join(f'[a{j}]' for j in range(len(parts)))+f'amix=inputs={len(parts)}:normalize=0,apad,atrim=duration={length},loudnorm=I=-17:TP=-1.5:LRA=7[a]')
        cmd+=['-filter_complex',';'.join(filters),'-map','[a]','-ar','48000','-ac','2',str(audio)]
        subprocess.run(cmd,check=True)
        plans.append(dict(slide=num,title=title,duration=length,audio=str(audio),parts=parts))
        (ROOT/'timing.json').write_text(json.dumps(plans,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(source=str(PPT),source_sha256=hashlib.sha256(PPT.read_bytes()).hexdigest(),voice=VOICE,rate='+4%',duration=sum(p['duration'] for p in plans),slides=len(plans))
    (ROOT/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(main())
