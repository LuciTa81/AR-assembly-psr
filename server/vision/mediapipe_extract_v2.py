from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import cv2
import mediapipe as mp

IMAGE_EXTS={".jpg",".jpeg",".png",".bmp",".webp"}

def parse_args():
    p=argparse.ArgumentParser(description="Extract MediaPipe hands. Saves up to 2 hands per frame.")
    g=p.add_mutually_exclusive_group(required=True); g.add_argument("--session"); g.add_argument("--image-dir")
    p.add_argument("--out",required=True); p.add_argument("--debug-dir",default=None); p.add_argument("--debug-limit",type=int,default=0); p.add_argument("--session-id",default=None)
    p.add_argument("--max-num-hands",type=int,default=2); p.add_argument("--min-detection-confidence",type=float,default=0.5); p.add_argument("--min-tracking-confidence",type=float,default=0.5)
    return p.parse_args()

def collect_images_from_dir(root:Path):
    paths=sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    return [{"frame_id":str(i),"image_path":str(p),"display_path":p.name} for i,p in enumerate(paths,1)]

def collect_images_from_session(session_dir:Path):
    frames_csv=session_dir/"frames.csv"
    if frames_csv.exists():
        rows=[]
        with frames_csv.open("r",encoding="utf-8-sig",newline="") as f:
            for i,row in enumerate(csv.DictReader(f),1):
                fid=str(row.get("frame_id",i)); rel=row.get("image_path","")
                path=session_dir/rel if rel else session_dir/"frames"/f"{int(fid):06d}.jpg"
                rows.append({"frame_id":fid,"image_path":str(path),"display_path":rel or path.name})
        return rows
    frames_dir=session_dir/"frames"
    return collect_images_from_dir(frames_dir if frames_dir.exists() else session_dir)

def frame_stem(fid,image_path):
    try: return f"{int(fid):06d}"
    except Exception: return Path(image_path).stem

def px_landmark(lm,w,h):
    return int(round(lm.x*w)), int(round(lm.y*h)), float(lm.z)

def write_no_hand(writer, session_id, fid, img_path, num_hands=0):
    writer.writerow({"session_id":session_id,"frame_id":fid,"image_path":img_path,"hand_id":-1,"hand_visible":0,"num_hands":num_hands,"handedness":"None","hand_score":0.0,"index_x":-1,"index_y":-1,"index_z":0.0,"wrist_x":-1,"wrist_y":-1,"wrist_z":0.0})

def draw_debug(img, result, path:Path):
    dbg=img.copy(); h,w=dbg.shape[:2]
    if not result.multi_hand_landmarks:
        cv2.putText(dbg,"no hands",(20,40),cv2.FONT_HERSHEY_SIMPLEX,1.0,(0,0,255),2); cv2.imwrite(str(path),dbg); return
    for hand_id, hand in enumerate(result.multi_hand_landmarks):
        lms=hand.landmark; ix,iy,_=px_landmark(lms[8],w,h); wx,wy,_=px_landmark(lms[0],w,h)
        handed="Unknown"; score=0.0
        if result.multi_handedness and hand_id < len(result.multi_handedness):
            cls=result.multi_handedness[hand_id].classification[0]; handed=cls.label; score=cls.score
        cv2.circle(dbg,(ix,iy),8,(0,0,255),-1); cv2.circle(dbg,(wx,wy),8,(255,0,0),-1)
        cv2.putText(dbg,f"id={hand_id} {handed} {score:.2f}",(ix+10,iy),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,0,255),2)
    cv2.imwrite(str(path),dbg)

def main():
    args=parse_args()
    if args.session:
        root=Path(args.session); items=collect_images_from_session(root); session_id=args.session_id or root.name
    else:
        root=Path(args.image_dir); items=collect_images_from_dir(root); session_id=args.session_id or root.name
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    debug_dir=Path(args.debug_dir) if args.debug_dir else None
    if debug_dir: debug_dir.mkdir(parents=True,exist_ok=True)
    fields=["session_id","frame_id","image_path","hand_id","hand_visible","num_hands","handedness","hand_score","index_x","index_y","index_z","wrist_x","wrist_y","wrist_z"]
    total=visible=hand_rows=dbg_count=0
    with mp.solutions.hands.Hands(static_image_mode=True,max_num_hands=args.max_num_hands,min_detection_confidence=args.min_detection_confidence,min_tracking_confidence=args.min_tracking_confidence) as hands, out.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for idx,item in enumerate(items,1):
            total+=1; fid=item["frame_id"]; img=cv2.imread(item["image_path"])
            if img is None:
                write_no_hand(writer,session_id,fid,item["display_path"]); continue
            h,w=img.shape[:2]; result=hands.process(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)); num=len(result.multi_hand_landmarks) if result.multi_hand_landmarks else 0
            if num==0:
                write_no_hand(writer,session_id,fid,item["display_path"])
            else:
                visible+=1
                for hand_id, hand in enumerate(result.multi_hand_landmarks):
                    lms=hand.landmark; ix,iy,iz=px_landmark(lms[8],w,h); wx,wy,wz=px_landmark(lms[0],w,h)
                    handed="Unknown"; score=0.0
                    if result.multi_handedness and hand_id < len(result.multi_handedness):
                        cls=result.multi_handedness[hand_id].classification[0]; handed=cls.label; score=float(cls.score)
                    writer.writerow({"session_id":session_id,"frame_id":fid,"image_path":item["display_path"],"hand_id":hand_id,"hand_visible":1,"num_hands":num,"handedness":handed,"hand_score":round(score,6),"index_x":ix,"index_y":iy,"index_z":round(iz,6),"wrist_x":wx,"wrist_y":wy,"wrist_z":round(wz,6)})
                    hand_rows+=1
            if debug_dir is not None and dbg_count < args.debug_limit:
                draw_debug(img,result,debug_dir/f"{frame_stem(fid,item['image_path'])}_hands_v2_debug.jpg"); dbg_count+=1
            if idx%50==0 or idx==len(items): print(f"[PROGRESS] {idx}/{len(items)}")
    print(f"\n[DONE] output csv: {out}"); print(f"[DONE] total images: {total}"); print(f"[DONE] hand visible frames: {visible}"); print(f"[DONE] total hand rows: {hand_rows}"); print(f"[DONE] debug dir: {debug_dir}")

if __name__=="__main__": main()
