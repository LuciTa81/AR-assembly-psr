"""문장 조각마다 받아쓰기 → 대본 글자와 비교 (앞/뒤 글자가 잘리거나 넘쳤는지)"""
import sys, json, os, re, difflib, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
R=json.load(open('lines_read.json')); want=set(sys.argv[1:])
m=WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4)
res=json.load(open('verify.json')) if os.path.exists('verify.json') else {}
h=lambda s: re.sub(r'[^가-힣]','',s)
for sc,k,orig,read,*_ in R:
    if want and sc not in want: continue
    f=f'clips/{sc}_{k}.wav'
    if not os.path.exists(f): continue
    x,sr=sf.read(f,dtype='float32'); x=x[::3]  # 48k → 16k
    segs,_=m.transcribe(x, language='ko', beam_size=1, vad_filter=False, condition_on_previous_text=False)
    txt=''.join(s.text for s in segs)
    r=difflib.SequenceMatcher(None,h(read),h(txt)).ratio()
    res[f'{sc}_{k}']=dict(txt=txt.strip(), ratio=round(r,2), head=h(read)[:2]==h(txt)[:2], tail=h(read)[-2:]==h(txt)[-2:])
    json.dump(res,open('verify.json','w'),ensure_ascii=False,indent=0)
    print(f'{sc}_{k} {r:.2f} {res[f"{sc}_{k}"]["head"]} {res[f"{sc}_{k}"]["tail"]} | {txt.strip()}', flush=True)
