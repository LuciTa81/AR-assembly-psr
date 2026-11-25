package com.lucita.beastgate;

import androidx.test.platform.app.InstrumentationRegistry;
import java.util.*;
import org.json.*;
import org.junit.Test;
import org.opencv.android.OpenCVLoader;
import org.opencv.core.Point;
import static org.junit.Assert.*;

public class ToolEvidenceTest {
    @Test public void matchesFrozenPythonGeometryAndSingleToolSelection()throws Exception{
        assertTrue(OpenCVLoader.initLocal());
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        JSONArray poses,cases;
        try(var in=context.getAssets().open("pose-fixtures.json")){poses=new JSONArray(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        try(var in=InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("tool-evidence-fixtures.json")){cases=new JSONArray(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        try(var tracker=new WorkspaceTracker(context);var evidence=new ToolEvidence(context)){
            for(int i=0;i<cases.length();i++){
                JSONObject sample=cases.getJSONObject(i),fixture=poses.getJSONObject(sample.getInt("pose_index"));
                Map<Integer,Point[]> points=new TreeMap<>();JSONObject raw=fixture.getJSONObject("detections");
                for(var it=raw.keys();it.hasNext();){String id=it.next();JSONArray q=raw.getJSONArray(id);Point[] quad=new Point[4];for(int j=0;j<4;j++)quad[j]=new Point(q.getJSONArray(j).getDouble(0),q.getJSONArray(j).getDouble(1));points.put(Integer.parseInt(id),quad);}
                WorkspaceTracker.Result pose=tracker.estimate(points,1280,720);assertTrue(pose.valid);
                List<YoloDetector.Detection> boxes=new ArrayList<>();JSONArray rawBoxes=sample.getJSONArray("boxes");
                for(int j=0;j<rawBoxes.length();j++){JSONArray d=rawBoxes.getJSONArray(j);boxes.add(new YoloDetector.Detection(d.getInt(0),(float)d.getDouble(1),(float)d.getDouble(2),(float)d.getDouble(3),(float)d.getDouble(4),(float)d.getDouble(5)));}
                var result=evidence.evaluate(boxes,pose);
                String label=i+" "+sample.getString("scenario");
                assertEquals(label,sample.getInt("driver_count"),result.driverCount());
                boolean expected=sample.getInt("driver_count")==1;
                assertEquals(label,expected,result.valid());
                if(expected){
                    assertEquals(label,sample.getInt("tip_source"),result.tipSource());
                    int current="ABCD".indexOf(sample.getString("target"));
                    for(int j=0;j<4;j++){
                        assertEquals(label,sample.getJSONArray("distances").getDouble(j),result.distances()[j],.05);
                        assertEquals(label,sample.getJSONArray("scores").getDouble(j),result.scores()[j],.005);
                        assertEquals(label,j==current,result.near(j));
                    }
                }
                var rejected=new WorkspaceTracker.Result(false,"no_pose",points,Map.of(),Map.of(),Double.NaN);
                assertFalse(evidence.evaluate(boxes,rejected).valid());
                Map<Integer,Point[]> four=new TreeMap<>(points);while(four.size()>4)four.remove(four.keySet().iterator().next());
                var fourPose=new WorkspaceTracker.Result(true,"tracking",four,pose.targets,pose.cameraTargets,pose.rms,pose.maxError,pose.rotation,pose.translation);
                assertFalse(evidence.evaluate(boxes,fourPose).valid());
            }
        }
    }
}
