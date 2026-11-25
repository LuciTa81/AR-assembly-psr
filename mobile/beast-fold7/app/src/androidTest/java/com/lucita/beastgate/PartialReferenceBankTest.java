package com.lucita.beastgate;

import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.*;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Point;
import java.util.*;
import static org.junit.Assert.*;

public class PartialReferenceBankTest {
    private Map<Integer,Point[]> detections(JSONObject json) throws Exception {
        Map<Integer,Point[]> result=new TreeMap<>();
        for(Iterator<String> it=json.keys();it.hasNext();) {
            String key=it.next();JSONArray q=json.getJSONArray(key);Point[] points=new Point[4];
            for(int i=0;i<4;i++)points[i]=new Point(q.getJSONArray(i).getDouble(0),q.getJSONArray(i).getDouble(1));
            result.put(Integer.parseInt(key),points);
        }
        return result;
    }

    @Test public void matchesPastOnlyReplayAndResetsWithoutCamera() throws Exception {
        assertTrue(OpenCVLoader.initLocal());
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        JSONArray fixtures;
        try(var input=instrumentation.getContext().getAssets().open("reference-bank-fixtures.json")) {
            fixtures=new JSONArray(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
        int added=0;
        try(var tracker=new WorkspaceTracker(instrumentation.getTargetContext())) {
            for(int i=0;i<fixtures.length();i++) {
                JSONObject f=fixtures.getJSONObject(i);var bank=new PartialReferenceBank(tracker);
                JSONArray observations=f.getJSONArray("observations");
                WorkspaceTracker.Result result=null;Map<Integer,Point[]> current=Map.of();long time=0;
                for(int n=0;n<observations.length();n++) {
                    JSONObject row=observations.getJSONObject(n);time=row.getLong("time_ms");
                    current=detections(row.getJSONObject("detections"));
                    result=bank.update(time,current);
                    assertTrue(bank.referenceCount()<=6);
                    assertEquals(current.size(),result.markers.size());
                }
                assertNotNull(result);
                assertEquals("fixture "+i+" "+result.reason,f.getBoolean("valid"),result.valid);
                if(result.valid) {
                    assertEquals(4,result.cameraTargets.size());
                    JSONObject expected=f.getJSONObject("camera_targets");
                    for(String key:result.cameraTargets.keySet()) {
                        JSONArray xyz=expected.getJSONArray(key);
                        for(int j=0;j<3;j++)assertEquals("fixture "+i+" target "+key,
                            xyz.getDouble(j),result.cameraTargets.get(key)[j],.15);
                    }
                    if("partial_reference_bank".equals(result.reason))added++;
                }
                assertFalse(bank.update(time,current).valid);
                assertEquals(0,bank.referenceCount());
                bank.reset();assertFalse(bank.update(time+1,current).valid);
            }
        }
        assertTrue(added>0);
    }
}
