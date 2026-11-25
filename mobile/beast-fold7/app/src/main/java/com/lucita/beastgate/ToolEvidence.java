package com.lucita.beastgate;

import android.content.Context;
import java.util.*;
import org.json.*;
import org.opencv.calib3d.Calib3d;
import org.opencv.core.*;
import org.opencv.dnn.Dnn;
import org.opencv.imgproc.Imgproc;

/** Metric image proximity port of Windows yolo_realtime.py, not physical contact. */
final class ToolEvidence implements AutoCloseable {
    record Result(boolean valid,String reason,int driverCount,Point tip,double[] distances,double[] scores,int tipSource){
        boolean near(int target){
            if(!valid||target<0||target>=4)return false;
            double other=0;for(int i=0;i<4;i++)if(i!=target)other=Math.max(other,scores[i]);
            return scores[target]>=.30&&scores[target]>other;
        }
    }
    private final Mat k=new Mat(3,3,CvType.CV_64F);
    private final MatOfDouble distortion=new MatOfDouble();
    private final Point[] targets=new Point[4];
    private final double height,minX,maxX,minY,maxY;

    ToolEvidence(Context context)throws Exception{
        JSONObject camera,workspace;
        try(var in=context.getAssets().open("camera-profile.json")){camera=new JSONObject(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        try(var in=context.getAssets().open("workspace-profile.json")){workspace=new JSONObject(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        double[] matrix=new double[9],d=new double[5];
        for(int i=0;i<9;i++)matrix[i]=camera.getJSONArray("camera_matrix").getJSONArray(i/3).getDouble(i%3);
        for(int i=0;i<5;i++)d[i]=camera.getJSONArray("distortion_coefficients").getDouble(i);
        k.put(0,0,matrix);distortion.fromArray(d);
        double h=0,low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
        for(int i=0;i<4;i++){
            JSONArray p=workspace.getJSONObject("targets_mm").getJSONArray("ABCD".substring(i,i+1));
            targets[i]=new Point(p.getDouble(0),p.getDouble(1));
            h+=p.getDouble(2);low=Math.min(low,p.getDouble(2));high=Math.max(high,p.getDouble(2));
        }
        if(high-low>.5)throw new IllegalArgumentException("common_screw_height_required");
        height=h/4;minX=Arrays.stream(targets).mapToDouble(p->p.x).min().orElseThrow()-100;
        maxX=Arrays.stream(targets).mapToDouble(p->p.x).max().orElseThrow()+100;
        minY=Arrays.stream(targets).mapToDouble(p->p.y).min().orElseThrow()-100;
        maxY=Arrays.stream(targets).mapToDouble(p->p.y).max().orElseThrow()+100;
    }

    Point project(Point pixel,WorkspaceTracker.Result pose){
        if(!pose.valid||pose.rotation==null||pose.translation==null)return null;
        MatOfPoint2f input=new MatOfPoint2f(pixel),output=new MatOfPoint2f();
        try{
            Calib3d.undistortPoints(input,output,k,distortion);
            Point p=output.toArray()[0];double[] ray={p.x,p.y,1},direction=new double[3],center=new double[3];
            for(int i=0;i<3;i++)for(int j=0;j<3;j++){
                direction[i]+=pose.rotation[j*3+i]*ray[j];
                center[i]-=pose.rotation[j*3+i]*pose.translation[j];
            }
            if(Math.abs(direction[2])<1e-9)return null;
            double scale=(height-center[2])/direction[2];
            double x=center[0]+scale*direction[0],y=center[1]+scale*direction[1];
            return scale>0&&Double.isFinite(x)&&Double.isFinite(y)?new Point(x,y):null;
        }finally{input.release();output.release();}
    }

    private boolean inWorkspace(YoloDetector.Detection d,WorkspaceTracker.Result pose){
        double x0=Double.POSITIVE_INFINITY,y0=x0,x1=Double.NEGATIVE_INFINITY,y1=x1;
        for(Point p:box(d)){
            Point q=project(p,pose);if(q==null)return false;
            x0=Math.min(x0,q.x);y0=Math.min(y0,q.y);x1=Math.max(x1,q.x);y1=Math.max(y1,q.y);
        }
        return !(x1<minX||y1<minY||x0>=maxX||y0>=maxY);
    }

    Result evaluate(List<YoloDetector.Detection> detections,WorkspaceTracker.Result pose){
        if(pose==null||!pose.supportsGuidance()||pose.rotation==null||pose.translation==null)
            return rejected("guidance_pose_required",0);
        List<YoloDetector.Detection> drivers=new ArrayList<>(),handles=new ArrayList<>();
        for(var d:detections){
            if(!validBox(d))return rejected("invalid_detection",0);
            if(d.classId()==0&&inWorkspace(d,pose))drivers.add(d);
            if(d.classId()==1)handles.add(d);
        }
        drivers=nms(drivers);
        List<YoloDetector.Detection> kept=new ArrayList<>();
        drivers.sort(Comparator.comparingDouble(YoloDetector.Detection::confidence).reversed()
            .thenComparingDouble(YoloDetector.Detection::x1).thenComparingDouble(YoloDetector.Detection::y1)
            .thenComparingDouble(YoloDetector.Detection::x2).thenComparingDouble(YoloDetector.Detection::y2));
        for(var driver:drivers){
            var handle=pickHandle(handles,driver);boolean duplicate=false;
            if(handle!=null)for(var other:kept)if(pickHandle(handles,other)==handle&&nested(other,driver,handle)){duplicate=true;break;}
            if(!duplicate)kept.add(driver);
        }
        drivers=kept;
        YoloDetector.Detection selectedHandle=null;
        if(drivers.size()>1&&!handles.isEmpty()){
            int links=0;YoloDetector.Detection selected=null;
            for(var driver:drivers)for(var handle:handles){
                int attached=0;
                for(Point end:ends(driver)){
                    double dx=Math.max(0,Math.max(handle.x1()-end.x,end.x-handle.x2()));
                    double dy=Math.max(0,Math.max(handle.y1()-end.y,end.y-handle.y2()));
                    if(Math.hypot(dx,dy)<=Math.max(4,.25*Math.min(handle.x2()-handle.x1(),handle.y2()-handle.y1())))attached++;
                }
                if(attached==1){links++;selected=driver;selectedHandle=handle;}
            }
            if(links==1)drivers=List.of(selected);else selectedHandle=null;
        }
        if(drivers.size()!=1)return rejected(drivers.isEmpty()?"tool_not_visible":"multiple_tool_candidates",drivers.size());
        var driver=drivers.get(0);var handle=selectedHandle!=null?selectedHandle:pickHandle(handles,driver);
        Point tip;int source;
        if(handle!=null&&(selectedHandle!=null||inWorkspace(handle,pose))){tip=project(guidedTip(driver,handle),pose);source=2;}
        else{
            Point[] ends=ends(driver);Point a=project(ends[0],pose),b=project(ends[1],pose);
            if(a==null||b==null)return rejected("tool_position_unknown",1);
            tip=nearestDistance(a)<=nearestDistance(b)?a:b;source=1;
        }
        if(tip==null||tip.x<minX||tip.x>=maxX||tip.y<minY||tip.y>=maxY)return rejected("tool_outside_workspace",1);
        double[] distances=new double[4],scores=new double[4];
        for(int i=0;i<4;i++){distances[i]=distance(tip,targets[i]);scores[i]=1/(1+Math.exp(Math.max(-60,Math.min(60,(distances[i]-12)/4))));}
        return new Result(true,"ok",1,tip,distances,scores,source);
    }

    private static Result rejected(String reason,int count){return new Result(false,reason,count,null,new double[4],new double[4],0);}
    private double nearestDistance(Point p){double value=Double.POSITIVE_INFINITY;for(Point target:targets)value=Math.min(value,distance(p,target));return value;}
    private static double distance(Point a,Point b){return Math.hypot(a.x-b.x,a.y-b.y);}
    private static Point center(YoloDetector.Detection d){return new Point((d.x1()+d.x2())/2,(d.y1()+d.y2())/2);}
    private static boolean validBox(YoloDetector.Detection d){return Float.isFinite(d.x1())&&Float.isFinite(d.x2())&&Float.isFinite(d.y1())&&Float.isFinite(d.y2())&&Float.isFinite(d.confidence())&&d.confidence()>=0&&d.confidence()<=1&&d.x2()>d.x1()&&d.y2()>d.y1();}
    private static Point[] box(YoloDetector.Detection d){return new Point[]{new Point(d.x1(),d.y1()),new Point(d.x2(),d.y1()),new Point(d.x2(),d.y2()),new Point(d.x1(),d.y2())};}
    private static Point[] ends(YoloDetector.Detection d){
        MatOfPoint2f points=new MatOfPoint2f(box(d));
        try{
            Point[] q=new Point[4];Imgproc.minAreaRect(points).points(q);int index=0;
            for(int i=1;i<4;i++)if(distance(q[i],q[(i+1)%4])<distance(q[index],q[(index+1)%4]))index=i;
            return new Point[]{new Point((q[index].x+q[(index+1)%4].x)/2,(q[index].y+q[(index+1)%4].y)/2),
                new Point((q[(index+2)%4].x+q[(index+3)%4].x)/2,(q[(index+2)%4].y+q[(index+3)%4].y)/2)};
        }finally{points.release();}
    }
    private static Point guidedTip(YoloDetector.Detection driver,YoloDetector.Detection handle){Point[] p=ends(driver);return distance(p[0],center(handle))>=distance(p[1],center(handle))?p[0]:p[1];}
    private static YoloDetector.Detection pickHandle(List<YoloDetector.Detection> handles,YoloDetector.Detection driver){
        YoloDetector.Detection best=null;double score=Double.NEGATIVE_INFINITY;
        for(var h:handles){double value=h.confidence()-.002*distance(center(h),center(driver));if(value>score){best=h;score=value;}}
        return best;
    }
    private static boolean nested(YoloDetector.Detection best,YoloDetector.Detection fragment,YoloDetector.Detection handle){
        double w1=best.x2()-best.x1(),h1=best.y2()-best.y1(),w2=fragment.x2()-fragment.x1(),h2=fragment.y2()-fragment.y1();
        double s1=Math.min(w1,h1),s2=Math.min(w2,h2);
        if(Math.max(w1,h1)<2.5*s1||Math.max(w2,h2)<2.5*s2||(w1>=h1)!=(w2>=h2)||Math.min(s1,s2)<.5*Math.max(s1,s2)||best.confidence()-fragment.confidence()<.15)return false;
        double overlap=Math.max(0,Math.min(best.x2(),fragment.x2())-Math.max(best.x1(),fragment.x1()))*Math.max(0,Math.min(best.y2(),fragment.y2())-Math.max(best.y1(),fragment.y1()));
        return overlap>=.75*Math.min(w1*h1,w2*h2)&&distance(guidedTip(best,handle),guidedTip(fragment,handle))<=Math.min(6,.3*Math.min(s1,s2));
    }
    private static List<YoloDetector.Detection> nms(List<YoloDetector.Detection> boxes){
        if(boxes.size()<2)return boxes;
        Rect2d[] rects=new Rect2d[boxes.size()];float[] scores=new float[boxes.size()];
        for(int i=0;i<boxes.size();i++){var d=boxes.get(i);rects[i]=new Rect2d(d.x1(),d.y1(),d.x2()-d.x1(),d.y2()-d.y1());scores[i]=d.confidence();}
        MatOfRect2d rectangles=new MatOfRect2d(rects);MatOfFloat confidence=new MatOfFloat(scores);MatOfInt indices=new MatOfInt();
        try{Dnn.NMSBoxes(rectangles,confidence,0,.5f,indices);List<YoloDetector.Detection> result=new ArrayList<>();for(int i:indices.toArray())result.add(boxes.get(i));return result;}
        finally{rectangles.release();confidence.release();indices.release();}
    }
    public void close(){k.release();distortion.release();}
}
