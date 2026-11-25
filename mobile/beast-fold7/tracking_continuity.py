"""Offline continuity candidates. No hardware access or calibration writes."""
import cv2
import numpy as np
import pose_replay_compare as replay
from corner_bridge_replay import CornerBridge,warp,fit_homography


class ReferenceBank:
    def __init__(self,workspace,camera):
        self.workspace,self.camera=workspace,camera
        self.latest=self.make_tracker()
        self.references=[]
        self.last_ms=None

    def make_tracker(self):
        return CornerBridge(self.workspace,self.camera,max_age_ms=30000,
                            conservative_three=True,retain_reference_on_loss=True)

    def update(self,timestamp,detections):
        if self.last_ms is not None and timestamp<=self.last_ms:
            self.references=[];self.latest=self.make_tracker()
            self.last_ms=timestamp
            return None,dict(reason='nonmonotonic_time')
        self.last_ms=timestamp
        self.references=[r for r in self.references if timestamp-r.anchor_ms<=30000]
        pose,detail=self.latest.update(timestamp,detections)
        if len(detections)>=5 and pose is not None:
            if not self.references or timestamp-self.references[-1].anchor_ms>=500:
                reference=self.make_tracker();reference.update(timestamp,detections)
                self.references=(self.references+[reference])[-6:]
            return pose,detail
        if pose is not None or len(detections) not in (3,4):return pose,detail
        candidates=[]
        for reference in self.references:
            p,d=reference.update(timestamp,detections)
            if p is not None:candidates.append((p,d))
        # Older references can add a pose only if two independently fitted views agree.
        for i,(p,d) in enumerate(candidates):
            for q,_ in candidates[i+1:]:
                delta=replay.target_deltas(p,q,self.workspace,self.camera)
                if delta['max_target_delta_px']<=2.5 and delta['max_target_delta_mm']<=2.5:
                    return p,{**d,'method':'reference_bank','references':len(candidates)}
        return None,detail

class FlowBridge:
    MAX_AGE_MS=500
    def __init__(self,workspace,camera):
        self.workspace,self.camera=workspace,camera
        self.gray=None;self.seed_ms=None;self.last_ms=None

    def seed(self,timestamp,gray,pose,detections):
        self.gray=None;self.seed_ms=None
        if pose is None or len(detections)<3 or gray.shape!=(720,1280):return
        points=[];groups=[]
        for key,quad in detections.items():
            mask=np.zeros(gray.shape,np.uint8)
            quad=np.array(quad);center=quad.mean(axis=0)
            cv2.fillConvexPoly(mask,np.rint(center+.92*(quad-center)).astype(np.int32),255)
            found=cv2.goodFeaturesToTrack(gray,maxCorners=24,qualityLevel=.02,minDistance=4,mask=mask,blockSize=5)
            if found is not None:
                points.extend(found.reshape(-1,2));groups.extend([key]*len(found))
        if len(points)<18 or len(set(groups))<3:return
        self.points=np.array(points,np.float32).reshape(-1,1,2)
        self.groups=np.array(groups)
        self.ids=sorted(self.workspace.markers)
        objects=np.array([self.workspace.markers[k] for k in self.ids])
        self.centers=cv2.projectPoints(objects,pose.rvec,pose.tvec,self.camera.matrix,None)[0].reshape(-1,2)
        self.gray=gray.copy();self.seed_ms=timestamp;self.last_ms=timestamp

    def update(self,timestamp,gray,detections):
        if self.gray is None:return None,dict(reason='flow_no_seed')
        if timestamp<=self.last_ms or timestamp-self.seed_ms>self.MAX_AGE_MS or gray.shape!=self.gray.shape:
            self.gray=None
            return None,dict(reason='flow_expired')
        self.last_ms=timestamp
        try:
            settings=dict(winSize=(21,21),maxLevel=3,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
            current,forward,error=cv2.calcOpticalFlowPyrLK(self.gray,gray,self.points,None,**settings)
            if current is None or forward is None or error is None:
                raise ValueError('flow_no_correspondence')
            back,backward,_=cv2.calcOpticalFlowPyrLK(gray,self.gray,current,None,**settings)
            if back is None or backward is None:
                raise ValueError('flow_no_correspondence')
            source=self.points.reshape(-1,2);target=current.reshape(-1,2)
            keep=(forward.ravel()!=0)&(backward.ravel()!=0)&(error.ravel()<20)&(np.linalg.norm(back.reshape(-1,2)-source,axis=1)<=.75)
            keep&=np.isfinite(target).all(axis=1)&(target[:,0]>=0)&(target[:,0]<1280)&(target[:,1]>=0)&(target[:,1]<720)
            groups=self.groups[keep]
            if keep.sum()<18 or len(set(groups))<3:raise ValueError('flow_support')
            und=lambda p:cv2.undistortPoints(p.reshape(-1,1,2),self.camera.matrix,self.camera.distortion,P=self.camera.matrix).reshape(-1,2)
            a,b=und(source[keep]),und(target[keep])
            h,mask=cv2.findHomography(a,b,cv2.RANSAC,1.5)
            if h is None or mask.sum()<18 or mask.mean()<.85:raise ValueError('flow_inliers')
            good=mask.ravel()!=0;a,b,groups=a[good],b[good],groups[good]
            if len(set(groups))<3:raise ValueError('flow_group_support')
            errors=np.linalg.norm(warp(a,h)-b,axis=1)
            if np.sqrt(np.mean(errors**2))>1 or errors.max()>2.5:raise ValueError('flow_residual')
            predicted=warp(self.centers,h)
            # Excluding each marker's features must not change unobserved centers substantially.
            for group in set(groups):
                other=groups!=group
                if other.sum()<12:raise ValueError('flow_group_support')
                alternate=fit_homography(a[other],b[other])
                if np.linalg.norm(warp(self.centers,alternate)-predicted,axis=1).max()>2.5:
                    raise ValueError('flow_extrapolation')
            for key,quad in detections.items():
                if key not in self.ids:raise ValueError('flow_unknown_marker')
                observed=replay.marker_center_px(quad,self.camera)
                if np.linalg.norm(observed-predicted[self.ids.index(key)])>3:
                    raise ValueError('flow_marker_disagreement')
            objects=np.array([self.workspace.markers[k] for k in self.ids])
            pose=replay._estimate_planar_pose(objects,predicted,self.ids,self.camera,3.2,5.,.25)
            return pose,dict(reason='tracking',method='optical_flow',age_ms=timestamp-self.seed_ms,
                             points=len(a),groups=len(set(groups)))
        except (ValueError,cv2.error) as exc:
            return None,dict(reason=str(exc))
