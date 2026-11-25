package com.lucita.beastgate;

import android.content.Context;
import org.json.*;
import org.opencv.core.*;
import org.opencv.calib3d.Calib3d;
import org.opencv.imgproc.Imgproc;
import org.opencv.objdetect.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Camera-space diagnostic port of the frozen Windows workspace_projection.py. */
final class WorkspaceTracker implements AutoCloseable {
    static final int WIDTH=1280, HEIGHT=720;
    private final Mat k=new Mat(3,3,CvType.CV_64F);
    private final MatOfDouble distortion=new MatOfDouble();
    private final Map<Integer,Point3> world=new TreeMap<>();
    private final Map<String,Point3> targets=new TreeMap<>();
    private final ArucoDetector detector;
    private final ArucoDetector legacyDetector;
    private final MultiWindowCornerTracker partialBridge;

    static final class Result {
        final boolean valid;
        final String reason;
        final Map<Integer,Point[]> markers;
        final Map<String,Point> targets;
        final Map<String,double[]> cameraTargets;
        final double rms;
        final double maxError;
        final double[] rotation,translation;
        Result(boolean valid,String reason,Map<Integer,Point[]> markers,Map<String,Point> targets,Map<String,double[]> cameraTargets,double rms) {
            this(valid,reason,markers,targets,cameraTargets,rms,Double.NaN);
        }
        Result(boolean valid,String reason,Map<Integer,Point[]> markers,Map<String,Point> targets,Map<String,double[]> cameraTargets,double rms,double maxError) {
            this(valid,reason,markers,targets,cameraTargets,rms,maxError,null,null);
        }
        Result(boolean valid,String reason,Map<Integer,Point[]> markers,Map<String,Point> targets,Map<String,double[]> cameraTargets,double rms,double maxError,double[] rotation,double[] translation) {
            this.valid=valid; this.reason=reason; this.markers=markers; this.targets=targets; this.rms=rms;
            this.cameraTargets=cameraTargets;this.maxError=maxError;
            this.rotation=rotation==null?null:rotation.clone();this.translation=translation==null?null:translation.clone();
        }
        boolean supportsGuidance() {
            // Partial guidance is opt-in and requires the learned model's full validation.
            return valid&&(markers.size()>=5||(BuildConfig.PARTIAL_MARKER_CANDIDATE
                &&markers.size()>=3&&"learned_corners".equals(reason)));
        }
    }

