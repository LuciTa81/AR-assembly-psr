package com.lucita.beastgate;

import org.opencv.core.Point;
import java.util.*;

/** Bounded past-only references; older views require agreement before adding a pose. */
final class PartialReferenceBank {
    private record Reference(long time,PartialMarkerBridge bridge) {}
    private final WorkspaceTracker tracker;
    private final PartialMarkerBridge latest;
    private final List<Reference> references=new ArrayList<>();
    private long lastMs=Long.MIN_VALUE;

    PartialReferenceBank(WorkspaceTracker tracker) {
        this.tracker=tracker;latest=new PartialMarkerBridge(tracker);
    }
    void reset(){latest.reset();references.clear();lastMs=Long.MIN_VALUE;}
    int referenceCount(){return references.size();}

    WorkspaceTracker.Result update(long now,Map<Integer,Point[]> real) {
        if(lastMs!=Long.MIN_VALUE&&now<=lastMs) {
            reset();lastMs=now;
            return new WorkspaceTracker.Result(false,"nonmonotonic_time",real,Map.of(),Map.of(),Double.NaN);
        }
        lastMs=now;
        references.removeIf(reference->now-reference.time()>PartialMarkerBridge.MAX_ANCHOR_MS);
        var result=latest.update(now,real);
        if(real.size()>=5&&result.valid) {
            if(references.isEmpty()||now-references.get(references.size()-1).time()>=500) {
                var bridge=new PartialMarkerBridge(tracker);bridge.update(now,real);
                references.add(new Reference(now,bridge));
                if(references.size()>6)references.remove(0);
            }
            return result;
        }
        if(result.valid||(real.size()!=3&&real.size()!=4))return result;
        List<WorkspaceTracker.Result> candidates=new ArrayList<>();
        for(var reference:references) {
            var candidate=reference.bridge().update(now,real);
            if(candidate.valid)candidates.add(candidate);
        }
        for(int i=0;i<candidates.size();i++)for(int j=i+1;j<candidates.size();j++) {
            var candidate=candidates.get(i);
            if(agree(candidate,candidates.get(j))) {
                return new WorkspaceTracker.Result(true,"partial_reference_bank",real,candidate.targets,
                    candidate.cameraTargets,candidate.rms,candidate.maxError,candidate.rotation,candidate.translation);
            }
        }
        return result;
    }

    private static boolean agree(WorkspaceTracker.Result a,WorkspaceTracker.Result b) {
        if(a.cameraTargets.size()!=4||b.cameraTargets.size()!=4||a.targets.size()!=4||b.targets.size()!=4)return false;
        for(String key:new String[]{"A","B","C","D"}) {
            Point p=a.targets.get(key),q=b.targets.get(key);
            double[] x=a.cameraTargets.get(key),y=b.cameraTargets.get(key);
            if(p==null||q==null||x==null||y==null)return false;
            double squared=0;for(int axis=0;axis<3;axis++)squared+=Math.pow(x[axis]-y[axis],2);
            if(!Double.isFinite(squared)||Math.sqrt(squared)>2.5||Math.hypot(p.x-q.x,p.y-q.y)>2.5)return false;
        }
        return true;
    }
}
