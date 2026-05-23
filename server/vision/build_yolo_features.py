from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
import yaml

SCREW_NAMES = ["a", "b", "c", "d"]


def parse_args():
    p = argparse.ArgumentParser(description="Project YOLO driver bbox to warped workspace and build tool_near features.")
    p.add_argument("--yolo-raw", required=True)
    p.add_argument("--homography", required=True)
    p.add_argument("--layout", required=True, help="ROI layout yaml with screw_a~d rectangles")
    p.add_argument("--out", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--near-threshold", type=float, default=100.0)
    p.add_argument("--distance-mode", choices=["polygon", "center", "tip"], default="polygon",
                   help="polygon=distance from screw to bbox polygon, center=bbox center, tip=oriented-box endpoint proxy")
    p.add_argument("--workspace-width", type=int, default=800)
    p.add_argument("--workspace-height", type=int, default=600)
    p.add_argument("--warped-dir", default=None)
    p.add_argument("--debug-dir", default=None)
    p.add_argument("--debug-limit", type=int, default=0)
    return p.parse_args()


def norm_frame_id(v) -> int:
    if pd.isna(v): return -1
    m = re.search(r"(\d+)", str(v))
    return int(m.group(1)) if m else -1


def parse_rect(value: Any) -> Tuple[float,float,float,float]:
    if isinstance(value, dict):
        if all(k in value for k in ["x","y","w","h"]):
            return float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])
        if all(k in value for k in ["x1","y1","x2","y2"]):
            x1,y1,x2,y2 = map(float, (value["x1"],value["y1"],value["x2"],value["y2"]))
            return x1,y1,x2-x1,y2-y1
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return float(value[0]), float(value[1]), float(value[2]), float(value[3])
    raise ValueError(f"Invalid ROI rect: {value}")


def load_screw_centers(layout_path: Path) -> Dict[str, Tuple[float,float]]:
    data = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
    if not data or "rois" not in data:
        raise ValueError(f"Invalid ROI layout: {layout_path}")
    centers = {}
    for name in ["screw_a","screw_b","screw_c","screw_d"]:
        if name not in data["rois"]:
            raise ValueError(f"Missing ROI in layout: {name}")
        x,y,w,h = parse_rect(data["rois"][name])
        centers[name.replace("screw_","")] = (x+w/2.0, y+h/2.0)
    return centers


def load_homography(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["frame_id"] = df["frame_id"].apply(norm_frame_id).astype(int)
    for c in ["h00","h01","h02","h10","h11","h12","h20","h21","h22"]:
        if c not in df.columns: raise ValueError(f"homography CSV missing column: {c}")
    if "homography_usable" not in df.columns:
        df["homography_usable"] = df.get("homography_valid", 0)
    if "homography_valid" not in df.columns:
        df["homography_valid"] = df["homography_usable"]
    if "warp_quality" not in df.columns: df["warp_quality"] = df["homography_usable"].astype(float)
    if "marker_count" not in df.columns: df["marker_count"] = 0
    if "homography_source" not in df.columns: df["homography_source"] = ""
    return df


def h_from_row(row) -> np.ndarray:
    return np.array([float(row[c]) for c in ["h00","h01","h02","h10","h11","h12","h20","h21","h22"]], dtype=np.float64).reshape(3,3)


def load_yolo_raw(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["frame_id","class","confidence","x1","y1","x2","y2"])
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["frame_id","class","confidence","x1","y1","x2","y2"])
    df["frame_id"] = df["frame_id"].apply(norm_frame_id).astype(int)
    for c in ["confidence","x1","y1","x2","y2"]:
        if c not in df.columns: raise ValueError(f"YOLO raw CSV missing column: {c}")
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    if "class" not in df.columns: df["class"] = "driver"
    return df


def transform_points(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(pts.reshape(-1,1,2).astype(np.float32), H).reshape(-1,2).astype(np.float32)


def make_bbox_points(row) -> np.ndarray:
    x1,y1,x2,y2 = map(float, (row["x1"],row["y1"],row["x2"],row["y2"]))
    return np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], dtype=np.float32)


