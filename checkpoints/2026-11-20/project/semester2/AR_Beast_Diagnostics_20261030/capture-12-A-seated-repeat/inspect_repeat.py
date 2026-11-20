"""Saved-photo contact sheet and unmarked A crops; no camera access."""
from pathlib import Path
import hashlib
import json
from unittest.mock import patch
import cv2
import numpy as np
from server.realtime.camera_calibration import write_json
from server.realtime.workspace_roi_candidate import _save_png

ROOT = Path(__file__).resolve().parent


def main():
    photos = sorted(ROOT.glob('frame-*/raw.png'))
    assert len(photos) == 10
    contact = np.full((1920,1280,3),245,np.uint8)
    valid = []
    hashes = {}
    for index,path in enumerate(photos):
        raw = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        image = cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        state = json.loads((path.parent/'report.json').read_text())
        x,y = index%2*640,index//2*384
        contact[y+24:y+384,x:x+640] = cv2.resize(image,(640,360))
        cv2.putText(contact,f'frame {state["frame_id"]} | {state["status"]}',(x+8,y+18),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1)
        if state['status']=='tracking':
            # Prediction locates the crop only. Manual review is not blind ground truth.
            px,py = np.rint(state['targets']['A']['pixel']).astype(int)
            x0,y0 = int(px//5*5-40),int(py//5*5-35)
            valid.append((state['frame_id'],path,image,(x0,y0,x0+90,y0+85)))
    sheet = np.full((((len(valid)+1)//2)*770,1600,3),245,np.uint8)
    for index,(frame_id,path,image,(x0,y0,x1,y1)) in enumerate(valid):
        ox,oy = index%2*800,index//2*770
        crop = cv2.resize(image[y0:y1,x0:x1],None,fx=8,fy=8,interpolation=cv2.INTER_NEAREST)
        sheet[oy+60:oy+740,ox+65:ox+785] = crop
        cv2.putText(sheet,f'frame {frame_id} | no predicted point drawn',(ox+12,oy+25),cv2.FONT_HERSHEY_SIMPLEX,.55,(20,20,20),1)
        for x in range(x0,x1,10):
            cv2.putText(sheet,str(x),(ox+53+(x-x0)*8,oy+48),cv2.FONT_HERSHEY_SIMPLEX,.4,(20,20,20),1)
        for y in range(y0,y1,5):
            cv2.putText(sheet,str(y),(ox+17,oy+64+(y-y0)*8),cv2.FONT_HERSHEY_SIMPLEX,.4,(20,20,20),1)
    destination = ROOT/'inspection'
    destination.mkdir(exist_ok=False)
    _save_png(destination/'contact.png',contact)
    _save_png(destination/'A-crops.png',sheet)
    write_json(destination/'sources.json',dict(raw_sha256=hashes,inputs=[dict(frame_id=f,source=str(p),crop_xyxy=list(b)) for f,p,im,b in valid]))
    for relative,sha in hashes.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==sha
    print(json.dumps(dict(raw_count=len(photos),valid_saved_frames=[v[0] for v in valid])))


if __name__=='__main__':
    with patch('cv2.VideoCapture',side_effect=AssertionError('Camera forbidden')):
        main()
