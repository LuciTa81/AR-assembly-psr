package com.lucita.beastgate;

import android.content.Intent;
import android.graphics.*;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.*;
import org.json.*;
import org.junit.Test;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Point;
import static org.junit.Assert.*;

public class PartialGuidanceIntegrationTest {
    private JSONArray fixtures(String name,boolean testAssets)throws Exception {
        var instrument=InstrumentationRegistry.getInstrumentation();
        var context=testAssets?instrument.getContext():instrument.getTargetContext();
        try(var in=context.getAssets().open(name)) {
            return new JSONArray(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    private WorkspaceTracker.Result learned(int count)throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        JSONObject raw=fixtures("pose-fixtures.json",false).getJSONObject(0).getJSONObject("detections");
        var full=new TreeMap<Integer,Point[]>();
        for(int id:new int[]{0,1,2,4,5}) {
            JSONArray q=raw.getJSONArray(""+id);Point[] quad=new Point[4];
            for(int j=0;j<4;j++)quad[j]=new Point(q.getJSONArray(j).getDouble(0),q.getJSONArray(j).getDouble(1));
            full.put(id,quad);
        }
        try(var tracker=new WorkspaceTracker(InstrumentationRegistry.getInstrumentation().getTargetContext())) {
            var model=new MultiWindowCornerTracker(tracker);
            for(int i=0;i<8;i++)assertTrue(model.update(i*500,full).valid);
            var partial=new TreeMap<>(full);partial.remove(5);if(count==3)partial.remove(2);
            var result=model.update(4000,partial);
            assertTrue(result.reason,result.valid);assertEquals("learned_corners",result.reason);
            assertEquals(count,result.markers.size());return result;
        }
    }
    private List<YoloDetector.Detection> toolBoxes()throws Exception {
        JSONArray boxes=fixtures("tool-evidence-fixtures.json",true).getJSONObject(0).getJSONArray("boxes");
        var result=new ArrayList<YoloDetector.Detection>();
        for(int i=0;i<boxes.length();i++) {
            JSONArray b=boxes.getJSONArray(i);
            result.add(new YoloDetector.Detection(b.getInt(0),(float)b.getDouble(1),(float)b.getDouble(2),
                (float)b.getDouble(3),(float)b.getDouble(4),(float)b.getDouble(5)));
        }
        return result;
    }
    private WorkspaceTracker.Result framedForRendering(WorkspaceTracker.Result pose) {
        // The native middle fixture clips the lid above the eye surface. Translate
        // this rendering-only fixture, not the calibration or tracker observations.
        double[] translation=pose.translation.clone();translation[1]+=30;
        var cameraTargets=new TreeMap<String,double[]>();
        for(var entry:pose.cameraTargets.entrySet()) {
            double[] xyz=entry.getValue().clone();xyz[1]+=30;cameraTargets.put(entry.getKey(),xyz);
        }
        return new WorkspaceTracker.Result(pose.valid,pose.reason,pose.markers,pose.targets,cameraTargets,
            pose.rms,pose.maxError,pose.rotation,translation);
    }
    private static Object field(Object object,String name)throws Exception {
        var f=object.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(object);
    }
    private static void field(Object object,String name,Object value)throws Exception {
        var f=object.getClass().getDeclaredField(name);f.setAccessible(true);f.set(object,value);
    }
    private static Object call(MainActivity activity,String name)throws Exception {
        var m=MainActivity.class.getDeclaredMethod(name);m.setAccessible(true);return m.invoke(activity);
    }
    private interface ActivityCheck {void run(MainActivity activity,StereoOverlayView view)throws Exception;}
    private void withActivity(ActivityCheck check)throws Exception {
        var instrument=InstrumentationRegistry.getInstrumentation();
        var intent=new Intent(instrument.getTargetContext(),MainActivity.class).putExtra("screw_context",true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK);
        var activity=(MainActivity)instrument.startActivitySync(intent);
        try {
            instrument.runOnMainSync(()->{
                try {
                    assertNull(field(activity,"camera"));assertNull(field(activity,"remoteSupervisor"));
                    var view=new StereoOverlayView(activity);view.setScrewContextEnabled(true);view.layout(0,0,3840,1080);
                    field(activity,"stereoView",view);field(activity,"running",true);
                    field(activity,"assembly",new AssemblyProbe(SystemClock.elapsedRealtime(),4));
                    check.run(activity,view);
                    assertNull(field(activity,"camera"));
                    view.clear();field(activity,"running",false);
                } catch(Exception e) {throw new AssertionError(e);}
            });
        } finally {instrument.runOnMainSync(activity::finish);}
    }

    @Test public void learnedPosesReachToolEvidenceAndAllOutlineStages()throws Exception {
        org.junit.Assume.assumeTrue(BuildConfig.PARTIAL_MARKER_CANDIDATE);
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        var outline=new BoxOutline(context);var eyes=new EyeProjection(context);
        try(var evidence=new ToolEvidence(context)) {
            var boxes=toolBoxes();
            for(int count:new int[]{3,4}) {
                var pose=learned(count);var result=evidence.evaluate(boxes,pose);
                assertTrue(count+" markers: "+result.reason(),result.valid());
                assertTrue(result.near(0));for(int i=1;i<4;i++)assertFalse(result.near(i));
                assertNotNull(outline.project(0,pose,eyes));
                assertNull("out-of-eye lid must stay hidden",outline.project(1,pose,eyes));
                for(int stage=0;stage<4;stage++)
                    assertNotNull("outline stage "+stage,outline.project(stage,framedForRendering(pose),eyes));
            }
        }
    }

    @Test public void fullActivityRendersFourRingsAndReportsPartialTracking()throws Exception {
        org.junit.Assume.assumeTrue(BuildConfig.PARTIAL_MARKER_CANDIDATE);
        var poses=List.of(framedForRendering(learned(3)),framedForRendering(learned(4)));
        withActivity((activity,view)->{
            var bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);
            try {
                for(var pose:poses) {
                    field(activity,"latestPose",pose);field(activity,"latestPoseAt",SystemClock.elapsedRealtime());
                    call(activity,"renderAssembly");
                    assertNotNull("active ring",field(view,"pair"));
                    var points=(double[][][])field(view,"screwContext");assertNotNull("four rings",points);
                    assertEquals(4,points.length);assertNotNull("outline",field(view,"outline"));
                    view.draw(new Canvas(bitmap));
                    for(int i=0;i<4;i++)for(int eye=0;eye<2;eye++) {
                        int x=(int)Math.round(points[i][eye][0])+eye*1920;
                        int y=(int)Math.round(points[i][eye][1]),radius=i==0?21:16,lit=0;
                        for(int dx=-2;dx<=2;dx++)for(int dy=-2;dy<=2;dy++)
                            if(bitmap.getPixel(x+radius+dx,y+dy)!=Color.BLACK)lit++;
                        assertTrue("ring "+i+" eye "+eye,lit>0);
                    }
                    var status=new JSONObject((String)call(activity,"supervisorSnapshot"));
                    assertTrue(status.getBoolean("tracked"));assertTrue(status.getBoolean("overlay_visible"));
                    assertEquals(pose.markers.size(),status.getInt("markers"));
                }
            } finally {bitmap.recycle();}
        });
    }

    @Test public void preparationAcceptsPartialPoseButStaleAndRejectedDataStayHidden()throws Exception {
        org.junit.Assume.assumeTrue(BuildConfig.PARTIAL_MARKER_CANDIDATE);
        var pose=learned(4);
        withActivity((activity,view)->{
            field(activity,"latestPose",pose);field(activity,"latestPoseAt",SystemClock.elapsedRealtime());
            field(activity,"preparation",new PreparationGuide(SystemClock.elapsedRealtime()));
            call(activity,"renderAssembly");assertEquals(true,field(view,"preparationTracked"));
            field(activity,"preparation",null);
            for(long time:new long[]{SystemClock.elapsedRealtime()-1000,SystemClock.elapsedRealtime()+10000}) {
                field(activity,"latestPoseAt",time);call(activity,"renderAssembly");
                assertNull(field(view,"pair"));assertNull(field(view,"screwContext"));assertNull(field(view,"outline"));
                assertFalse(new JSONObject((String)call(activity,"supervisorSnapshot")).getBoolean("tracked"));
            }
            var rejected=new WorkspaceTracker.Result(false,"corner_pose_uncertain",pose.markers,Map.of(),Map.of(),Double.NaN);
            field(activity,"latestPose",rejected);field(activity,"latestPoseAt",SystemClock.elapsedRealtime());
            call(activity,"renderAssembly");assertNull(field(view,"pair"));assertNull(field(view,"screwContext"));
        });
    }

    @Test public void unvalidatedPartialAndRejectedPosesCannotAdvanceGuidance()throws Exception {
        var pose=learned(4);
        assertEquals(BuildConfig.PARTIAL_MARKER_CANDIDATE,pose.supportsGuidance());
        for(String reason:new String[]{"tracking","partial_marker_bridge","map_disagreement"}) {
            var unqualified=new WorkspaceTracker.Result(true,reason,pose.markers,pose.targets,pose.cameraTargets,
                pose.rms,pose.maxError,pose.rotation,pose.translation);
            assertFalse(reason,unqualified.supportsGuidance());
        }
        var two=new TreeMap<>(pose.markers);two.remove(0);two.remove(1);
        var insufficient=new WorkspaceTracker.Result(true,"learned_corners",two,pose.targets,pose.cameraTargets,
            pose.rms,pose.maxError,pose.rotation,pose.translation);
        assertFalse(insufficient.supportsGuidance());
        var rejected=new WorkspaceTracker.Result(false,"learned_corners",pose.markers,pose.targets,pose.cameraTargets,
            pose.rms,pose.maxError,pose.rotation,pose.translation);
        assertFalse(rejected.supportsGuidance());
    }
}
