import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).parent
SRC = ROOT / 'recordings/20261116_034830_linefix-take4'
OUT = ROOT / 'edited/take4-sync'
OUT.mkdir(exist_ok=True)
rows = [json.loads(line) for line in (SRC / 'states.jsonl').open(encoding='utf-8')]
transitions = [(r['video_seconds'], r['state']['current_state']) for i,r in enumerate(rows) if i == 0 or r['state']['current_state'] != rows[i-1]['state']['current_state']]
print(transitions)
for name in ['camera-preview','unity-sbs']:
    cap=cv2.VideoCapture(str(SRC/(name+'.mp4')))
    for sec in [65,69,71,88,90,93,119,121,123,138,140]:
        cap.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
        ok,frame=cap.read()
        if ok:
            if name=='unity-sbs': frame=frame[:,:1920]
            cv2.imwrite(str(OUT/f'{name}-{sec}.jpg'),frame)
    cap.release()
print('Diagnostic frames extracted')