    WorkspaceTracker(Context context) throws Exception { this(context,false); }
    WorkspaceTracker(Context context,boolean partialCandidate) throws Exception {
        byte[] bytes=read(context,"camera-profile.json");
        JSONObject camera=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        JSONObject workspace=new JSONObject(new String(read(context,"workspace-profile.json"),StandardCharsets.UTF_8));
        StringBuilder hash=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes)) hash.append(String.format(Locale.ROOT,"%02x",b&255));
        JSONObject binding=workspace.getJSONObject("target_registration");
        require(binding.getString("camera_profile_sha256").equals(hash.toString()),"profile_hash");
        require(binding.getString("camera_profile_id").equals(camera.getString("profile_id")),"profile_id");
        require(camera.getJSONArray("image_size").getInt(0)==WIDTH && camera.getJSONArray("image_size").getInt(1)==HEIGHT,"calibration_size");
        require(workspace.getString("axes").equals("x_right_y_away_z_up") && workspace.getString("units").equals("mm"),"axes");
        double[] matrix=new double[9];
        for(int row=0;row<3;row++) for(int col=0;col<3;col++) matrix[row*3+col]=camera.getJSONArray("camera_matrix").getJSONArray(row).getDouble(col);
        k.put(0,0,matrix);
        double[] d=new double[5]; for(int i=0;i<5;i++) d[i]=camera.getJSONArray("distortion_coefficients").getDouble(i);
        distortion.fromArray(d);
        JSONObject markers=workspace.getJSONObject("marker_centers_mm");
        for(Iterator<String> it=markers.keys();it.hasNext();) {String id=it.next();world.put(Integer.parseInt(id),xyz(markers.getJSONArray(id)));}
        for(String name:new String[]{"A","B","C","D"}) targets.put(name,xyz(workspace.getJSONObject("targets_mm").getJSONArray(name)));
        detector=createDetector(partialCandidate);
        legacyDetector=partialCandidate?createDetector(false):null;
        partialBridge=partialCandidate?new MultiWindowCornerTracker(this):null;
    }
    private static ArucoDetector createDetector(boolean precise) {
        DetectorParameters p=new DetectorParameters();
        p.set_adaptiveThreshWinSizeMin(3); p.set_adaptiveThreshWinSizeMax(53); p.set_adaptiveThreshWinSizeStep(4);
        p.set_minMarkerPerimeterRate(.015); p.set_maxMarkerPerimeterRate(4); p.set_polygonalApproxAccuracyRate(.03);
        p.set_cornerRefinementMethod(precise?Objdetect.CORNER_REFINE_APRILTAG:Objdetect.CORNER_REFINE_SUBPIX);
        return new ArucoDetector(Objdetect.getPredefinedDictionary(Objdetect.DICT_4X4_50),p);
    }
    private static byte[] read(Context c,String name)throws Exception {try(java.io.InputStream in=c.getAssets().open(name)){return in.readAllBytes();}}
    private static Point3 xyz(JSONArray a)throws JSONException{return new Point3(a.getDouble(0),a.getDouble(1),a.getDouble(2));}
    private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
    private static boolean finite(double... values){for(double v:values)if(!Double.isFinite(v))return false;return true;}
    private static Result rejected(String reason,Map<Integer,Point[]> markers){return new Result(false,reason,markers,Collections.emptyMap(),Collections.emptyMap(),Double.NaN);}

    synchronized Result process(Mat gray) {
        Map<Integer,Point[]> found=new TreeMap<>();
        List<Mat> corners=new ArrayList<>(); Mat ids=new Mat();
        try {
            detector.detectMarkers(gray,corners,ids);
            for(int i=0;i<ids.rows();i++) {
                int id=(int)ids.get(i,0)[0];
                if(!world.containsKey(id))continue;
                Point[] quad=new Point[4];
                for(int j=0;j<4;j++){double[] xy=corners.get(i).get(0,j);quad[j]=new Point(xy[0],xy[1]);}
                if(found.put(id,quad)!=null){resetPartialTracking();return rejected("duplicate_id",found);}
            }
            if(partialBridge!=null&&gray.cols()==WIDTH&&gray.rows()==HEIGHT) {
                Result precise=partialBridge.update(android.os.SystemClock.elapsedRealtime(),found);
                if(precise.valid)return precise;
                Result legacy=legacyEstimate(gray);
                return legacy.valid?legacy:precise;
            }
            return estimate(found,gray.cols(),gray.rows());
        }catch(CvException e){return rejected("detect_error",found);}
        finally{ids.release();for(Mat m:corners)m.release();}
    }

    private Result legacyEstimate(Mat gray) {
        List<Mat> corners=new ArrayList<>();Mat ids=new Mat();Map<Integer,Point[]> found=new TreeMap<>();
        try {
            legacyDetector.detectMarkers(gray,corners,ids);
            for(int i=0;i<ids.rows();i++) {
                int id=(int)ids.get(i,0)[0];if(!world.containsKey(id))continue;
                Point[] quad=new Point[4];
                for(int j=0;j<4;j++){double[] xy=corners.get(i).get(0,j);quad[j]=new Point(xy[0],xy[1]);}
                if(found.put(id,quad)!=null)return rejected("duplicate_id",found);
            }
            return estimate(found,gray.cols(),gray.rows());
        }finally{ids.release();for(Mat m:corners)m.release();}
    }

    Result estimate(Map<Integer,Point[]> detections,int width,int height) {
        try(NativeScope s=new NativeScope()) {
            require(width==WIDTH&&height==HEIGHT,"resolution_mismatch");
            List<Integer> ids=new ArrayList<>();
            for(int id:world.keySet())if(detections.containsKey(id))ids.add(id);
            require(ids.size()>=4,"need_four_markers");
            Point[] observed=new Point[ids.size()];
            for(int i=0;i<ids.size();i++)observed[i]=center(detections.get(ids.get(i)),s);
            return estimateCenters(detections,ids,observed);
        }catch(IllegalArgumentException|CvException e){return rejected(e.getMessage(),detections);}
    }

    Result estimateTransferred(Map<Integer,Point[]> real,Map<Integer,Point> centers) {
        List<Integer> ids=new ArrayList<>(centers.keySet());Collections.sort(ids);
        if(ids.size()<5||!world.keySet().containsAll(ids))return rejected("invalid_transfer_ids",real);
        return estimateCenters(real,ids,ids.stream().map(centers::get).toArray(Point[]::new));
    }

    private Result estimateCenters(Map<Integer,Point[]> detections,List<Integer> ids,Point[] observed) {
        Point3[] objects=new Point3[ids.size()];
        for(int i=0;i<ids.size();i++)objects[i]=world.get(ids.get(i));
        return estimateCorrespondences(detections,objects,observed,3.2,5);
    }

    private Result estimateCorrespondences(Map<Integer,Point[]> detections,Point3[] objects,Point[] observed,double rmsLimit,double maxLimit) {
        double measuredRms=Double.NaN,measuredMax=Double.NaN;
        try(NativeScope s=new NativeScope()) {
            requireSupport(objects,s); requireSpread(observed,s);
            MatOfPoint3f obj=s.own(new MatOfPoint3f(objects));MatOfPoint2f obs=s.own(new MatOfPoint2f(observed));
            MatOfDouble zero=s.own(new MatOfDouble());
            List<Mat> rs=new ArrayList<>(),ts=new ArrayList<>();
            try { Calib3d.solvePnPGeneric(obj,obs,k,zero,rs,ts,false,Calib3d.SOLVEPNP_IPPE); }
            finally { for(Mat m:rs)s.own(m);for(Mat m:ts)s.own(m); }
            List<Pose> candidates=new ArrayList<>();
            for(int i=0;i<rs.size();i++){Pose p=score(rs.get(i),ts.get(i),obj,observed,zero,s);if(p!=null)candidates.add(p);}
            require(!candidates.isEmpty(),"no_physical_pose");
            candidates.sort(Comparator.comparingDouble(p->p.rms));Pose best=candidates.get(0);
            measuredRms=best.rms;measuredMax=best.max;
            if(candidates.size()>1) {
                Pose other=candidates.get(1);double trace=0,dist=0;
                for(int i=0;i<9;i++)trace+=best.rotation[i]*other.rotation[i];
                for(int i=0;i<3;i++)dist+=Math.pow(best.position[i]-other.position[i],2);
                double angle=Math.toDegrees(Math.acos(Math.max(-1,Math.min(1,(trace-1)/2))));
                require(!(other.rms-best.rms<.25&&(angle>2||Math.sqrt(dist)>5)),"ambiguous_pose");
            }
            Mat r=s.own(best.r.clone()),t=s.own(best.t.clone());
            Calib3d.solvePnPRefineLM(obj,obs,k,zero,r,t);
            best=score(r,t,obj,observed,zero,s);
            require(best!=null,"invalid_refinement");
            measuredRms=best.rms;measuredMax=best.max;
            require(best.rms<=rmsLimit&&best.max<=maxLimit,"reprojection_limit");
            Map<String,Point> pixels=new TreeMap<>();
            Map<String,double[]> cameraPoints=new TreeMap<>();
            for(Map.Entry<String,Point3> entry:targets.entrySet()) {
                Point3 p=entry.getValue();
                double depth=best.rotation[6]*p.x+best.rotation[7]*p.y+best.rotation[8]*p.z+t.get(2,0)[0];
                if(depth<=0)continue;
                MatOfPoint2f out=s.own(new MatOfPoint2f());
                Calib3d.projectPoints(s.own(new MatOfPoint3f(p)),r,t,k,distortion,out);
                Point q=out.toArray()[0];
                if(finite(q.x,q.y)&&q.x>=0&&q.x<WIDTH&&q.y>=0&&q.y<HEIGHT){
                    pixels.put(entry.getKey(),q);
                    double[] xyz=new double[3];
                    for(int axis=0;axis<3;axis++)xyz[axis]=best.rotation[axis*3]*p.x+best.rotation[axis*3+1]*p.y+best.rotation[axis*3+2]*p.z+t.get(axis,0)[0];
                    cameraPoints.put(entry.getKey(),xyz);
                }
            }
            double[] translation=new double[3];t.get(0,0,translation);
            return new Result(true,"tracking",detections,pixels,cameraPoints,best.rms,best.max,best.rotation,translation);
        } catch(IllegalArgumentException|CvException e) {
            return new Result(false,e.getMessage(),detections,Collections.emptyMap(),Collections.emptyMap(),measuredRms,measuredMax);
        }
    }

    Map<Integer,Point> markerCenters(Map<Integer,Point[]> detections) {
        try(NativeScope s=new NativeScope()) {
            require(world.keySet().containsAll(detections.keySet()),"unknown_marker");
            Map<Integer,Point> result=new TreeMap<>();
            for(var entry:detections.entrySet())result.put(entry.getKey(),center(entry.getValue(),s));
            return result;
        }
    }

    Map<Integer,Point3[]> inferCornerMap(Map<Integer,Point[]> real,Result pose) {
        require(pose.valid&&real.size()>=5&&pose.rotation!=null,"invalid_map_seed");
        Map<Integer,Point3[]> map=new TreeMap<>();
        double[] position=new double[3];
        for(int i=0;i<3;i++)for(int j=0;j<3;j++)position[i]-=pose.rotation[j*3+i]*pose.translation[j];
        try(NativeScope s=new NativeScope()) {
            for(var entry:real.entrySet()) {
                center(entry.getValue(),s);
                MatOfPoint2f out=s.own(new MatOfPoint2f());
                Calib3d.undistortPoints(s.own(new MatOfPoint2f(entry.getValue())),out,k,distortion);
                Point[] normalized=out.toArray();Point3[] corners=new Point3[4];
                for(int n=0;n<4;n++) {
                    double[] ray={normalized[n].x,normalized[n].y,1},direction=new double[3];
                    for(int i=0;i<3;i++)for(int j=0;j<3;j++)direction[i]+=pose.rotation[j*3+i]*ray[j];
                    require(Math.abs(direction[2])>1e-9,"parallel_ray");
                    double distance=-position[2]/direction[2];
                    require(Double.isFinite(distance)&&distance>0,"invalid_ray");
                    corners[n]=new Point3(position[0]+distance*direction[0],position[1]+distance*direction[1],0);
                }
                map.put(entry.getKey(),corners);
            }
        }
        return map;
    }

    // Two-marker calls are sensitivity checks only; the candidate requires 3+ to display.
    Result estimateCornerSubset(Map<Integer,Point[]> real,Map<Integer,Point3[]> geometry) {
        try(NativeScope s=new NativeScope()) {
            require(real.size()>=2&&geometry.keySet().containsAll(real.keySet()),"invalid_corner_ids");
            List<Point3> objects=new ArrayList<>();List<Point> observed=new ArrayList<>();
            var undistorted=undistortedQuads(real);
            for(int id:new TreeSet<>(real.keySet())) {
                center(real.get(id),s);
                Point3[] quad=geometry.get(id);require(quad!=null&&quad.length==4,"invalid_map_quad");
                double area=0,sign=0;
                for(int i=0;i<4;i++) {
                    Point3 a=quad[i],b=quad[(i+1)%4],c=quad[(i+2)%4];
                    require(a!=null&&b!=null&&c!=null&&finite(a.x,a.y,a.z)&&a.z==0,"invalid_map_quad");
                    double cross=(b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x);
                    require(cross!=0&&(i==0||cross*sign>0),"nonconvex_map");sign=cross;
                    area+=a.x*b.y-a.y*b.x;
                }
                require(area < -2,"map_winding");
                Collections.addAll(objects,quad);Collections.addAll(observed,undistorted.get(id));
            }
            return estimateCorrespondences(real,objects.toArray(new Point3[0]),observed.toArray(new Point[0]),1.5,3);
        }catch(IllegalArgumentException|CvException e){return rejected(e.getMessage(),real);}
    }
    Map<Integer,Point[]> undistortedQuads(Map<Integer,Point[]> detections) {
        try(NativeScope s=new NativeScope()) {
            Map<Integer,Point[]> result=new TreeMap<>();
            for(var entry:detections.entrySet()) {
                MatOfPoint2f out=s.own(new MatOfPoint2f());
                Calib3d.undistortPoints(s.own(new MatOfPoint2f(entry.getValue())),out,k,distortion,s.own(new Mat()),k);
                result.put(entry.getKey(),out.toArray());
            }
            return result;
        }
    }
    Point3 markerPosition(int id){return world.get(id);}
    boolean noncollinearCenters(Set<Integer> ids) {
        if(!world.keySet().containsAll(ids))return false;
        try(NativeScope s=new NativeScope()) {
            double x=0,y=0;for(int id:ids){x+=world.get(id).x;y+=world.get(id).y;}
            Mat points=s.own(new Mat(ids.size(),2,CvType.CV_64F));int row=0;
            for(int id:ids){Point3 p=world.get(id);points.put(row++,0,p.x-x/ids.size(),p.y-y/ids.size());}
            Mat singular=s.own(new Mat());Core.SVDecomp(points,singular,s.own(new Mat()),s.own(new Mat()),Core.SVD_NO_UV);
            double largest=singular.get(0,0)[0];return largest>0&&singular.get(1,0)[0]/largest>=.05;
        }
    }
    synchronized void resetPartialTracking(){if(partialBridge!=null)partialBridge.reset();}

    private Point center(Point[] quad,NativeScope s) {
        require(quad!=null&&quad.length==4,"bad_corners");
        for(Point p:quad)require(p!=null&&finite(p.x,p.y)&&p.x>=0&&p.x<WIDTH&&p.y>=0&&p.y<HEIGHT,"bad_corners");
        MatOfPoint2f und=s.own(new MatOfPoint2f());
        Calib3d.undistortPoints(s.own(new MatOfPoint2f(quad)),und,k,distortion,s.own(new Mat()),k);
        Point[] q=und.toArray();double sign=0,area=0;
        for(int i=0;i<4;i++) {
            Point a=q[i],b=q[(i+1)%4],c=q[(i+2)%4];
            double cross=(b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x);
            require(finite(cross)&&cross!=0&&(i==0||cross*sign>0),"nonconvex_corners");sign=cross;
            area+=a.x*b.y-a.y*b.x;
        }
        require(Math.abs(area)/2>=4,"tiny_marker");
        double[] first=line(q[0],q[2]),second=line(q[1],q[3]);
        double z=first[0]*second[1]-first[1]*second[0];
        require(Math.abs(z)>=1e-9,"bad_diagonals");
        return new Point((first[1]*second[2]-first[2]*second[1])/z,(first[2]*second[0]-first[0]*second[2])/z);
    }
    private static double[] line(Point a,Point b){return new double[]{a.y-b.y,b.x-a.x,a.x*b.y-a.y*b.x};}
    private static void requireSpread(Point[] points,NativeScope s) {
        double x=0,y=0;Set<String> unique=new HashSet<>();
        for(Point p:points){x+=p.x;y+=p.y;unique.add(p.x+","+p.y);}
        require(unique.size()==points.length,"duplicate_points");x/=points.length;y/=points.length;
        Mat centered=s.own(new Mat(points.length,2,CvType.CV_64F));
        for(int i=0;i<points.length;i++)centered.put(i,0,points[i].x-x,points[i].y-y);
        Mat singular=s.own(new Mat());Core.SVDecomp(centered,singular,s.own(new Mat()),s.own(new Mat()),Core.SVD_NO_UV);
        require(singular.get(0,0)[0]>=1&&singular.get(1,0)[0]/singular.get(0,0)[0]>=.03,"insufficient_spread");
    }
    private static void requireSupport(Point3[] objects,NativeScope s) {
        Point[] points=new Point[objects.length];double x=0,y=0,scale=0;
        for(int i=0;i<points.length;i++){points[i]=new Point(objects[i].x,objects[i].y);x+=points[i].x;y+=points[i].y;}
        requireSpread(points,s);x/=points.length;y/=points.length;
        for(Point p:points)scale+=Math.pow(p.x-x,2)+Math.pow(p.y-y,2);
        scale=Math.sqrt(scale/points.length);
        Mat design=s.own(Mat.zeros(2*points.length,9,CvType.CV_64F));
        for(int i=0;i<points.length;i++) {
            double a=(points[i].x-x)/scale,b=(points[i].y-y)/scale;
            design.put(2*i,0,a,b,1,0,0,0,-a*a,-a*b,-a);
            design.put(2*i+1,0,0,0,0,a,b,1,-b*a,-b*b,-b);
        }
        Mat w=s.own(new Mat());Core.SVDecomp(design,w,s.own(new Mat()),s.own(new Mat()),Core.SVD_NO_UV);
        int rank=0;for(int i=0;i<w.rows();i++)if(w.get(i,0)[0]>1e-10)rank++;
        require(rank>=8,"degenerate_ippe_geometry");
    }
    private Pose score(Mat r,Mat t,MatOfPoint3f obj,Point[] observed,MatOfDouble zero,NativeScope s) {
        if(!Core.checkRange(r)||!Core.checkRange(t))return null;
        Mat rotation=s.own(new Mat());Calib3d.Rodrigues(r,rotation);
        double[] a=new double[9],v=new double[3],position=new double[3];rotation.get(0,0,a);t.get(0,0,v);
        for(int i=0;i<3;i++)for(int j=0;j<3;j++)position[i]-=a[j*3+i]*v[j];
        if(position[2]<=0)return null;
        for(Point3 p:obj.toArray())if(a[6]*p.x+a[7]*p.y+a[8]*p.z+v[2]<=0)return null;
        MatOfPoint2f projected=s.own(new MatOfPoint2f());Calib3d.projectPoints(obj,r,t,k,zero,projected);
        Point[] actual=projected.toArray();double sum=0,max=0;
        for(int i=0;i<actual.length;i++){double e=Math.hypot(actual[i].x-observed[i].x,actual[i].y-observed[i].y);if(!finite(e))return null;sum+=e*e;max=Math.max(max,e);}
        return new Pose(r,t,a,position,Math.sqrt(sum/actual.length),max);
    }
    private record Pose(Mat r,Mat t,double[] rotation,double[] position,double rms,double max) {}
    private static final class NativeScope implements AutoCloseable {
        private final List<Mat> mats=new ArrayList<>();
        <T extends Mat>T own(T mat){mats.add(mat);return mat;}
        public void close(){for(Mat m:mats)m.release();}
    }
    public void close(){k.release();distortion.release();detector.clear();if(legacyDetector!=null)legacyDetector.clear();}
}
