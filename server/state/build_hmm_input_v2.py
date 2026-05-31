from __future__ import annotations

import argparse, csv, re
from pathlib import Path
from typing import List
import numpy as np
import pandas as pd

IMAGE_EXTS={".jpg",".jpeg",".png",".bmp",".webp"}
ROI_COLS=["box_present_score","lid_closed_score","screw_a_done_score","screw_b_done_score","screw_c_done_score","screw_d_done_score"]
SCREW_SCORE_COLS=[f"{p}_{k}" for p in ["screw_detect_score","tip_screw_score"] for k in ["a","b","c","d"]]
YOLO_COLS=["tool_visible","tool_confidence","tool_detection_count","tool_inside_workspace","tool_x","tool_y","tool_tip_x","tool_tip_y","tool_dist_a","tool_dist_b","tool_dist_c","tool_dist_d","tool_near_a","tool_near_b","tool_near_c","tool_near_d","chosen_screw"]+SCREW_SCORE_COLS
MP_COLS=["hand_visible","selected_hand_visible","selected_hand_source","selected_handedness","selected_hand_score","selected_hand_to_tool_dist","index_inside_workspace","index_x_warped","index_y_warped","index_dist_a","index_dist_b","index_dist_c","index_dist_d","index_near_a","index_near_b","index_near_c","index_near_d"]

def parse_args():
    p=argparse.ArgumentParser(description="Merge v2 visual features into HMM input CSV.")
    p.add_argument("--session",default=None); p.add_argument("--session-id",required=True)
    p.add_argument("--homography",required=True); p.add_argument("--roi",required=True); p.add_argument("--yolo",required=True); p.add_argument("--mediapipe",required=True); p.add_argument("--labels",required=True); p.add_argument("--out",required=True)
    p.add_argument("--smooth-window",type=int,default=5); p.add_argument("--seen-threshold",type=float,default=0.4)
    p.add_argument("--tool-score-radius",type=float,default=100.0)
    p.add_argument("--tool-score-softness",type=float,default=25.0)
    p.add_argument("--index-score-radius",type=float,default=120.0)
    p.add_argument("--index-score-softness",type=float,default=30.0)
    p.add_argument("--roi-delta-window",type=int,default=1)
    p.add_argument("--roi-delta-scale",type=float,default=0.20)
    p.add_argument("--roi-delta-smooth-window",type=int,default=3)
    return p.parse_args()

def norm_frame_id(v):
    if pd.isna(v): return -1
    m=re.search(r"(\d+)",str(v)); return int(m.group(1)) if m else -1

def read(path):
    p=Path(path); return pd.DataFrame() if (not p.exists() or p.stat().st_size==0) else pd.read_csv(p)

def collect_frames(session_dir:Path):
    frames_csv=session_dir/"frames.csv"
    if frames_csv.exists():
        rows=[]
        with frames_csv.open("r",encoding="utf-8-sig",newline="") as f:
            for i,row in enumerate(csv.DictReader(f),1):
                rows.append({"frame_id":norm_frame_id(row.get("frame_id",i)),"timestamp_ms":row.get("timestamp_ms") or row.get("timestamp") or row.get("time_ms") or "","image_path":row.get("image_path","")})
        return pd.DataFrame(rows).sort_values("frame_id")
    root=session_dir/"frames" if (session_dir/"frames").exists() else session_dir
    paths=sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    return pd.DataFrame([{"frame_id":i,"timestamp_ms":"","image_path":p.name} for i,p in enumerate(paths,1)])

def norm_df(df):
    if df.empty: return df
    if "frame_id" not in df.columns: raise ValueError("CSV missing frame_id")
    df=df.copy(); df["frame_id"]=df["frame_id"].apply(norm_frame_id).astype(int); return df

def safe_cols(df, cols):
    if df.empty: return pd.DataFrame(columns=["frame_id"]+cols)
    keep=["frame_id"]+[c for c in cols if c in df.columns]
    return df[keep].copy()

def label_for_frame(frame_id: int, labels_df: pd.DataFrame, session_id: str) -> str:
    """
    세션별 GT 라벨을 반환합니다.

    중요:
    - labels_segments.csv에 현재 session_id가 있으면 해당 세션 라벨만 사용합니다.
    - 현재 session_id가 없으면 다른 세션 라벨을 fallback으로 사용하지 않습니다.
    - 라벨이 없으면 UNKNOWN을 반환합니다.
    """
    if labels_df.empty:
        return "UNKNOWN"

    df = labels_df.copy()

    if "session_id" in df.columns:
        matched = df[df["session_id"].astype(str) == str(session_id)]

        if matched.empty:
            return "UNKNOWN"

        df = matched

    required = {"start_frame", "end_frame", "state"}

    if not required.issubset(set(df.columns)):
        return "UNKNOWN"

    for _, row in df.iterrows():
        try:
            start = int(row["start_frame"])
            end = int(row["end_frame"])
        except Exception:
            continue

        if start <= frame_id <= end:
            return str(row["state"])

    return "UNKNOWN"


