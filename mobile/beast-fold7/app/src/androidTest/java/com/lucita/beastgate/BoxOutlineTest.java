package com.lucita.beastgate;

import android.content.Context;
import android.graphics.*;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.*;
import org.junit.Test;
import java.util.*;
import org.opencv.core.Point;
import static org.junit.Assert.*;

public class BoxOutlineTest {
    private Context context(){return InstrumentationRegistry.getInstrumentation().getTargetContext();}
    private JSONObject json(String name)throws Exception{
        try(var in=context().getAssets().open(name)){return new JSONObject(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
    }
    private WorkspaceTracker.Result pose(int count,boolean valid,double[] r,double[] t){
        Map<Integer,Point[]> markers=new TreeMap<>();for(int i=0;i<count;i++)markers.put(i,new Point[0]);
        return new WorkspaceTracker.Result(valid,"fixture",markers,Map.of(),Map.of(),1,2,r,t);
    }
    private WorkspaceTracker.Result goodPose(){return pose(6,true,new double[]{1,0,0,0,-1,0,0,0,-1},new double[]{-200,250,700});}
    private int referenceIndex(JSONArray strokes,BoxOutline.Stroke actual)throws Exception{
        // Unity Array.Sort is unstable for equal emphasis levels; order is not geometry.
        for(int i=0;i<strokes.length();i++){
            JSONObject candidate=strokes.getJSONObject(i);JSONArray points=candidate.getJSONArray("points");
            if(candidate.getInt("level")!=actual.level()||points.length()!=actual.points().length)continue;
            boolean sameStart=true;
            for(int axis=0;axis<3;axis++)sameStart&=Math.abs(points.getJSONArray(0).getDouble(axis)-actual.points()[0][axis])<1e-9;
            if(sameStart)return i;
        }
        throw new AssertionError("No matching frozen stroke");
    }
    @Test public void stagesAndEveryWorldVertexMatchFrozenUnity()throws Exception{
        BoxOutline outline=new BoxOutline(context());
        JSONArray reference=json("box-outline-fixtures.json").getJSONArray("stages");
        int[] counts={20,20,20,32};double[] low={0,50,50,0},high={50,60,60,60};
        for(int stage=0;stage<4;stage++){
            var actual=outline.geometry(stage);JSONArray expected=reference.getJSONObject(stage).getJSONArray("strokes");
            assertEquals(counts[stage],actual.length);assertEquals(expected.length(),actual.length);
            Set<Integer> matched=new HashSet<>();
            double minimum=Double.POSITIVE_INFINITY,maximum=Double.NEGATIVE_INFINITY;
            for(int i=0;i<actual.length;i++){
                int index=referenceIndex(expected,actual[i]);assertTrue("Duplicate stroke",matched.add(index));
                JSONObject stroke=expected.getJSONObject(index);JSONArray points=stroke.getJSONArray("points");
                assertEquals(stroke.getInt("level"),actual[i].level());assertEquals(points.length(),actual[i].points().length);
                for(int j=0;j<points.length();j++)for(int axis=0;axis<3;axis++){
                    double value=actual[i].points()[j][axis];
                    assertEquals(points.getJSONArray(j).getDouble(axis),value,1e-9);
                    if(axis==2){minimum=Math.min(minimum,value);maximum=Math.max(maximum,value);}
                }
            }
            assertEquals(low[stage],minimum,0);assertEquals(high[stage],maximum,0);
        }
        assertEquals(0,BoxOutline.stage(0,0));assertEquals(1,BoxOutline.stage(1,0));
        for(int i=0;i<4;i++)assertEquals(2,BoxOutline.stage(2,i));
        assertEquals(3,BoxOutline.stage(2,4));assertEquals(-1,BoxOutline.stage(-1,-1));
        assertEquals(0,outline.geometry(-1).length);
    }
    @Test public void bothEyePixelsMatchReferenceGeometryAndCalibration()throws Exception{
        BoxOutline outline=new BoxOutline(context());EyeProjection eyes=new EyeProjection(context());
        JSONObject calibration=json("eye-projection.json");
        JSONArray reference=json("box-outline-fixtures.json").getJSONArray("stages");
        for(int stage=0;stage<4;stage++){
            var projected=outline.project(stage,goodPose(),eyes);assertNotNull(projected);
            JSONArray strokes=reference.getJSONObject(stage).getJSONArray("strokes");
            for(int i=0;i<projected.length;i++)for(int j=0;j<projected[i].eyes()[0].length;j++){
                JSONArray p=strokes.getJSONObject(referenceIndex(strokes,outline.geometry(stage)[i])).getJSONArray("points").getJSONArray(j);
                double[] camera={p.getDouble(0)-200,250-p.getDouble(1),700-p.getDouble(2),1};
                for(int eye=0;eye<2;eye++){
                    JSONArray matrix=calibration.getJSONArray(eye==0?"left_projection":"right_projection");
                    double[] homogeneous=new double[3];
                    for(int row=0;row<3;row++)for(int col=0;col<4;col++)homogeneous[row]+=matrix.getDouble(row*4+col)*camera[col];
                    for(int axis=0;axis<2;axis++)assertEquals(homogeneous[axis]/homogeneous[2],projected[i].eyes()[eye][j][axis],1e-7);
                }
            }
        }
    }
    @Test public void rejectedOrIncompletePoseNeverLeavesPartialOutline()throws Exception{
        BoxOutline outline=new BoxOutline(context());EyeProjection eyes=new EyeProjection(context());var good=goodPose();
        assertNull(outline.project(0,null,eyes));assertNull(outline.project(-1,good,eyes));
        assertNull(outline.project(0,pose(4,true,good.rotation,good.translation),eyes));
        assertNull(outline.project(0,pose(6,false,good.rotation,good.translation),eyes));
        assertNull(outline.project(0,pose(6,true,null,null),eyes));
        assertNull(outline.project(0,pose(6,true,good.rotation,new double[]{0,0,-1000}),eyes));
        assertNull(outline.project(0,pose(6,true,good.rotation,new double[]{100000,0,700}),eyes));
        assertNull(outline.project(0,pose(6,true,good.rotation,new double[]{Double.NaN,0,700}),eyes));
    }
    @Test public void cameraTransformAgreesWithTrackerForEveryFrozenPose()throws Exception{
        assertTrue(org.opencv.android.OpenCVLoader.initLocal());
        JSONArray samples;
        try(var in=context().getAssets().open("pose-fixtures.json")){samples=new JSONArray(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        JSONObject workspace=json("workspace-profile.json").getJSONObject("targets_mm");
        try(WorkspaceTracker tracker=new WorkspaceTracker(context())){
            for(int i=0;i<samples.length();i++){
                JSONObject detections=samples.getJSONObject(i).getJSONObject("detections");Map<Integer,Point[]> markers=new TreeMap<>();
                for(Iterator<String> ids=detections.keys();ids.hasNext();){
                    String id=ids.next();JSONArray quad=detections.getJSONArray(id);Point[] points=new Point[4];
                    for(int j=0;j<4;j++)points[j]=new Point(quad.getJSONArray(j).getDouble(0),quad.getJSONArray(j).getDouble(1));
                    markers.put(Integer.parseInt(id),points);
                }
                var result=tracker.estimate(markers,1280,720);assertTrue(result.reason,result.valid);
                for(String name:new String[]{"A","B","C","D"}){
                    JSONArray xyz=workspace.getJSONArray(name);double[] world={xyz.getDouble(0),xyz.getDouble(1),xyz.getDouble(2)};
                    assertArrayEquals(result.cameraTargets.get(name),BoxOutline.toCamera(world,result.rotation,result.translation),1e-9);
                }
            }
        }
    }
    @Test public void rejectsMismatchedCalibrationAndInvalidDimensions()throws Exception{
        JSONObject profile=BoxOutline.readProfile(context());
        for(String key:new String[]{"camera_profile_sha256","workspace_profile_sha256","lid_height_mm","corner_radius_mm","vertices_mm"}){
            JSONObject bad=new JSONObject(profile.toString());
            if(key.endsWith("sha256"))bad.put(key,"wrong");
            else if(key.equals("vertices_mm")){JSONArray v=bad.getJSONArray(key);v.put(14,2);}
            else bad.put(key,1000);
            try{new BoxOutline(context(),bad);fail("accepted "+key);}catch(IllegalArgumentException expected){assertTrue(expected.getMessage().startsWith("outline_"));}
        }
    }
    @Test public void canvasSeparatesEyesExpiresAndClearsWithoutChangingGreenAcknowledgement(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            StereoOverlayView view=new StereoOverlayView(context());view.layout(0,0,3840,1080);
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
            var stroke=new BoxOutline.ProjectedStroke(new double[][][]{{{400,400},{500,400}},{{600,400},{700,400}}},2);
            var strokes=new BoxOutline.ProjectedStroke[]{stroke};int[] acks={0};
            try{
                long now=SystemClock.elapsedRealtime();view.updateOutline(strokes,now);
                view.updateGuide(null,now,0,AssemblyProbe.Phase.RELEASE,(target,time)->acks[0]++);view.draw(canvas);
                assertEquals(Color.rgb(77,133,119),bitmap.getPixel(450,400));assertEquals(Color.rgb(77,133,119),bitmap.getPixel(2590,400));
                assertEquals(Color.BLACK,bitmap.getPixel(650,400));assertEquals(Color.BLACK,bitmap.getPixel(2390,400));assertEquals(0,acks[0]);
                view.updateOutline(strokes,now-1000);view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(450,400));
                view.updateOutline(strokes,now+10000);view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(450,400));
                view.updateOutline(strokes,SystemClock.elapsedRealtime());view.layout(0,0,1920,1080);view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(450,400));
                view.layout(0,0,3840,1080);view.updateOutline(null,now);view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(450,400));
                view.updateOutline(strokes,SystemClock.elapsedRealtime());view.clear();view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(450,400));
            }finally{view.clear();bitmap.recycle();}
        });
    }
    @Test public void renderSyntheticStageProofsWithoutCamera()throws Exception{
        BoxOutline outline=new BoxOutline(context());EyeProjection eyes=new EyeProjection(context());
        var pose=goodPose();
        java.io.File directory=new java.io.File(context().getExternalFilesDir(null),"outline-qa");
        assertTrue(directory.isDirectory()||directory.mkdirs());
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            StereoOverlayView view=new StereoOverlayView(context());view.layout(0,0,3840,1080);
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
            try{
                for(int stage=0;stage<4;stage++){
                    long now=SystemClock.elapsedRealtime();view.updateOutline(outline.project(stage,pose,eyes),now);
                    if(stage<2)view.updatePreparation(stage,now,true,null);
                    else if(stage==3)view.showInspection();
                    else view.updateGuide(eyes.project(new double[]{0,140,640}),now,0,AssemblyProbe.Phase.WORKING,null);
                    view.draw(canvas);
                    for(int eye=0;eye<2;eye++){
                        int pixels=0;for(int y=150;y<900;y++)for(int x=0;x<1920;x++)if(bitmap.getPixel(eye*1920+x,y)!=Color.BLACK)pixels++;
                        assertTrue("stage "+stage+" eye "+eye,pixels>500);
                    }
                    try(var stream=new java.io.FileOutputStream(new java.io.File(directory,"stage-"+stage+".png"))){assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,stream));}
                    catch(java.io.IOException error){throw new AssertionError(error);}
                }
            }finally{view.clear();bitmap.recycle();}
        });
    }
}
