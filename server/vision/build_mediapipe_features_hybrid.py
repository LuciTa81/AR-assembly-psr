from __future__ import annotations

import argparse, csv, re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import cv2, numpy as np, pandas as pd, yaml

SCREW_NAMES=["a","b","c","d"]

def parse_args():
    p=argparse.ArgumentParser(description="Build MediaPipe index-near features with YOLO-hand association and handedness fallback.")
    p.add_argument("--mediapipe-raw",required=True); p.add_argument("--yolo-raw",required=True); p.add_argument("--homography",required=True); p.add_argument("--layout",required=True); p.add_argument("--out",required=True); p.add_argument("--session-id",required=True)
    p.add_argument("--preferred-handedness",default="Right"); p.add_argument("--swap-handedness",action="store_true",help="Swap Left/Right labels only. Coordinates are unchanged.")
    p.add_argument("--association-threshold",type=float,default=140.0); p.add_argument("--near-threshold",type=float,default=120.0); p.add_argument("--workspace-width",type=int,default=800); p.add_argument("--workspace-height",type=int,default=600)
    p.add_argument("--warped-dir",default=None); p.add_argument("--debug-dir",default=None); p.add_argument("--debug-limit",type=int,default=0); p.add_argument("--disable-handedness-fallback",action="store_true")
    return p.parse_args()

def norm_frame_id(v):
    if pd.isna(v): return -1
    m=re.search(r"(\d+)",str(v)); return int(m.group(1)) if m else -1

def swap_lr(x):
    x=str(x)
    return "Right" if x=="Left" else "Left" if x=="Right" else x

def parse_rect(value:Any):
    if isinstance(value,dict):
        if all(k in value for k in ["x","y","w","h"]): return float(value["x"]),float(value["y"]),float(value["w"]),float(value["h"])
        if all(k in value for k in ["x1","y1","x2","y2"]):
            x1,y1,x2,y2=map(float,(value["x1"],value["y1"],value["x2"],value["y2"])); return x1,y1,x2-x1,y2-y1
    if isinstance(value,(list,tuple)) and len(value)==4: return float(value[0]),float(value[1]),float(value[2]),float(value[3])
    raise ValueError(f"Invalid ROI rect: {value}")

def load_centers(layout_path:Path):
    data=yaml.safe_load(layout_path.read_text(encoding="utf-8")); centers={}
    for name in ["screw_a","screw_b","screw_c","screw_d"]:
        x,y,w,h=parse_rect(data["rois"][name]); centers[name.replace("screw_","")] = (x+w/2,y+h/2)
    return centers

def load_homography(path:Path):
    df=pd.read_csv(path); df["frame_id"]=df["frame_id"].apply(norm_frame_id).astype(int)
    if "homography_usable" not in df.columns: df["homography_usable"]=df.get("homography_valid",0)
    if "homography_valid" not in df.columns: df["homography_valid"]=df["homography_usable"]
    if "warp_quality" not in df.columns: df["warp_quality"]=df["homography_usable"].astype(float)
    if "marker_count" not in df.columns: df["marker_count"]=0
    if "homography_source" not in df.columns: df["homography_source"]=""
    return df

def h_from_row(row):
    return np.array([float(row[c]) for c in ["h00","h01","h02","h10","h11","h12","h20","h21","h22"]],dtype=np.float64).reshape(3,3)

def load_mp(path:Path, swap=False):
    if not path.exists() or path.stat().st_size==0: return pd.DataFrame()
    df=pd.read_csv(path)
    if df.empty: return df
    df["frame_id"]=df["frame_id"].apply(norm_frame_id).astype(int)
    if "hand_visible" not in df.columns: df["hand_visible"]=0
    if "handedness" not in df.columns: df["handedness"]="Unknown"
    if swap: df["handedness"]=df["handedness"].apply(swap_lr)
    if "hand_score" not in df.columns: df["hand_score"]=0.0
    for c in ["index_x","index_y","wrist_x","wrist_y"]:
        if c not in df.columns: df[c]=-1.0
    for c in ["hand_visible","hand_score","index_x","index_y","wrist_x","wrist_y"]:
        df[c]=pd.to_numeric(df[c],errors="coerce").fillna(-1.0)
    df["handedness"]=df["handedness"].astype(str)
    return df

