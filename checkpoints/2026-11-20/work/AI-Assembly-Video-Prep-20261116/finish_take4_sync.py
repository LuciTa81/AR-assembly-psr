import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from render_take4_sync import SRC, OUT, run, composite_sample


def inspect_events():
    cap=cv2.VideoCapture(str(SRC/'unity-sbs.mp4'))
    def title(f):
        return cv2.resize(cv2.cvtColor(f[50:110,800:1150],cv2.COLOR_BGR2GRAY),(175,30)).astype(float)
    templates=[]
    for t in [38,60,80,100,130,142]:
        cap.set(cv2.CAP_PROP_POS_FRAMES,round(t*30))
        ok,f=cap.read()
        assert ok
        templates.append(title(f))
    camera=json.loads((OUT/'camera-sync-analysis.json').read_text())
    result=[]
    for idx,expected in enumerate([47.9,70.7,92.6,122.0,140.1]):
        start=round((expected-.7)*30)
        cap.set(cv2.CAP_PROP_POS_FRAMES,start)
        hits=[]
        for frame in range(start,start+30):
            ok,f=cap.read()
            assert ok
            a=title(f)
            state=int(np.argmin([np.mean((a-b)**2) for b in templates]))+1
            hits.append((frame,state))
        event=next(frame/30 for i,(frame,state) in enumerate(hits[:-2]) if state==idx+2 and all(s==state for _,s in hits[i:i+3]))
        cam=next(s['t'] for s in camera[idx]['samples'] if s['target']==camera[idx]['target'])
        result.append({'state':f'S{idx+2}','camera_seconds':cam,'unity_seconds':round(event,4),'offset_seconds':round(cam-event,4),'residual_after_0_3s_shift':round(cam-event-.3,4)})
    cap.release()
    (OUT/'verified-transitions.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


def aligned_tracks():
    for name, vf in [('03-unity-left-synchronized.mp4','crop=1920:1080:0:0'),('04-unity-sbs-synchronized.mp4',None)]:
        args=['-ss','20.7','-i',str(SRC/'unity-sbs.mp4'),'-t','121.5','-an']
        if vf: args+=['-vf',vf]
        args+=['-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/name)]
        run(args,name+'.log')
        print(name,flush=True)


def verify():
    result=[]
    for p in sorted(OUT.glob('*.mp4')):
        cap=cv2.VideoCapture(str(p))
        fps=cap.get(cv2.CAP_PROP_FPS)
        count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        info={'name':p.name,'fps':fps,'frames':count,'duration':count/fps,'width':int(cap.get(3)),'height':int(cap.get(4)),'bytes':p.stat().st_size}
        for pos in [0,count//4,count//2,3*count//4,count-1]:
            cap.set(cv2.CAP_PROP_POS_FRAMES,pos)
            ok,f=cap.read()
            assert ok,(p,pos)
            assert float(f.std())>5,(p,pos,'blank')
            if pos==count//2: cv2.imwrite(str(OUT/(p.stem+'-preview.jpg')),f)
        cap.release()
        info['sample_decode']='passed 5 frames including final frame'
        result.append(info)
    (OUT/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    inspect_events()
    composite_sample()
    aligned_tracks()
    verify()
