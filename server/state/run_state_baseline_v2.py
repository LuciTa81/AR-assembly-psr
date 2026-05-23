from __future__ import annotations

import argparse, re
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

STATES=["S0","S1","S2","S3","S4","S5","S6"]
STATE_TO_IDX={s:i for i,s in enumerate(STATES)}; IDX_TO_STATE={i:s for s,i in STATE_TO_IDX.items()}

def parse_args():
    p=argparse.ArgumentParser(description="Run Framewise/FSM/HMM v2 using ROI + YOLO + optional MediaPipe features.")
    p.add_argument("--input",required=True); p.add_argument("--out-csv",required=True); p.add_argument("--out-plot",required=True); p.add_argument("--out-metrics",required=True)
    p.add_argument("--tool-threshold",type=float,default=0.4); p.add_argument("--index-weight",type=float,default=0.0); p.add_argument("--roi-weight",type=float,default=0.10)
    p.add_argument("--self-prob",type=float,default=0.92); p.add_argument("--next-prob",type=float,default=0.08); p.add_argument("--min-dwell",type=int,default=2)
    return p.parse_args()

def normalize_state(v):
    if pd.isna(v): return "UNKNOWN"
    m=re.search(r"S[0-6]",str(v).strip()); return m.group(0) if m else "UNKNOWN"

def to_float(df,col,default=0.0):
    if col not in df.columns: return pd.Series([default]*len(df),index=df.index,dtype=float)
    return pd.to_numeric(df[col],errors="coerce").fillna(default).astype(float)

def sigmoid(x): return 1.0/(1.0+np.exp(-x))
def calib(x,thr=0.52,gain=10.0): return sigmoid((x-thr)*gain)

def build_ordered_evidence(df, tool_threshold, index_weight):
    df=df.copy()
    for k in ["a","b","c","d"]:
        tool=to_float(df,f"tool_near_{k}_smooth",0.0); idx=to_float(df,f"index_near_{k}_smooth",0.0)
        df[f"event_{k}_score"]=(tool+index_weight*idx).clip(0,1)
    seen={k:[] for k in ["a","b","c","d"]}; done={k:0 for k in ["a","b","c","d"]}
    order=["a","b","c","d"]
    for _,r in df.iterrows():
        if done["a"]==0 and r["event_a_score"]>=tool_threshold: done["a"]=1
        if done["a"] and done["b"]==0 and r["event_b_score"]>=tool_threshold: done["b"]=1
        if done["b"] and done["c"]==0 and r["event_c_score"]>=tool_threshold: done["c"]=1
        if done["c"] and done["d"]==0 and r["event_d_score"]>=tool_threshold: done["d"]=1
        for k in order: seen[k].append(done[k])
    for k in order: df[f"ordered_seen_{k}"]=seen[k]
    return df

def build_scores(df, roi_weight):
    n=len(df); scores=np.zeros((n,len(STATES)),dtype=float)
    box=calib(to_float(df,"box_present_score_effective",0.5).to_numpy(),0.50,8.0)
    lid=calib(to_float(df,"lid_closed_score_effective",0.5).to_numpy(),0.52,10.0)
    roi={k:calib(to_float(df,f"screw_{k}_done_score_effective",0.5).to_numpy(),0.53,8.0) for k in ["a","b","c","d"]}
    seen={k:to_float(df,f"ordered_seen_{k}",0.0).to_numpy() for k in ["a","b","c","d"]}
    q=to_float(df,"warp_quality",1.0).clip(0,1).to_numpy(); floor=0.05
    for i in range(n):
        scores[i,0]=floor+0.30*(1-box[i])
        scores[i,1]=floor+0.35*box[i]*(1-lid[i])
        scores[i,2]=floor+0.45*lid[i]*(1-seen['a'][i])
        scores[i,3]=floor+0.80*seen['a'][i]*(1-seen['b'][i])+roi_weight*roi['a'][i]*q[i]
        scores[i,4]=floor+0.80*seen['b'][i]*(1-seen['c'][i])+roi_weight*roi['b'][i]*q[i]
        scores[i,5]=floor+0.80*seen['c'][i]*(1-seen['d'][i])+roi_weight*roi['c'][i]*q[i]
        scores[i,6]=floor+0.80*seen['d'][i]+roi_weight*roi['d'][i]*q[i]
    return scores/np.maximum(scores.sum(axis=1,keepdims=True),1e-9)

def predict_framewise(scores): return [IDX_TO_STATE[int(i)] for i in np.argmax(scores,axis=1)]

def predict_fsm(df,min_dwell,tool_threshold):
    cur=0; dwell=0; preds=[]
    box=calib(to_float(df,"box_present_score_effective",0.5).to_numpy(),0.50,8.0); lid=calib(to_float(df,"lid_closed_score_effective",0.5).to_numpy(),0.52,10.0)
    ev={k:to_float(df,f"event_{k}_score",0.0).to_numpy() for k in ["a","b","c","d"]}
    for i in range(len(df)):
        if dwell>=min_dwell:
            if cur==0 and box[i]>=0.50: cur=1; dwell=0
            elif cur==1 and lid[i]>=0.50: cur=2; dwell=0
            elif cur==2 and ev['a'][i]>=tool_threshold: cur=3; dwell=0
            elif cur==3 and ev['b'][i]>=tool_threshold: cur=4; dwell=0
            elif cur==4 and ev['c'][i]>=tool_threshold: cur=5; dwell=0
            elif cur==5 and ev['d'][i]>=tool_threshold: cur=6; dwell=0
        preds.append(IDX_TO_STATE[cur]); dwell+=1
    return preds

