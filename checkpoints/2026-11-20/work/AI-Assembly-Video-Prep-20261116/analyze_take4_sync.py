import json
from pathlib import Path
import cv2
import numpy as np
from sync_take4 import SRC, OUT

def read(cap,t):
    cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
    ok,f=cap.read()
    if not ok: raise RuntimeError(t)
    return f

cap=cv2.VideoCapture(str(SRC/'unity-sbs.mp4'))
times=[38,60,80,100,130,142]
def title(f):
    return cv2.resize(cv2.cvtColor(f[50:110,800:1150],cv2.COLOR_BGR2GRAY),(175,30))
templates=[title(read(cap,t)) for t in times]
events=[]
for state,expected in [(2,47.9),(3,70.7),(4,92.6),(5,122.0),(6,140.1)]:
    samples=[]
    for t in np.arange(expected-1,expected+1,.1):
        a=title(read(cap,t))
        scores=[float(np.mean((a.astype(float)-b)**2)) for b in templates]
        samples.append((round(float(t),3),int(np.argmin(scores))+1))
    hits=[t for i,(t,s) in enumerate(samples[:-2]) if s==state and all(x[1]==state for x in samples[i:i+3])]
    events.append({'state':f'S{state}','log_seconds':expected,'unity_seconds':hits[0] if hits else None,'samples':samples})
cap.release()
print(json.dumps(events,indent=2))
(OUT/'sync-analysis.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
