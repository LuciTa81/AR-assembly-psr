package com.lucita.beastgate;

import org.opencv.core.*;
import java.util.*;

/** Volatile corner geometry in the frozen workspace, never a calibration-file update. */
final class LearnedCornerTracker {
    private record Sample(long time,Map<Integer,Point3[]> geometry) {}
    private final WorkspaceTracker tracker;
    private final int capacity;
    private final List<Sample> history=new ArrayList<>();
    private List<Map<Integer,Point3[]>> maps=List.of();
    private final Map<Integer,Long> markerTimes=new TreeMap<>();
    private long lastMs=Long.MIN_VALUE,anchorMs=Long.MIN_VALUE;
    LearnedCornerTracker(WorkspaceTracker tracker){this(tracker,8);}
    LearnedCornerTracker(WorkspaceTracker tracker,int capacity){this.tracker=tracker;this.capacity=capacity;}
    void reset(){history.clear();maps=List.of();markerTimes.clear();lastMs=Long.MIN_VALUE;anchorMs=Long.MIN_VALUE;}
    private static WorkspaceTracker.Result reject(String reason,Map<Integer,Point[]> real) {
        return new WorkspaceTracker.Result(false,reason,real,Map.of(),Map.of(),Double.NaN);
    }
    WorkspaceTracker.Result update(long now,Map<Integer,Point[]> real) {
        if(lastMs!=Long.MIN_VALUE&&now<=lastMs){reset();lastMs=now;return reject("nonmonotonic_time",real);}
        lastMs=now;
        if(real.size()>=5) {
            var result=tracker.estimate(real,1280,720);
            if(result.valid&&(history.isEmpty()||now-history.get(history.size()-1).time()>=500)) {
                try {
                    var geometry=tracker.inferCornerMap(real,result);
                    history.removeIf(sample->now-sample.time()>30_000);
                    history.add(new Sample(now,geometry));if(history.size()>capacity)history.remove(0);
                    if(history.size()>=4) {
                        Set<Integer> ids=new TreeSet<>();
                        for(var sample:history)ids.addAll(sample.geometry().keySet());
                        maps=List.of(new TreeMap<>(),new TreeMap<>(),new TreeMap<>());markerTimes.clear();
                        Map<Integer,Integer> counts=new TreeMap<>();
                        for(int id:ids) {
                            List<Sample> present=new ArrayList<>(),even=new ArrayList<>(),odd=new ArrayList<>();
                            for(var sample:history)if(sample.geometry().containsKey(id))present.add(sample);
                            counts.put(id,present.size());if(present.size()<4)continue;
                            for(int i=0;i<present.size();i++)(i%2==0?even:odd).add(present.get(i));
                            maps.get(0).putAll(median(present,Set.of(id)));
                            maps.get(1).putAll(median(even,Set.of(id)));
                            maps.get(2).putAll(median(odd,Set.of(id)));
                            markerTimes.put(id,present.get(present.size()-1).time());
                        }
                        anchorMs=now;
                        android.util.Log.i("BeastCornerMap","capacity="+capacity+" ready="+markerTimes.keySet()+" counts="+counts);
                    }
                }catch(IllegalArgumentException|CvException e){history.clear();maps=List.of();markerTimes.clear();anchorMs=Long.MIN_VALUE;}
            }
            return result;
        }
        if(real.size()!=3&&real.size()!=4)return reject("need_three_markers",real);
        if(real.size()==3&&!tracker.noncollinearCenters(real.keySet()))return reject("three_marker_collinear",real);
        if(maps.isEmpty()||maps.get(0).size()<3)return reject("map_warmup",real);
        if(!maps.get(0).keySet().containsAll(real.keySet()))return reject("map_marker_warmup",real);
        for(int id:real.keySet())if(now-markerTimes.get(id)>30_000)return reject("map_expired",real);
        WorkspaceTracker.Result best=null;
        for(var map:maps) {
            var result=tracker.estimateCornerSubset(real,map);
            if(!result.valid)return result;
            if(best==null)best=result;
            else if(!agrees(best,result))return reject("map_disagreement",real);
        }
        for(int removed:real.keySet()) {
            var subset=new TreeMap<>(real);subset.remove(removed);
            var other=tracker.estimateCornerSubset(subset,maps.get(0));
            if(!other.valid||!agrees(best,other))return reject("corner_pose_uncertain",real);
        }
        return new WorkspaceTracker.Result(true,"learned_corners",real,best.targets,best.cameraTargets,
            best.rms,best.maxError,best.rotation,best.translation);
    }

    private static Map<Integer,Point3[]> median(List<Sample> samples,Set<Integer> ids) {
        Map<Integer,Point3[]> result=new TreeMap<>();
        for(int id:ids) {
            Point3[] quad=new Point3[4];
            for(int corner=0;corner<4;corner++) {
                double[] x=new double[samples.size()],y=new double[x.length];
                for(int i=0;i<x.length;i++){Point3 p=samples.get(i).geometry().get(id)[corner];x[i]=p.x;y[i]=p.y;}
                Arrays.sort(x);Arrays.sort(y);int m=x.length/2;
                quad[corner]=new Point3((x[m]+x[(x.length-1)/2])/2,(y[m]+y[(y.length-1)/2])/2,0);
            }
            result.put(id,quad);
        }
        return result;
    }

    private static boolean agrees(WorkspaceTracker.Result a,WorkspaceTracker.Result b) {
        if(a.cameraTargets.size()!=4||b.cameraTargets.size()!=4)return false;
        for(String key:new String[]{"A","B","C","D"}) {
            Point p=a.targets.get(key),q=b.targets.get(key);double[] x=a.cameraTargets.get(key),y=b.cameraTargets.get(key);
            if(p==null||q==null||x==null||y==null)return false;
            double squared=0;for(int i=0;i<3;i++)squared+=Math.pow(x[i]-y[i],2);
            if(!Double.isFinite(squared)||Math.sqrt(squared)>3||Math.hypot(p.x-q.x,p.y-q.y)>3)return false;
        }
        return true;
    }
}
