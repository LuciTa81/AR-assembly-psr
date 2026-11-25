package com.lucita.beastgate;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.*;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Point;
import java.util.*;
import static org.junit.Assert.*;

public class PartialMarkerBridgeTest {
    private Map<Integer,Point[]> detections(JSONObject json) throws Exception {
        Map<Integer,Point[]> result=new TreeMap<>();
        for(Iterator<String> it=json.keys();it.hasNext();) {
            String key=it.next();JSONArray q=json.getJSONArray(key);Point[] points=new Point[4];
            for(int i=0;i<4;i++)points[i]=new Point(q.getJSONArray(i).getDouble(0),q.getJSONArray(i).getDouble(1));
            result.put(Integer.parseInt(key),points);
        }
        return result;
    }
    @Test public void matchesOfflinePartialReplayWithoutCamera() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        JSONArray fixtures;
        try(var input=instrumentation.getContext().getAssets().open("partial-marker-fixtures.json")) {
            fixtures=new JSONArray(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
        int accepted=0,rejected=0;
        try(var tracker=new WorkspaceTracker(instrumentation.getTargetContext())) {
            for(int i=0;i<fixtures.length();i++) {
                JSONObject f=fixtures.getJSONObject(i);
                var bridge=new PartialMarkerBridge(tracker);
                var first=detections(f.getJSONObject("anchor"));
                assertTrue(bridge.update(0,first).valid);
                var current=detections(f.getJSONObject("current"));
                var result=bridge.update(f.getLong("age_ms"),current);
                assertEquals("fixture "+i+" "+result.reason,f.getBoolean("valid"),result.valid);
                assertEquals(current.size(),result.markers.size());
                if(result.valid) {
                    accepted++;
                    JSONObject expected=f.getJSONObject("camera_targets");
                    for(String key:result.cameraTargets.keySet()) {
                        JSONArray xyz=expected.getJSONArray(key);
                        for(int j=0;j<3;j++)assertEquals("fixture "+i+" target "+key,xyz.getDouble(j),result.cameraTargets.get(key)[j],.15);
                    }
                } else {rejected++;assertTrue(result.cameraTargets.isEmpty());}
                bridge.reset();
                assertFalse(bridge.update(200,current).valid);
                bridge.reset();
                assertTrue(bridge.update(0,first).valid);
                assertFalse(bridge.update(PartialMarkerBridge.MAX_ANCHOR_MS+1,current).valid);
                bridge.reset();bridge.update(0,first);
                assertFalse(bridge.update(1,Map.of()).valid);
                var resumed=bridge.update(Math.max(2,f.getLong("age_ms")),current);
                assertEquals(result.valid,resumed.valid);
            }
        }
        assertTrue(accepted>20);assertTrue(rejected>5);
    }
}
