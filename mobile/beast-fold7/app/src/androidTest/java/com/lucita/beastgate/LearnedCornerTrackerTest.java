package com.lucita.beastgate;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.*;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Point;
import java.util.*;
import static org.junit.Assert.*;

public class LearnedCornerTrackerTest {
    @Test public void mixedFiveMarkerSetsDoNotEraseObservedMarker() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        Map<Integer,Point[]> full;
        try(var input=context.getAssets().open("pose-fixtures.json")) {
            full=detections(new JSONArray(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8))
                .getJSONObject(0).getJSONObject("detections"));
        }
        try(var tracker=new WorkspaceTracker(context)) {
            var model=new MultiWindowCornerTracker(tracker);
            for(int i=0;i<8;i++) {
                int[] ids=i%2==0?new int[]{0,2,3,4,5}:new int[]{0,1,2,4,5};
                var sample=new TreeMap<Integer,Point[]>();for(int id:ids)sample.put(id,full.get(id));
                assertTrue(model.update(i*500,sample).valid);
            }
            for(int missing:new int[]{4,5}) {
                var partial=new TreeMap<Integer,Point[]>();
                for(int id:new int[]{0,1,2,4,5})if(id!=missing)partial.put(id,full.get(id));
                var result=model.update(4000+(missing-4)*100,partial);
                assertTrue(result.reason,result.valid);assertEquals(4,result.markers.size());
                assertEquals("learned_corners",result.reason);
            }
        }
    }

    @Test public void markerSeenOnlyOnceIsNotInvented() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        Map<Integer,Point[]> full;
        try(var input=context.getAssets().open("pose-fixtures.json")) {
            full=detections(new JSONArray(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8))
                .getJSONObject(0).getJSONObject("detections"));
        }
        try(var tracker=new WorkspaceTracker(context)) {
            var model=new MultiWindowCornerTracker(tracker);
            for(int i=0;i<8;i++) {
                int[] ids=i==0?new int[]{0,1,2,4,5}:new int[]{0,2,3,4,5};
                var sample=new TreeMap<Integer,Point[]>();for(int id:ids)sample.put(id,full.get(id));
                model.update(i*500,sample);
            }
            var partial=new TreeMap<Integer,Point[]>();for(int id:new int[]{0,1,2,4})partial.put(id,full.get(id));
            var result=model.update(4000,partial);
            assertFalse(result.valid);assertEquals("map_marker_warmup",result.reason);
        }
    }

    private Map<Integer,Point[]> detections(JSONObject json) throws Exception {
        Map<Integer,Point[]> result=new TreeMap<>();
        for(Iterator<String> it=json.keys();it.hasNext();) {
            String key=it.next();JSONArray q=json.getJSONArray(key);Point[] points=new Point[4];
            for(int i=0;i<4;i++)points[i]=new Point(q.getJSONArray(i).getDouble(0),q.getJSONArray(i).getDouble(1));
            result.put(Integer.parseInt(key),points);
        }
        return result;
    }
    @Test public void matchesCornerReplayAndRejectsExpiredMapsWithoutCamera() throws Exception {
        runFixtures("learned-corner-fixtures.json",false);
    }
    @Test public void matchesMultiWindowReplayWithoutCamera() throws Exception {
        runFixtures("multi-corner-fixtures.json",true);
    }
    private void runFixtures(String filename,boolean multiMode) throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        var instrumentation=InstrumentationRegistry.getInstrumentation();JSONArray fixtures;
        try(var input=instrumentation.getContext().getAssets().open(filename)) {
            fixtures=new JSONArray(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
        int accepted=0,rejected=0;
        try(var tracker=new WorkspaceTracker(instrumentation.getTargetContext())) {
            for(int i=0;i<fixtures.length();i++) {
                JSONObject f=fixtures.getJSONObject(i);var model=new LearnedCornerTracker(tracker);
                var multi=new MultiWindowCornerTracker(tracker);
                JSONArray rows=f.getJSONArray("observations");WorkspaceTracker.Result result=null;
                long time=0;Map<Integer,Point[]> current=Map.of();
                for(int n=0;n<rows.length();n++) {
                    var row=rows.getJSONObject(n);time=row.getLong("time_ms");current=detections(row.getJSONObject("detections"));
                    result=multiMode?multi.update(time,current):model.update(time,current);assertEquals(current.size(),result.markers.size());
                }
                assertNotNull(result);assertEquals("fixture "+i+" "+result.reason,f.getBoolean("valid"),result.valid);
                if(result.valid) {
                    accepted++;assertEquals(4,result.cameraTargets.size());
                    JSONObject expected=f.getJSONObject("camera_targets");
                    for(String key:result.cameraTargets.keySet())for(int j=0;j<3;j++)
                        assertEquals("fixture "+i+" "+key,expected.getJSONArray(key).getDouble(j),result.cameraTargets.get(key)[j],.15);
                }else rejected++;
                assertFalse((multiMode?multi.update(time+30001,current):model.update(time+30001,current)).valid);
                model.reset();multi.reset();assertFalse((multiMode?multi.update(0,current):model.update(0,current)).valid);
            }
        }
        assertTrue(accepted>0);assertTrue(rejected>0);
    }
}