def load_yolo(path:Path):
    if not path.exists() or path.stat().st_size==0: return pd.DataFrame()
    df=pd.read_csv(path)
    if df.empty: return df
    df["frame_id"]=df["frame_id"].apply(norm_frame_id).astype(int)
    for c in ["confidence","x1","y1","x2","y2"]:
        df[c]=pd.to_numeric(df[c],errors="coerce").fillna(0.0)
    return df

def valid_hands(hands):
    if hands is None or hands.empty: return pd.DataFrame()
    return hands[(hands["hand_visible"]>0)&(hands["index_x"]>=0)&(hands["index_y"]>=0)].copy()

def pick_yolo(dets):
    if dets is None or dets.empty: return None
    return dets.sort_values("confidence",ascending=False).iloc[0]

def point_to_bbox_distance(x,y,bbox):
    x1,y1,x2,y2=bbox; dx=max(x1-x,0.0,x-x2); dy=max(y1-y,0.0,y-y2); return float(np.sqrt(dx*dx+dy*dy))

def hand_to_tool_distance(hand,yolo):
    bbox=(float(yolo["x1"]),float(yolo["y1"]),float(yolo["x2"]),float(yolo["y2"]))
    d_idx=point_to_bbox_distance(float(hand["index_x"]),float(hand["index_y"]),bbox)
    wx,wy=float(hand.get("wrist_x",-1)),float(hand.get("wrist_y",-1))
    return min(d_idx, point_to_bbox_distance(wx,wy,bbox)) if wx>=0 and wy>=0 else d_idx

def select_hand(hands,yolo,preferred,assoc_thresh,disable_fallback):
    cand=valid_hands(hands)
    if cand.empty: return None,"none",-1.0
    if yolo is not None:
        scored=sorted([(hand_to_tool_distance(row,yolo),row) for _,row in cand.iterrows()], key=lambda x:x[0])
        dist,row=scored[0]
        if dist <= assoc_thresh: return row,"yolo_association",float(dist)
        if disable_fallback: return None,"none_yolo_unmatched",float(dist)
    if not disable_fallback:
        pref=cand[cand["handedness"].str.lower()==preferred.lower()].copy()
        if not pref.empty: return pref.sort_values("hand_score",ascending=False).iloc[0],"handedness_fallback",-1.0
    return None,"none",-1.0

def transform_point(H,x,y):
    pts=np.array([[[x,y]]],dtype=np.float32); out=cv2.perspectiveTransform(pts,H); return float(out[0,0,0]),float(out[0,0,1])

def inside(x,y,w,h): return 0<=x<w and 0<=y<h

def draw_debug(wp,out_path,index,centers,row):
    img=cv2.imread(str(wp));
    if img is None: return
    for k,c in centers.items():
        x,y=int(round(c[0])),int(round(c[1])); cv2.circle(img,(x,y),8,(0,255,255),2); cv2.putText(img,k.upper(),(x+8,y-8),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,255),2)
    if index is not None:
        x,y=int(round(index[0])),int(round(index[1])); cv2.circle(img,(x,y),10,(0,0,255),-1); cv2.putText(img,"index",(x+10,y),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)
    text=f"src={row['selected_hand_source']} hand={row['selected_handedness']} near={row['chosen_screw']}"
    cv2.putText(img,text,(20,30),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,0,255),2)
    out_path.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(out_path),img)