def polygon_intersects_workspace(poly, width, height) -> bool:
    if poly is None or len(poly)==0: return False
    if np.any((poly[:,0] >= 0) & (poly[:,0] < width) & (poly[:,1] >= 0) & (poly[:,1] < height)): return True
    x0,x1,y0,y1 = float(np.min(poly[:,0])), float(np.max(poly[:,0])), float(np.min(poly[:,1])), float(np.max(poly[:,1]))
    return not (x1 < 0 or y1 < 0 or x0 >= width or y0 >= height)


def dist_point_to_segment(p,a,b):
    ab=b-a; denom=float(np.dot(ab,ab))
    if denom<=1e-8: return float(np.linalg.norm(p-a))
    t=max(0.0,min(1.0,float(np.dot(p-a,ab)/denom)))
    return float(np.linalg.norm(p-(a+t*ab)))


def dist_point_to_polygon(point, polygon) -> float:
    p=np.array(point,dtype=np.float32); poly=polygon.astype(np.float32)
    if len(poly)>=3 and cv2.pointPolygonTest(poly.reshape(-1,1,2), (float(p[0]),float(p[1])), False)>=0:
        return 0.0
    return min(dist_point_to_segment(p, poly[i], poly[(i+1)%len(poly)]) for i in range(len(poly)))


def long_axis_endpoints(poly: np.ndarray):
    # Estimate two long-axis endpoints from minAreaRect. Used as driver-tip proxy candidates.
    rect = cv2.minAreaRect(poly.astype(np.float32))
    box = cv2.boxPoints(rect).astype(np.float32)
    # side lengths in cyclic order
    lens = [np.linalg.norm(box[(i+1)%4]-box[i]) for i in range(4)]
    i = int(np.argmax(lens))
    # long sides: i and i+2; endpoints are their midpoints
    mid1 = (box[i] + box[(i+1)%4]) / 2.0
    j = (i + 2) % 4
    mid2 = (box[j] + box[(j+1)%4]) / 2.0
    return mid1, mid2


def distances(mode: str, poly: np.ndarray, centers: Dict[str, Tuple[float,float]]):
    center = np.mean(poly, axis=0)
    if mode == "center":
        return {k: float(np.linalg.norm(center - np.array(v,dtype=np.float32))) for k,v in centers.items()}, center
    if mode == "tip":
        e1,e2 = long_axis_endpoints(poly)
        # choose endpoint closer to any screw as tip proxy
        min1 = min(np.linalg.norm(e1-np.array(v,dtype=np.float32)) for v in centers.values())
        min2 = min(np.linalg.norm(e2-np.array(v,dtype=np.float32)) for v in centers.values())
        tip = e1 if min1 <= min2 else e2
        return {k: float(np.linalg.norm(tip - np.array(v,dtype=np.float32))) for k,v in centers.items()}, tip
    # polygon distance
    return {k: dist_point_to_polygon(v, poly) for k,v in centers.items()}, center


def pick_best(dets):
    if dets is None or dets.empty: return None
    return dets.sort_values("confidence", ascending=False).iloc[0]


def draw_debug(warped_path: Path, out_path: Path, poly, tip, centers, row):
    img = cv2.imread(str(warped_path))
    if img is None: return
    for k,c in centers.items():
        x,y = map(lambda z:int(round(z)), c)
        cv2.circle(img,(x,y),8,(0,255,255),2); cv2.putText(img,k.upper(),(x+8,y-8),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,255),2)
    if poly is not None:
        cv2.polylines(img,[np.round(poly).astype(np.int32).reshape(-1,1,2)],True,(0,0,255),2)
    if tip is not None:
        x,y=int(round(float(tip[0]))),int(round(float(tip[1]))); cv2.circle(img,(x,y),8,(255,0,0),-1); cv2.putText(img,"tip/center",(x+8,y),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,0,0),2)
    cv2.putText(img,f"near={row['chosen_screw']} conf={row['tool_confidence']}",(20,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,255),2)
    out_path.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(out_path),img)