def to_num(df,col,default=0.0):
    if col not in df.columns: df[col]=default
    df[col]=pd.to_numeric(df[col],errors="coerce").fillna(default); return df

def add_defaults(df):
    for c in ROI_COLS: df=to_num(df,c,0.5)
    for c,d in {"homography_valid":0,"homography_usable":0,"marker_count":0,"warp_quality":0.0}.items(): df=to_num(df,c,d)
    if "homography_source" not in df.columns: df["homography_source"]="unknown"
    for c,d in {"tool_visible":0,"tool_confidence":0.0,"tool_detection_count":0,"tool_inside_workspace":0,"tool_x":-1.0,"tool_y":-1.0,"tool_tip_x":-1.0,"tool_tip_y":-1.0,"tool_dist_a":-1.0,"tool_dist_b":-1.0,"tool_dist_c":-1.0,"tool_dist_d":-1.0,"tool_near_a":0,"tool_near_b":0,"tool_near_c":0,"tool_near_d":0}.items(): df=to_num(df,c,d)
    for c in SCREW_SCORE_COLS: df=to_num(df,c,0.0)
    if "chosen_screw" not in df.columns: df["chosen_screw"]="none"
    df["chosen_screw"]=df["chosen_screw"].fillna("none").astype(str)
    for c,d in {"hand_visible":0,"selected_hand_visible":0,"selected_hand_score":0.0,"selected_hand_to_tool_dist":-1.0,"index_inside_workspace":0,"index_x_warped":-1.0,"index_y_warped":-1.0,"index_dist_a":-1.0,"index_dist_b":-1.0,"index_dist_c":-1.0,"index_dist_d":-1.0,"index_near_a":0,"index_near_b":0,"index_near_c":0,"index_near_d":0}.items(): df=to_num(df,c,d)
    if "selected_hand_source" not in df.columns: df["selected_hand_source"]="none"
    if "selected_handedness" not in df.columns: df["selected_handedness"]="None"
    df["selected_hand_source"]=df["selected_hand_source"].fillna("none").astype(str); df["selected_handedness"]=df["selected_handedness"].fillna("None").astype(str)
    return df

def distance_to_score(dist, radius, softness):
    dist=pd.to_numeric(dist,errors="coerce").fillna(-1.0).astype(float)
    score=1.0/(1.0+np.exp(((dist-radius)/max(float(softness),1e-6)).clip(-60,60)))
    return score.where(dist>=0,0.0).clip(0,1)

def add_continuous_near_scores(df, tool_radius, tool_softness, index_radius, index_softness):
    for k in ["a","b","c","d"]:
        tool_col=f"tool_near_{k}"
        index_col=f"index_near_{k}"

        df[f"{tool_col}_binary"]=pd.to_numeric(df[tool_col],errors="coerce").fillna(0.0).astype(float)
        df[f"{index_col}_binary"]=pd.to_numeric(df[index_col],errors="coerce").fillna(0.0).astype(float)

        tool_gate=(
            pd.to_numeric(df["tool_visible"],errors="coerce").fillna(0.0).astype(float)
            * pd.to_numeric(df["tool_inside_workspace"],errors="coerce").fillna(0.0).astype(float)
        ).clip(0,1)
        index_gate=(
            pd.to_numeric(df["selected_hand_visible"],errors="coerce").fillna(0.0).astype(float)
            * pd.to_numeric(df["index_inside_workspace"],errors="coerce").fillna(0.0).astype(float)
        ).clip(0,1)

        df[f"tool_score_{k}"]=distance_to_score(df[f"tool_dist_{k}"],tool_radius,tool_softness)*tool_gate
        df[f"index_score_{k}"]=distance_to_score(df[f"index_dist_{k}"],index_radius,index_softness)*index_gate

        # Continuous version: keep the historical column names, but store 0~1 distance scores.
        df[tool_col]=df[f"tool_score_{k}"]
        df[index_col]=df[f"index_score_{k}"]
    return df

