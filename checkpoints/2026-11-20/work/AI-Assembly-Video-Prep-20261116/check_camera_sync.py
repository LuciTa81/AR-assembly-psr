import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).parent
SRC = ROOT / 'recordings/20261116_034830_linefix-take4'
OUT = ROOT / 'edited/take4-sync'
cap = cv2.VideoCapture(str(SRC / 'camera-preview.mp4'))
points = [(574,326),(798,317),(566,520),(836,514)]
results = []
for expected, target in [(47.9,0),(70.7,1),(92.6,2),(122.0,3),(140.1,-1)]:
    samples = []
    for t in np.arange(expected-.8, expected+.6, .1):
        cap.set(cv2.CAP_PROP_POS_MSEC, round(t*1000))
        ok, f = cap.read()
        if not ok: continue
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, (18,150,150), (40,255,255))
        scores = [int(np.count_nonzero(yellow[y-40:y+30,x-35:x+40])) for x,y in points]
        winner = int(np.argmax(scores)) if max(scores)>100 else -1
        samples.append({'t':round(float(t),2),'target':winner,'scores':scores})
    event = next((s['t'] for i,s in enumerate(samples[:-2]) if all(v['target']==target for v in samples[i:i+3])),None)
    results.append({'log':expected,'target':target,'camera':event,'samples':samples})
cap.release()
(OUT/'camera-sync-analysis.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