def main():
    args=parse_args()
    centers=load_screw_centers(Path(args.layout)); hdf=load_homography(Path(args.homography)); ydf=load_yolo_raw(Path(args.yolo_raw))
    ygroups={int(fid):g.copy() for fid,g in ydf.groupby("frame_id")} if not ydf.empty else {}
    warped_dir=Path(args.warped_dir) if args.warped_dir else None; debug_dir=Path(args.debug_dir) if args.debug_dir else None
    rows=[]; debug_count=0
    for _,hrow in hdf.sort_values("frame_id").iterrows():
        fid=int(hrow["frame_id"]); dets=ygroups.get(fid,pd.DataFrame()); best=pick_best(dets)
        usable = int(str(hrow.get("homography_usable","0")) == "1")
        valid = int(str(hrow.get("homography_valid","0")) == "1")
        out={"session_id":args.session_id,"frame_id":fid,"tool_visible":1 if best is not None else 0,
             "tool_confidence":round(float(best["confidence"]),6) if best is not None else 0.0,
             "tool_detection_count":int(len(dets)),"homography_valid":valid,"homography_usable":usable,
             "homography_source":hrow.get("homography_source",""),"marker_count":hrow.get("marker_count",0),"warp_quality":round(float(hrow.get("warp_quality",0.0) or 0.0),6),
             "tool_inside_workspace":0,"tool_x":-1.0,"tool_y":-1.0,"tool_tip_x":-1.0,"tool_tip_y":-1.0,
             "tool_dist_a":-1.0,"tool_dist_b":-1.0,"tool_dist_c":-1.0,"tool_dist_d":-1.0,
             "tool_near_a":0,"tool_near_b":0,"tool_near_c":0,"tool_near_d":0,"chosen_screw":"none"}
        poly=None; tip=None
        if best is not None and usable==1:
            H=h_from_row(hrow); poly=transform_points(H,make_bbox_points(best)); center=np.mean(poly,axis=0)
            out["tool_x"],out["tool_y"] = round(float(center[0]),3),round(float(center[1]),3)
            inside=polygon_intersects_workspace(poly,args.workspace_width,args.workspace_height); out["tool_inside_workspace"]=1 if inside else 0
            if inside:
                dists, tip = distances(args.distance_mode, poly, centers)
                if args.distance_mode != "tip":
                    # still expose representative point as tip_x/y for debugging
                    tip = center
                out["tool_tip_x"],out["tool_tip_y"] = round(float(tip[0]),3),round(float(tip[1]),3)
                for k,d in dists.items():
                    out[f"tool_dist_{k}"] = round(float(d),3)
                    # multi-hot: every screw within threshold becomes near=1
                    if d <= args.near_threshold: out[f"tool_near_{k}"] = 1
                chosen=min(dists,key=dists.get)
                if dists[chosen] <= args.near_threshold: out["chosen_screw"] = chosen
        rows.append(out)
        if debug_dir is not None and debug_count < args.debug_limit and warped_dir is not None:
            wp=warped_dir/f"{fid:06d}_warped.jpg"
            if wp.exists():
                draw_debug(wp, debug_dir/f"{fid:06d}_yolo_feature_debug.jpg", poly, tip, centers, out); debug_count+=1
    out_path=Path(args.out); out_path.parent.mkdir(parents=True,exist_ok=True)
    fields=["session_id","frame_id","tool_visible","tool_confidence","tool_detection_count","homography_valid","homography_usable","homography_source","marker_count","warp_quality","tool_inside_workspace","tool_x","tool_y","tool_tip_x","tool_tip_y","tool_dist_a","tool_dist_b","tool_dist_c","tool_dist_d","tool_near_a","tool_near_b","tool_near_c","tool_near_d","chosen_screw"]
    with out_path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"[DONE] saved: {out_path}"); print(f"[DONE] rows: {len(rows)}")
    print(f"[DONE] tool visible frames: {sum(r['tool_visible'] for r in rows)}")
    print(f"[DONE] tool inside workspace frames: {sum(r['tool_inside_workspace'] for r in rows)}")
    for k in SCREW_NAMES: print(f"[DONE] tool near {k.upper()}: {sum(r[f'tool_near_{k}'] for r in rows)}")
    if debug_dir is not None: print(f"[DONE] debug dir: {debug_dir}")

if __name__=="__main__": main()