def viterbi(scores,self_prob,next_prob):
    n,k=scores.shape; eps=1e-12
    trans=np.full((k,k),eps)
    for s in range(k):
        trans[s,s]=self_prob
        if s+1<k: trans[s,s+1]=next_prob
        else: trans[s,s]=1.0
    trans=trans/trans.sum(axis=1,keepdims=True); logT=np.log(trans+eps); logE=np.log(scores+eps)
    start=np.full(k,eps); start[0]=0.85; start[1]=0.15; start=start/start.sum(); logS=np.log(start+eps)
    dp=np.full((n,k),-np.inf); back=np.zeros((n,k),dtype=int); dp[0]=logS+logE[0]
    for t in range(1,n):
        for s in range(k):
            cand=dp[t-1]+logT[:,s]; bp=int(np.argmax(cand)); dp[t,s]=cand[bp]+logE[t,s]; back[t,s]=bp
    path=np.zeros(n,dtype=int); path[-1]=int(np.argmax(dp[-1]))
    for t in range(n-2,-1,-1): path[t]=back[t+1,path[t+1]]
    return [IDX_TO_STATE[int(i)] for i in path]

def accuracy(y,p):
    pairs=[(a,b) for a,b in zip(y,p) if a in STATE_TO_IDX]
    return sum(a==b for a,b in pairs)/len(pairs) if pairs else float('nan')

def macro_f1(y,p):
    vals=[]
    for s in STATES:
        tp=sum(a==s and b==s for a,b in zip(y,p)); fp=sum(a!=s and b==s for a,b in zip(y,p)); fn=sum(a==s and b!=s for a,b in zip(y,p))
        if tp==0 and fp==0 and fn==0: continue
        prec=tp/(tp+fp) if tp+fp>0 else 0; rec=tp/(tp+fn) if tp+fn>0 else 0; vals.append(0 if prec+rec==0 else 2*prec*rec/(prec+rec))
    return float(np.mean(vals)) if vals else float('nan')

def state_nums(states): return [float(STATE_TO_IDX[s]) if s in STATE_TO_IDX else float('nan') for s in states]

def save_metrics(path,y,preds):
    rows=[]
    for name,p in preds.items():
        rows.append({"metric":"accuracy","model":name,"value":accuracy(y,p)})
        rows.append({"metric":"macro_f1","model":name,"value":macro_f1(y,p)})
    out=pd.DataFrame(rows); Path(path).parent.mkdir(parents=True,exist_ok=True); out.to_csv(path,index=False,encoding="utf-8-sig"); print(out)

def save_plot(path,frame_ids,y,preds):
    plt.figure(figsize=(14,5)); plt.plot(frame_ids,state_nums(y),label="GT",linewidth=3)
    for name,p in preds.items(): plt.plot(frame_ids,state_nums(p),label=name,linewidth=2)
    plt.yticks(range(len(STATES)),STATES); plt.xlabel("frame_id"); plt.ylabel("state"); plt.title("State Timeline v2"); plt.grid(True); plt.legend(); plt.tight_layout(); Path(path).parent.mkdir(parents=True,exist_ok=True); plt.savefig(path); plt.close()

def main():
    args=parse_args(); df=pd.read_csv(args.input); df["frame_id"]=pd.to_numeric(df["frame_id"],errors="coerce").fillna(-1).astype(int); df=df.sort_values("frame_id").reset_index(drop=True); df["gt_state"]=df["gt_state"].apply(normalize_state)
    df=build_ordered_evidence(df,args.tool_threshold,args.index_weight); scores=build_scores(df,args.roi_weight)
    pred_framewise=predict_framewise(scores); pred_fsm=predict_fsm(df,args.min_dwell,args.tool_threshold); pred_hmm=viterbi(scores,args.self_prob,args.next_prob)
    for i,s in enumerate(STATES): df[f"obs_score_{s}"]=scores[:,i]
    df["pred_framewise"]=pred_framewise; df["pred_fsm"]=pred_fsm; df["pred_hmm"]=pred_hmm
    out_csv=Path(args.out_csv); out_csv.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out_csv,index=False,encoding="utf-8-sig")
    preds={"Framewise_v2":pred_framewise,"FSM_v2":pred_fsm,"HMM_v2":pred_hmm}
    save_metrics(Path(args.out_metrics),df["gt_state"].tolist(),preds); save_plot(Path(args.out_plot),df["frame_id"].tolist(),df["gt_state"].tolist(),preds)
    print(f"\n[DONE] predictions: {args.out_csv}\n[DONE] metrics: {args.out_metrics}\n[DONE] plot: {args.out_plot}")
    print("\n[STATE COUNTS]"); print(df[["gt_state","pred_framewise","pred_fsm","pred_hmm"]].apply(lambda x:x.value_counts()).fillna(0))
if __name__=="__main__": main()
