package com.lucita.beastgate;

import org.opencv.calib3d.Calib3d;
import org.opencv.core.*;
import java.util.*;

/** Candidate-only planar transfer. Real marker counts never include inferred points. */
final class PartialMarkerBridge {
    static final long MAX_ANCHOR_MS=30_000;
    private final WorkspaceTracker tracker;
    private Map<Integer,Point[]> anchor;
    private Map<Integer,Point> anchorCenters;
    private long anchorMs,lastMs=Long.MIN_VALUE;

    PartialMarkerBridge(WorkspaceTracker tracker){this.tracker=tracker;}
    void reset(){anchor=null;anchorCenters=null;lastMs=Long.MIN_VALUE;}
    private static void require(boolean value,String reason){if(!value)throw new IllegalArgumentException(reason);}
    private static WorkspaceTracker.Result rejected(String reason,Map<Integer,Point[]> markers){
        return new WorkspaceTracker.Result(false,reason,markers,Map.of(),Map.of(),Double.NaN);
    }

    WorkspaceTracker.Result update(long now,Map<Integer,Point[]> real) {
        if(lastMs!=Long.MIN_VALUE&&now<=lastMs){reset();lastMs=now;return rejected("nonmonotonic_time",real);}
        lastMs=now;
        try {
            Map<Integer,Point> centers=tracker.markerCenters(real);
            if(real.size()>=5) {
                var result=tracker.estimate(real,1280,720);
                if(result.valid){anchor=tracker.undistortedQuads(real);anchorCenters=centers;anchorMs=now;}
                return result;
            }
            if(real.size()<3)return rejected("need_three_markers",real);
            require(anchor!=null&&now-anchorMs<=MAX_ANCHOR_MS,"reference_expired");
            require(anchor.keySet().containsAll(real.keySet()),"reference_missing_marker");
            List<Integer> keys=new ArrayList<>(real.keySet());Collections.sort(keys);
            if(keys.size()==3)requireNoncollinear(keys);
            Map<Integer,Point[]> current=tracker.undistortedQuads(real);
            Point[] source=flatten(anchor,keys),target=flatten(current,keys);
            List<Integer> all=new ArrayList<>(anchor.keySet());Collections.sort(all);
            Point[] original=all.stream().map(anchorCenters::get).toArray(Point[]::new);
            double[] h=fit(source,target);
            Point[] predicted=warp(source,h),transferred=warp(original,h);
            double sum=0,max=0;
            for(int i=0;i<target.length;i++){double e=distance(predicted[i],target[i]);sum+=e*e;max=Math.max(max,e);}
            require(Math.sqrt(sum/target.length)<=1.5&&max<=3,"corner_transfer_residual");
            List<Point[]> alternatives=new ArrayList<>();double spread=0;
            for(int removed=0;removed<keys.size();removed++) {
                Point[] a=new Point[source.length-4],b=new Point[a.length];int n=0;
                for(int i=0;i<source.length;i++)if(i/4!=removed){a[n]=source[i];b[n++]=target[i];}
                Point[] other=warp(original,fit(a,b));alternatives.add(other);
                for(int i=0;i<other.length;i++)spread=Math.max(spread,distance(other[i],transferred[i]));
            }
            require(spread<=3,"transfer_uncertain");
            var result=tracker.estimateTransferred(real,combine(all,centers,transferred));
            if(!result.valid)return result;
            if(keys.size()==3)for(Point[] other:alternatives) {
                var alternate=tracker.estimateTransferred(real,combine(all,centers,other));
                require(alternate.valid,"three_marker_pose_uncertain");
                require(result.cameraTargets.size()==4&&alternate.cameraTargets.size()==4,"three_marker_targets_outside");
                for(String key:result.cameraTargets.keySet()) {
                    double[] a=result.cameraTargets.get(key),b=alternate.cameraTargets.get(key);double squared=0;
                    for(int i=0;i<3;i++)squared+=Math.pow(a[i]-b[i],2);
                    require(Math.sqrt(squared)<=3&&distance(result.targets.get(key),alternate.targets.get(key))<=3,"three_marker_pose_uncertain");
                }
            }
            return new WorkspaceTracker.Result(true,"partial_corner_bridge",real,result.targets,result.cameraTargets,
                result.rms,result.maxError,result.rotation,result.translation);
        }catch(IllegalArgumentException|CvException e){return rejected(e.getMessage(),real);}
    }

    private void requireNoncollinear(List<Integer> ids) {
        Mat points=new Mat(3,2,CvType.CV_64F),w=new Mat(),u=new Mat(),v=new Mat();
        try {
            double x=0,y=0;for(int id:ids){Point3 p=tracker.markerPosition(id);x+=p.x;y+=p.y;}
            for(int i=0;i<3;i++){Point3 p=tracker.markerPosition(ids.get(i));points.put(i,0,p.x-x/3,p.y-y/3);}
            Core.SVDecomp(points,w,u,v,Core.SVD_NO_UV);
            require(w.get(1,0)[0]/w.get(0,0)[0]>=.05,"three_marker_collinear");
        }finally{points.release();w.release();u.release();v.release();}
    }
    private static Map<Integer,Point> combine(List<Integer> ids,Map<Integer,Point> real,Point[] inferred) {
        Map<Integer,Point> result=new TreeMap<>();
        for(int i=0;i<ids.size();i++)result.put(ids.get(i),real.getOrDefault(ids.get(i),inferred[i]));
        return result;
    }
    private static Point[] flatten(Map<Integer,Point[]> map,List<Integer> ids) {
        List<Point> result=new ArrayList<>();for(int id:ids)Collections.addAll(result,map.get(id));
        return result.toArray(new Point[0]);
    }
    private static double[] fit(Point[] a,Point[] b) {
        MatOfPoint2f source=new MatOfPoint2f(a),target=new MatOfPoint2f(b);Mat h=null;
        try {
            h=Calib3d.findHomography(source,target,0);
            require(!h.empty()&&Core.checkRange(h),"invalid_homography");
            double[] values=new double[9];h.get(0,0,values);
            require(Math.abs(values[8])>1e-12,"invalid_homography");
            for(int i=0;i<9;i++)values[i]/=values[8];
            return values;
        }finally{source.release();target.release();if(h!=null)h.release();}
    }
    private static Point[] warp(Point[] points,double[] h) {
        Point[] result=new Point[points.length];
        for(int i=0;i<points.length;i++) {
            double x=points[i].x,y=points[i].y,z=h[6]*x+h[7]*y+h[8];
            require(Double.isFinite(z)&&z>1e-8,"invalid_transfer");
            double u=(h[0]*x+h[1]*y+h[2])/z,v=(h[3]*x+h[4]*y+h[5])/z;
            require(Double.isFinite(u)&&Double.isFinite(v),"invalid_transfer");
            result[i]=new Point(u,v);
        }
        return result;
    }
    private static double distance(Point a,Point b){return Math.hypot(a.x-b.x,a.y-b.y);}
}
