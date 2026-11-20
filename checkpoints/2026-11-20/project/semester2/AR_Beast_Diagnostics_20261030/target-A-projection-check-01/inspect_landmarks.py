"""Unprojected saved-photo crops for approximate A-landmark inspection."""
from pathlib import Path
import hashlib
import cv2
import numpy as np
from server.realtime.camera_calibration import write_json
from server.realtime.workspace_roi_candidate import _save_png

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
SOURCES=[
    ('closed07-051', BASE/'capture-07-live-roi/frame-000051/raw.png', (575,355,665,440)),
    ('closed07-076', BASE/'capture-07-live-roi/frame-000076/raw.png', (575,350,665,435)),
    ('closed07-101', BASE/'capture-07-live-roi/frame-000101/raw.png', (550,360,640,445)),
    ('closed09-039', BASE/'capture-09-lid-closed/frame-000039/raw.png', (575,335,665,420)),
]

def main():
    panel_w,panel_h,scale=800,770,8
    sheet=np.full((panel_h*2,panel_w*2,3),245,np.uint8)
    inputs=[]
    for i,(name,path,box) in enumerate(SOURCES):
        data=path.read_bytes()
        im=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
        assert im.shape[:2]==(720,1280)
        x0,y0,x1,y1=box
        crop=cv2.resize(im[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
        ox,oy=(i%2)*panel_w,(i//2)*panel_h
        left,top=ox+65,oy+60
        sheet[top:top+crop.shape[0],left:left+crop.shape[1]]=crop
        cv2.putText(sheet,name+' | raw pixel ruler, no prediction',(ox+15,oy+25),cv2.FONT_HERSHEY_SIMPLEX,.55,(15,15,15),1,cv2.LINE_AA)
        for x in range(x0,x1,5):
            px=left+(x-x0)*scale
            cv2.line(sheet,(px,top-5),(px,top),(50,50,50),1)
            if x%10==0:
                cv2.putText(sheet,str(x),(px-12,top-12),cv2.FONT_HERSHEY_SIMPLEX,.4,(20,20,20),1,cv2.LINE_AA)
        for y in range(y0,y1,5):
            py=top+(y-y0)*scale
            cv2.line(sheet,(left-5,py),(left,py),(50,50,50),1)
            cv2.putText(sheet,str(y),(ox+17,py+4),cv2.FONT_HERSHEY_SIMPLEX,.4,(20,20,20),1,cv2.LINE_AA)
        inputs.append(dict(name=name,path=str(path),sha256=hashlib.sha256(data).hexdigest(),crop_xyxy=list(box)))
    _save_png(ROOT/'landmark-crops.png',sheet)
    write_json(ROOT/'sources.json',dict(scope='visual approximation, not ground truth',inputs=inputs))
    print('Saved four unprojected crops; source photos unchanged.')

if __name__=='__main__':
    main()