def add_smoothing(df, window, seen_threshold):
    df=df.sort_values("frame_id").reset_index(drop=True)
    for prefix in ["tool_near","index_near"]:
        for k in ["a","b","c","d"]:
            col=f"{prefix}_{k}"; sm=f"{col}_smooth"; seen=f"{prefix.replace('_near','_seen')}_{k}_cum"
            df[sm]=df[col].astype(float).rolling(window=window,min_periods=1).mean()
            df[seen]=df[sm].astype(float).cummax().clip(0,1)
    for prefix in ["screw_detect_score","tip_screw_score"]:
        for k in ["a","b","c","d"]:
            col=f"{prefix}_{k}"
            df[f"{col}_smooth"]=df[col].astype(float).rolling(window=window,min_periods=1).mean().clip(0,1)
    df["roi_quality_weight"]=df["homography_usable"].astype(float)*df["warp_quality"].astype(float).clip(0,1)
    for c in ROI_COLS:
        df[f"{c}_effective"]=0.5+(df[c].astype(float)-0.5)*df["roi_quality_weight"]
    return df

def add_roi_deltas(df, window, scale, smooth_window):
    period=max(1,int(window))
    smooth=max(1,int(smooth_window))
    denom=max(float(scale),1e-6)
    for c in ROI_COLS:
        eff=f"{c}_effective"
        values=pd.to_numeric(df[eff],errors="coerce").fillna(0.5).astype(float)
        positive_delta=values.diff(periods=period).fillna(0.0).clip(lower=0.0)
        score=(positive_delta/denom).clip(0,1)
        df[f"{c}_delta"]=score
        df[f"{c}_delta_smooth"]=score.rolling(window=smooth,min_periods=1).max().clip(0,1)
    return df

def main():
    args=parse_args(); h=norm_df(read(args.homography))
    if h.empty: raise ValueError("homography CSV is empty")
    base=collect_frames(Path(args.session)) if args.session and Path(args.session).exists() else h[["frame_id"]].assign(timestamp_ms="",image_path="")
    h=safe_cols(h,["homography_valid","homography_usable","homography_source","marker_count","warp_quality"])
    roi=safe_cols(norm_df(read(args.roi)),ROI_COLS); yolo=safe_cols(norm_df(read(args.yolo)),YOLO_COLS); mp=safe_cols(norm_df(read(args.mediapipe)),MP_COLS)
    labels=read(args.labels)
    df=base.merge(h,on="frame_id",how="left").merge(roi,on="frame_id",how="left").merge(yolo,on="frame_id",how="left").merge(mp,on="frame_id",how="left")
    df["session_id"]=args.session_id; df=add_defaults(df); df["gt_state"]=[label_for_frame(fid,labels,args.session_id) for fid in df["frame_id"]]
    df=add_continuous_near_scores(df,args.tool_score_radius,args.tool_score_softness,args.index_score_radius,args.index_score_softness)
    df=add_smoothing(df,args.smooth_window,args.seen_threshold)
    df=add_roi_deltas(df,args.roi_delta_window,args.roi_delta_scale,args.roi_delta_smooth_window)
    CONT_COLS=[f"{p}_{k}" for p in ["tool_score","index_score"] for k in ["a","b","c","d"]]+[f"{p}_near_{k}_binary" for p in ["tool","index"] for k in ["a","b","c","d"]]
    ROI_DELTA_COLS=[f"{c}_delta" for c in ROI_COLS]+[f"{c}_delta_smooth" for c in ROI_COLS]
    SCREW_SCORE_SMOOTH_COLS=[f"{c}_smooth" for c in SCREW_SCORE_COLS]
    preferred=["session_id","frame_id","timestamp_ms","image_path","gt_state","homography_valid","homography_usable","homography_source","marker_count","warp_quality","roi_quality_weight"]+ROI_COLS+[f"{c}_effective" for c in ROI_COLS]+ROI_DELTA_COLS+YOLO_COLS+SCREW_SCORE_SMOOTH_COLS+CONT_COLS+["tool_near_a_smooth","tool_near_b_smooth","tool_near_c_smooth","tool_near_d_smooth","tool_seen_a_cum","tool_seen_b_cum","tool_seen_c_cum","tool_seen_d_cum"]+MP_COLS+["index_near_a_smooth","index_near_b_smooth","index_near_c_smooth","index_near_d_smooth","index_seen_a_cum","index_seen_b_cum","index_seen_c_cum","index_seen_d_cum"]
    cols=[c for c in preferred if c in df.columns]+[c for c in df.columns if c not in preferred]
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); df[cols].to_csv(out,index=False,encoding="utf-8-sig")
    print(f"[DONE] saved: {out}"); print(f"[DONE] rows: {len(df)}"); print("\n[GT STATE COUNTS]"); print(df["gt_state"].value_counts(dropna=False)); print("\n[FEATURE SUMMARY]"); print(f"homography usable: {int((df['homography_usable']==1).sum())}"); print(f"tool visible: {int((df['tool_visible']==1).sum())}"); print(f"tool inside workspace: {int((df['tool_inside_workspace']==1).sum())}"); print(f"selected hand: {int((df['selected_hand_visible']==1).sum())}")
if __name__=="__main__": main()
