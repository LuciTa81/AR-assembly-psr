package com.lucita.beastgate;

import android.content.Context;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.*;
import org.opencv.objdetect.Objdetect;
import org.json.*;
import java.util.*;
import static org.junit.Assert.*;

public class WorkspaceTrackerTest {
    private Context context() { return InstrumentationRegistry.getInstrumentation().getTargetContext(); }
    private JSONArray fixtures() throws Exception {
        try (java.io.InputStream in = context().getAssets().open("pose-fixtures.json")) {
            return new JSONArray(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    private Map<Integer, Point[]> detections(JSONObject sample) throws Exception {
        Map<Integer, Point[]> result = new TreeMap<>();
        JSONObject items = sample.getJSONObject("detections");
        for (Iterator<String> it = items.keys(); it.hasNext();) {
            String id = it.next(); JSONArray points = items.getJSONArray(id); Point[] quad = new Point[4];
            for (int i=0; i<4; i++) quad[i] = new Point(points.getJSONArray(i).getDouble(0), points.getJSONArray(i).getDouble(1));
            result.put(Integer.parseInt(id), quad);
        }
        return result;
    }
    @Test public void matchesFrozenWindowsProjection() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        try (WorkspaceTracker tracker = new WorkspaceTracker(context())) {
            JSONArray samples = fixtures();
            for (int i=0; i<samples.length(); i++) {
                JSONObject sample = samples.getJSONObject(i);
                WorkspaceTracker.Result result = tracker.estimate(detections(sample), 1280, 720);
                assertTrue(result.reason, result.valid);
                JSONObject expected = sample.getJSONObject("targets");
                for (String key : new String[]{"A","B","C","D"}) {
                    JSONArray px = expected.getJSONObject(key).getJSONArray("pixel");
                    assertEquals(key, px.getDouble(0), result.targets.get(key).x, 0.05);
                    assertEquals(key, px.getDouble(1), result.targets.get(key).y, 0.05);
                    JSONArray xyz=sample.getJSONObject("camera_targets").getJSONArray(key);
                    for(int axis=0;axis<3;axis++)assertEquals(key,xyz.getDouble(axis),result.cameraTargets.get(key)[axis],0.05);
                }
            }
        }
    }
    @Test public void failsClosedForBadInput() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        try (WorkspaceTracker tracker = new WorkspaceTracker(context())) {
            Map<Integer, Point[]> good = detections(fixtures().getJSONObject(0));
            assertFalse(tracker.estimate(good, 1920, 1080).valid);
            Map<Integer, Point[]> three = new TreeMap<>(good);
            while (three.size()>3) three.remove(three.keySet().iterator().next());
            assertFalse(tracker.estimate(three, 1280, 720).valid);
            Map<Integer, Point[]> bad = detections(fixtures().getJSONObject(0));
            for (Point p: bad.values().iterator().next()) { p.x += 50; p.y -= 30; }
            assertFalse(tracker.estimate(bad,1280,720).valid);
            bad.values().iterator().next()[0].x = Double.NaN;
            assertFalse(tracker.estimate(bad,1280,720).valid);
            Map<Integer, Point[]> degenerate = new TreeMap<>();
            for (int id : new int[]{0,1,2,4}) degenerate.put(id, good.get(id));
            assertFalse(tracker.estimate(degenerate,1280,720).valid);
        }
    }
    @Test public void detectsGeneratedMarkerWithoutCamera() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        Mat marker=new Mat(), image=new Mat(720,1280,CvType.CV_8UC1,new Scalar(255));
        Mat roi=image.submat(200,400,400,600);
        try (WorkspaceTracker tracker = new WorkspaceTracker(context())) {
            Objdetect.generateImageMarker(Objdetect.getPredefinedDictionary(Objdetect.DICT_4X4_50), 4, 200, marker);
            marker.copyTo(roi);
            WorkspaceTracker.Result result=tracker.process(image);
            assertTrue(result.markers.containsKey(4));
            assertFalse(result.valid);
            assertTrue(result.targets.isEmpty());
        } finally { roi.release(); marker.release(); image.release(); }
    }

    @Test public void auditsEveryFourMarkerSubsetWithoutChangingPoseRules() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        try (WorkspaceTracker tracker = new WorkspaceTracker(context())) {
            JSONArray samples=fixtures();
            for(int sample=0;sample<samples.length();sample++){
                JSONObject fixture=samples.getJSONObject(sample);
                Map<Integer,Point[]> all=detections(fixture);
                int accepted=0,rejected=0;
                for(int a=0;a<3;a++)for(int b=a+1;b<4;b++)for(int c=b+1;c<5;c++)for(int d=c+1;d<6;d++){
                    Map<Integer,Point[]> subset=new TreeMap<>();
                    for(int id:new int[]{a,b,c,d})subset.put(id,all.get(id));
                    var result=tracker.estimate(subset,1280,720);
                    android.util.Log.i("BeastPoseAudit","pose="+fixture.getString("name")+" ids="+subset.keySet()+" valid="+result.valid+" reason="+result.reason+" rms="+result.rms);
                    if(a==0&&b==1&&c==2){
                        assertFalse("three collinear centers",result.valid);
                        assertEquals("degenerate_ippe_geometry",result.reason);rejected++;
                    }else{
                        assertTrue(subset.keySet()+": "+result.reason,result.valid);accepted++;
                    }
                }
                assertEquals(12,accepted);assertEquals(3,rejected);
            }
        }
    }

    @Test public void rejectedPoseKeepsErrorMetricsButNeverPublishesTargets() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        try(WorkspaceTracker tracker=new WorkspaceTracker(context())){
            Map<Integer,Point[]> input=detections(fixtures().getJSONObject(0));
            for(Point p:input.get(4)){p.x+=20;p.y-=10;}
            var result=tracker.estimate(input,1280,720);
            assertFalse(result.valid);assertEquals("reprojection_limit",result.reason);
            assertTrue(Double.isFinite(result.rms));assertTrue(Double.isFinite(result.maxError));
            assertTrue(result.rms>3.2||result.maxError>5);
            assertTrue(result.targets.isEmpty());assertTrue(result.cameraTargets.isEmpty());
        }
    }
}
