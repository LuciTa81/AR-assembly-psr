package com.lucita.beastgate;

import android.content.Context;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Frozen Unity BoxOutlineProfile geometry, projected by the existing eye calibration. */
final class BoxOutline {
    record Stroke(double[][] points,int level) {}
    record ProjectedStroke(double[][][] eyes,int level) {}
    private final double[] vertices=new double[24];
    private final double radius,lidHeight;
    private final Stroke[][] stages=new Stroke[4][];

    BoxOutline(Context context)throws Exception { this(context,readProfile(context)); }
    BoxOutline(Context context,JSONObject profile)throws Exception {
        require(profile.getString("schema_version").equals("beast_box_outline_trial_v1")
            &&profile.getBoolean("candidate_only")&&profile.getBoolean("staged_rounded"),"outline_schema");
        for(String type:new String[]{"camera","workspace"})
            require(profile.getString(type+"_profile_sha256").equals(hash(read(context,type+"-profile.json"))),"outline_"+type+"_hash");
        JSONArray a=profile.getJSONArray("vertices_mm");require(a.length()==24,"outline_vertices");
        for(int i=0;i<24;i++){vertices[i]=a.getDouble(i);require(Double.isFinite(vertices[i])&&Math.abs(vertices[i])<=2000,"outline_vertex");}
        double top=vertices[2],bottom=vertices[14];
        require(bottom>=0&&top-bottom>=5&&top-bottom<=500,"outline_height");
        lidHeight=profile.getDouble("lid_height_mm");radius=profile.getDouble("corner_radius_mm");
        require(Double.isFinite(lidHeight)&&lidHeight>=1&&lidHeight<=top-bottom-5,"outline_lid_height");
        require(Double.isFinite(radius)&&radius>0,"outline_radius");
        for(int layer=0;layer<2;layer++)for(int i=0;i<4;i++){
            int p=layer*12+3*i,q=layer*12+3*((i+1)%4),r=layer*12+3*((i+2)%4);
            double x=vertices[q]-vertices[p],y=vertices[q+1]-vertices[p+1];
            double nx=vertices[r]-vertices[q],ny=vertices[r+1]-vertices[q+1],length=Math.hypot(x,y);
            require(Math.abs(vertices[p+2]-(layer==0?top:bottom))<1e-6,"outline_planarity");
            require(length>=10&&length<=1000&&x*ny-y*nx<-1&&Math.abs(x*nx+y*ny)<1e-6,"outline_rectangle");
            require(radius*4<=length,"outline_radius_large");
            if(layer==0)require(Math.abs(vertices[p]-vertices[p+12])<1e-6&&Math.abs(vertices[p+1]-vertices[p+13])<1e-6,"outline_upright");
        }
        double body=top-lidHeight;
        stages[0]=prism(bottom,body,2);
        stages[1]=prism(body,top,3);
        stages[2]=prism(body,top,2);
        List<Stroke> whole=new ArrayList<>(Arrays.asList(stages[0]));
        // The lid shares its bottom rim with the body's upper rim: draw the seam once.
        whole.addAll(Arrays.asList(stages[2]).subList(8,20));
        stages[3]=whole.toArray(new Stroke[0]);
    }
    static int stage(int preparation,int target){
        if(preparation==0||preparation==1)return preparation;
        return target>=0&&target<4?2:target==4?3:-1;
    }
    Stroke[] geometry(int stage){return stage>=0&&stage<4?stages[stage]:new Stroke[0];}

    ProjectedStroke[] project(int stage,WorkspaceTracker.Result pose,EyeProjection projection){
        if(stage<0||stage>3||pose==null||!pose.supportsGuidance()||projection==null
            ||!finite(pose.rotation,9)||!finite(pose.translation,3))return null;
        Stroke[] source=stages[stage];ProjectedStroke[] result=new ProjectedStroke[source.length];
        for(int i=0;i<source.length;i++){
            double[][] points=source[i].points();double[][][] eyes=new double[2][points.length][2];
            for(int j=0;j<points.length;j++){
                double[][] pair=projection.project(toCamera(points[j],pose.rotation,pose.translation));
                // Reject the complete outline if either eye cannot display any vertex.
                if(pair==null)return null;
                for(int eye=0;eye<2;eye++)eyes[eye][j]=pair[eye];
            }
            result[i]=new ProjectedStroke(eyes,source[i].level());
        }
        return result;
    }
    static double[] toCamera(double[] point,double[] rotation,double[] translation){
        double[] xyz=new double[3];
        for(int axis=0;axis<3;axis++)xyz[axis]=rotation[axis*3]*point[0]+rotation[axis*3+1]*point[1]+rotation[axis*3+2]*point[2]+translation[axis];
        return xyz;
    }
    private Stroke[] prism(double bottom,double top,int level){
        List<Stroke> lines=new ArrayList<>();
        rim(lines,bottom,level);rim(lines,top,level);
        for(int i=0;i<4;i++)lines.add(new Stroke(new double[][]{middle(i,bottom),middle(i,top)},level));
        return lines.toArray(new Stroke[0]);
    }
    private double[] point(int i,double z){return new double[]{vertices[3*i],vertices[3*i+1],z};}
    private double[] direction(int i){
        int next=(i+1)%4;double x=vertices[3*next]-vertices[3*i],y=vertices[3*next+1]-vertices[3*i+1],length=Math.hypot(x,y);
        return new double[]{x/length,y/length};
    }
    private double[] offset(double[] p,double[] d,double amount){return new double[]{p[0]+d[0]*amount,p[1]+d[1]*amount,p[2]};}
    private double[] middle(int i,double z){
        double[] p=point(i,z),prev=direction((i+3)%4),next=direction(i);
        return new double[]{p[0]+radius*(next[0]-prev[0])*.25,p[1]+radius*(next[1]-prev[1])*.25,z};
    }
    private void rim(List<Stroke> lines,double z,int level){
        for(int i=0;i<4;i++){
            double[] corner=point(i,z),start=offset(corner,direction((i+3)%4),-radius),end=offset(corner,direction(i),radius);
            double[][] curve=new double[9][];
            for(int j=0;j<9;j++){
                double t=j/8.0,u=1-t;
                curve[j]=new double[]{u*u*start[0]+2*u*t*corner[0]+t*t*end[0],u*u*start[1]+2*u*t*corner[1]+t*t*end[1],z};
            }
            lines.add(new Stroke(curve,level));
            lines.add(new Stroke(new double[][]{end,offset(point((i+1)%4,z),direction(i),-radius)},level));
        }
    }
    private static boolean finite(double[] a,int length){if(a==null||a.length!=length)return false;for(double v:a)if(!Double.isFinite(v))return false;return true;}
    static JSONObject readProfile(Context c)throws Exception{return new JSONObject(new String(read(c,"box-outline.json"),StandardCharsets.UTF_8));}
    private static byte[] read(Context c,String name)throws Exception{try(java.io.InputStream in=c.getAssets().open(name)){return in.readAllBytes();}}
    private static String hash(byte[] bytes)throws Exception{
        StringBuilder value=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))value.append(String.format(Locale.ROOT,"%02x",b&255));return value.toString();
    }
    private static void require(boolean valid,String reason){if(!valid)throw new IllegalArgumentException(reason);}
}
