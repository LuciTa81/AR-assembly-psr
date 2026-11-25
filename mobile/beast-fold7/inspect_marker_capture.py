"""Read-only capture audit and pixel-coordinate inspection sheets."""
import json
from collections import Counter
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parent/'pose-comparison/workbench-capture-20261121'


def read_image(path):
    image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape!=(720,1280,3):
        raise ValueError(f'Invalid full-resolution image: {path}')
    return image


def write_image(path,image):
    assert not path.exists(),path
    ok,encoded=cv2.imencode('.png',image)
    assert ok
    encoded.tofile(path)


def annotate(image,row):
    image=image.copy()
    for key,quad in row['corners'].items():
        points=np.rint(quad).astype(np.int32)
        cv2.polylines(image,[points],True,(0,255,255),1,cv2.LINE_AA)
        for point in points:
            cv2.drawMarker(image,tuple(point),(255,0,255),cv2.MARKER_CROSS,7,1)
        cv2.putText(image,key,tuple(points[0]-[0,7]),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,255),1,cv2.LINE_AA)
    return image


def main():
    output=ROOT/'inspection-v2'
    output.mkdir(exist_ok=False)
    summaries=[]
    for run in sorted(ROOT.glob('marker-*')):
        if not run.is_dir():continue
        rows=[]
        for path in sorted(run.glob('*.json')):
            row=json.loads(path.read_bytes())
            assert Path(row['image']).name==row['image']
            image=read_image(run/row['image'])
            assert row['width']==1280 and row['height']==720
            for quad in row['corners'].values():
                assert np.array(quad).shape==(4,2) and np.isfinite(quad).all()
            rows.append(row)
        orphan=[p.name for p in run.glob('*.png') if not p.with_suffix('.json').exists()]
        # Read orphan images only to determine whether transfer was complete; no pose inference.
        incomplete=[]
        for name in orphan:
            try:read_image(run/name)
            except ValueError:incomplete.append(name)
        summaries.append(dict(run=run.name,photos=len(list(run.glob('*.png'))),paired=len(rows),
            orphan_images=orphan,incomplete_images=incomplete,sessions=dict(Counter(r['session'] for r in rows)),
            reasons=dict(Counter(r['reason'] for r in rows)),
            combinations=dict(Counter(','.join(sorted(r['corners'],key=int)) for r in rows))))
        for start in range(0,len(rows),12):
            sheet=np.full((3*300,4*480,3),24,np.uint8)
            for index,row in enumerate(rows[start:start+12]):
                image=annotate(read_image(run/row['image']),row)
                if row['corners']:
                    points=np.concatenate(list(row['corners'].values()))
                    x0,y0=np.maximum(np.floor(points.min(axis=0)-35).astype(int),0)
                    x1,y1=np.minimum(np.ceil(points.max(axis=0)+35).astype(int),[1280,720])
                    image=image[y0:y1,x0:x1]
                scale=min(480/image.shape[1],260/image.shape[0])
                small=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
                x=(index%4)*480;y=(index//4)*300
                sheet[y+40:y+40+small.shape[0],x:x+small.shape[1]]=small
                label=f"{row['image']} ids={','.join(row['corners'])} {row['reason']}"
                cv2.putText(sheet,label[:61],(x+3,y+18),cv2.FONT_HERSHEY_SIMPLEX,.36,(230,230,230),1,cv2.LINE_AA)
                if row['rms'] is not None:
                    cv2.putText(sheet,f"RMS={row['rms']:.3f}px",(x+3,y+34),cv2.FONT_HERSHEY_SIMPLEX,.4,(230,230,230),1)
            write_image(output/f'{run.name}-{start//12+1}.png',sheet)
        # Two raw/annotated close-ups per marker at several stages, without perspective warping.
        selected=sorted(set([0,len(rows)//4,len(rows)//2,3*len(rows)//4,len(rows)-1]))
        for index in selected:
            row=rows[index];raw=read_image(run/row['image']);marked=annotate(raw,row)
            panels=[]
            for key in ('4','5'):
                if key not in row['corners']:continue
                quad=np.array(row['corners'][key])
                x0,y0=np.maximum(np.floor(quad.min(axis=0)-12).astype(int),0)
                x1,y1=np.minimum(np.ceil(quad.max(axis=0)+12).astype(int),[1280,720])
                pair=np.hstack([raw[y0:y1,x0:x1],marked[y0:y1,x0:x1]])
                pair=cv2.resize(pair,None,fx=3,fy=3,interpolation=cv2.INTER_NEAREST)
                canvas=np.full((pair.shape[0]+30,pair.shape[1],3),24,np.uint8)
                canvas[30:]=pair
                cv2.putText(canvas,f"{row['image']} ID{key} raw | detected",(8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(240,240,240),1)
                write_image(output/f'{run.name}-{index+1:04d}-id{key}.png',canvas)
    report=dict(runs=summaries,total_photos=sum(r['photos'] for r in summaries),
        total_paired=sum(r['paired'] for r in summaries),camera_shape=[1280,720])
    assert report['total_photos']<=100
    (output/'inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
