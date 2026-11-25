"""Session-local precise corner map experiment. Does not write calibration."""
import cv2
import numpy as np
import pose_replay_compare as replay
from session_corner_replay import fit_reference,partial_pose


class LearnedCornerTracker:
    def __init__(self,workspace,camera,capacity=8):
        self.workspace,self.camera=workspace,camera
        self.capacity=capacity
        self.history=[];self.maps=[];self.last_ms=None;self.anchor_ms=None
        self.marker_times={}

    def agrees(self,a,b):
        d=replay.target_deltas(a,b,self.workspace,self.camera)
        return d['max_target_delta_px']<=3 and d['max_target_delta_mm']<=3

    def update(self,timestamp,detections):
        if self.last_ms is not None and timestamp<=self.last_ms:
            self.history=[];self.maps=[];self.anchor_ms=None;self.last_ms=timestamp
            self.marker_times={}
            return None,dict(reason='nonmonotonic_time')
        self.last_ms=timestamp
        if not set(detections)<=set(self.workspace.markers):return None,dict(reason='unknown_marker')
        if len(detections)>=5:
            pose,reason=replay.baseline(detections,self.workspace,self.camera)
            if pose is not None:
                if not self.history or timestamp-self.history[-1][0]>=500:
                    try:
                        geometry=fit_reference([dict(detections=detections)],self.workspace,self.camera)
                        self.history=[r for r in self.history if timestamp-r[0]<=30000]
                        self.history=(self.history+[(timestamp,geometry)])[-self.capacity:]
                        if len(self.history)>=4:
                            self.maps=[{},{},{}];self.marker_times={}
                            ids=set.union(*(set(g) for _,g in self.history))
                            for k in ids:
                                samples=[(time,g[k]) for time,g in self.history if k in g]
                                if len(samples)<4:continue
                                for model,group in zip(self.maps,(samples,samples[::2],samples[1::2])):
                                    model[k]=np.median([quad for _,quad in group],axis=0)
                                self.marker_times[k]=samples[-1][0]
                            self.anchor_ms=timestamp
                    except (ValueError,cv2.error):
                        self.maps=[];self.history=[];self.anchor_ms=None;self.marker_times={}
            return pose,dict(reason=reason)
        if len(detections) not in (3,4):return None,dict(reason='need_three_markers')
        if len(detections)==3:
            points=np.array([self.workspace.markers[k][:2] for k in sorted(detections)])
            singular=np.linalg.svd(points-points.mean(axis=0),compute_uv=False)
            if singular[0]<=0 or singular[1]/singular[0]<.05:
                return None,dict(reason='three_marker_collinear')
        if not self.maps or len(self.maps[0])<3:return None,dict(reason='map_warmup')
        if not set(detections)<=set(self.maps[0]):return None,dict(reason='map_marker_warmup')
        if any(timestamp-self.marker_times[k]>30000 for k in detections):return None,dict(reason='map_expired')
        try:
            poses=[]
            for geometry in self.maps:
                pose,reason=partial_pose(detections,geometry,self.camera)
                if pose is None:raise ValueError(reason)
                if pose.rms_px>1.5 or pose.max_error_px>3:raise ValueError('corner_map_residual')
                poses.append(pose)
            best=poses[0]
            if not all(self.agrees(best,p) for p in poses[1:]):raise ValueError('map_disagreement')
            # Physical pose sensitivity is tested, not unconstrained 8-DOF homography extrapolation.
            for removed in detections:
                ids=sorted(set(detections)-{removed})
                objects=np.concatenate([self.maps[0][k] for k in ids])
                observed=np.concatenate([cv2.undistortPoints(detections[k].reshape(-1,1,2),
                    self.camera.matrix,self.camera.distortion,P=self.camera.matrix).reshape(-1,2) for k in ids])
                other=replay._estimate_planar_pose(objects,observed,ids,self.camera,1.5,3.,.25)
                if not self.agrees(best,other):raise ValueError('corner_pose_uncertain')
            return best,dict(reason='tracking',method='learned_corners',age_ms=timestamp-self.anchor_ms)
        except (ValueError,cv2.error) as exc:
            return None,dict(reason=str(exc))


class MultiWindowCorners:
    def __init__(self,workspace,camera):
        self.long=LearnedCornerTracker(workspace,camera)
        self.short=LearnedCornerTracker(workspace,camera,capacity=4)

    def update(self,timestamp,detections):
        pose,detail=self.long.update(timestamp,detections)
        other,why=self.short.update(timestamp,detections)
        if pose is not None:return pose,detail
        if other is not None:return other,{**why,'method':'short_corner_map'}
        return None,detail


class CohortCorners:
    """Do not mix maps anchored by different registered-center subsets."""
    def __init__(self,workspace,camera):
        self.workspace,self.camera=workspace,camera
        self.cohorts={};self.last_ms=None

    def update(self,timestamp,detections):
        if self.last_ms is not None and timestamp<=self.last_ms:
            self.cohorts={};self.last_ms=timestamp
            return None,dict(reason='nonmonotonic_time')
        self.last_ms=timestamp
        self.cohorts={k:v for k,v in self.cohorts.items() if timestamp-v[0]<=30000}
        if len(detections)>=5:
            key=tuple(sorted(detections))
            _,tracker=self.cohorts.get(key,(timestamp,MultiWindowCorners(self.workspace,self.camera)))
            pose,detail=tracker.update(timestamp,detections)
            if pose is not None:
                self.cohorts[key]=(timestamp,tracker)
                if len(self.cohorts)>3:del self.cohorts[min(self.cohorts,key=lambda k:self.cohorts[k][0])]
            return pose,detail
        if len(detections) not in (3,4):return None,dict(reason='need_three_markers')
        detail=dict(reason='map_warmup')
        for key,(_,tracker) in sorted(self.cohorts.items(),key=lambda item:item[1][0],reverse=True):
            if not set(detections)<=set(key):continue
            pose,detail=tracker.update(timestamp,detections)
            if pose is not None:return pose,{**detail,'cohort':key}
        return None,detail