def main():
    args=parse_args(); centers=load_centers(Path(args.layout)); hdf=load_homography(Path(args.homography)); mpdf=load_mp(Path(args.mediapipe_raw),args.swap_handedness); ydf=load_yolo(Path(args.yolo_raw))
    mpg={int(fid):g.copy() for fid,g in mpdf.groupby("frame_id")} if not mpdf.empty else {}; yg={int(fid):g.copy() for fid,g in ydf.groupby("frame_id")} if not ydf.empty else {}
    warped_dir=Path(args.warped_dir) if args.warped_dir else None; debug_dir=Path(args.debug_dir) if args.debug_dir else None
    rows=[]; dbg=0
    for _,hr in hdf.sort_values("frame_id").iterrows():
        fid=int(hr["frame_id"]); hands=mpg.get(fid,pd.DataFrame()); yolo=pick_yolo(yg.get(fid,pd.DataFrame()))
        sel,src,dist=select_hand(hands,yolo,args.preferred_handedness,args.association_threshold,args.disable_handedness_fallback)
        usable=int(str(hr.get("homography_usable","0"))=="1"); valid=int(str(hr.get("homography_valid","0"))=="1")
        row={"session_id":args.session_id,"frame_id":fid,"hand_visible":int((hands["hand_visible"]>0).any()) if not hands.empty and "hand_visible" in hands else 0,
             "selected_hand_visible":1 if sel is not None else 0,"selected_hand_source":src,"selected_handedness":"None","selected_hand_score":0.0,"selected_hand_to_tool_dist":round(float(dist),3),
             "yolo_tool_visible":1 if yolo is not None else 0,"yolo_tool_confidence":round(float(yolo["confidence"]),6) if yolo is not None else 0.0,
             "homography_valid":valid,"homography_usable":usable,"homography_source":hr.get("homography_source",""),"marker_count":hr.get("marker_count",0),"warp_quality":round(float(hr.get("warp_quality",0.0) or 0.0),6),
             "index_inside_workspace":0,"index_x_warped":-1.0,"index_y_warped":-1.0,"index_dist_a":-1.0,"index_dist_b":-1.0,"index_dist_c":-1.0,"index_dist_d":-1.0,
             "index_near_a":0,"index_near_b":0,"index_near_c":0,"index_near_d":0,"chosen_screw":"none"}
        idx_point=None
        if sel is not None:
            row["selected_handedness"]=str(sel.get("handedness","Unknown")); row["selected_hand_score"]=round(float(sel.get("hand_score",0.0)),6)
        if sel is not None and usable==1:
            xw,yw=transform_point(h_from_row(hr),float(sel["index_x"]),float(sel["index_y"])); row["index_x_warped"]=round(xw,3); row["index_y_warped"]=round(yw,3); idx_point=(xw,yw)
            if inside(xw,yw,args.workspace_width,args.workspace_height):
                row["index_inside_workspace"]=1; dists={k:float(np.linalg.norm(np.array([xw,yw])-np.array(c))) for k,c in centers.items()}
                for k,d in dists.items(): row[f"index_dist_{k}"]=round(d,3)
                chosen=min(dists,key=dists.get)
                if dists[chosen] <= args.near_threshold: row[f"index_near_{chosen}"]=1; row["chosen_screw"]=chosen
        rows.append(row)
        if debug_dir is not None and dbg<args.debug_limit and warped_dir is not None:
            wp=warped_dir/f"{fid:06d}_warped.jpg"
            if wp.exists(): draw_debug(wp,debug_dir/f"{fid:06d}_mediapipe_hybrid_debug.jpg",idx_point,centers,row); dbg+=1
    fields=["session_id","frame_id","hand_visible","selected_hand_visible","selected_hand_source","selected_handedness","selected_hand_score","selected_hand_to_tool_dist","yolo_tool_visible","yolo_tool_confidence","homography_valid","homography_usable","homography_source","marker_count","warp_quality","index_inside_workspace","index_x_warped","index_y_warped","index_dist_a","index_dist_b","index_dist_c","index_dist_d","index_near_a","index_near_b","index_near_c","index_near_d","chosen_screw"]
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"[DONE] saved: {out}"); print(f"[DONE] rows: {len(rows)}"); print(f"[DONE] hand visible frames: {sum(r['hand_visible'] for r in rows)}"); print(f"[DONE] selected hand frames: {sum(r['selected_hand_visible'] for r in rows)}"); print(f"[DONE] index inside workspace frames: {sum(r['index_inside_workspace'] for r in rows)}")
    for k in SCREW_NAMES: print(f"[DONE] index near {k.upper()}: {sum(r[f'index_near_{k}'] for r in rows)}")
    if debug_dir is not None: print(f"[DONE] debug dir: {debug_dir}")

if __name__=="__main__": main()
