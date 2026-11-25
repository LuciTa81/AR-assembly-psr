package com.lucita.beastgate;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.*;
import org.junit.Test;
import org.opencv.android.OpenCVLoader;
import org.opencv.android.Utils;
import org.opencv.core.Mat;
import java.util.List;
import static org.junit.Assert.*;

public class YoloDetectorTest {
    @Test public void recordedFramesMatchDesktopOnnx()throws Exception{
        assertTrue(OpenCVLoader.initLocal());
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        var assets=instrumentation.getContext().getAssets();
        JSONArray samples;
        try(var in=assets.open("yolo-fixtures.json")){samples=new JSONArray(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));}
        try(YoloDetector detector=new YoloDetector(instrumentation.getTargetContext())){
            for(int sample=0;sample<samples.length();sample++){
                JSONObject item=samples.getJSONObject(sample);
                Bitmap bitmap;
                try(var in=assets.open(item.getString("image"))){bitmap=BitmapFactory.decodeStream(in);}
                Mat rgba=new Mat();
                try{
                    Utils.bitmapToMat(bitmap,rgba);
                    long start=SystemClock.elapsedRealtime();
                    float[] prepared=YoloDetector.prepare(rgba),reference=new float[prepared.length];
                    try(var in=assets.open(item.getString("image")+".f32")){
                        java.nio.ByteBuffer.wrap(in.readAllBytes()).order(java.nio.ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(reference);
                    }
                    int differences=0;float maxDifference=0;
                    for(int i=0;i<prepared.length;i++)if(prepared[i]!=reference[i]){differences++;maxDifference=Math.max(maxDifference,Math.abs(prepared[i]-reference[i]));}
                    android.util.Log.i("BeastYoloTest","preprocess="+item.getString("image")+" different="+differences+" max="+maxDifference);
                    assertArrayEquals("desktop preprocessing",reference,prepared,0f);
                    float[][] raw=detector.run(prepared);
                    long ms=SystemClock.elapsedRealtime()-start;
                    JSONArray indices=item.getJSONArray("indices"),expectedRaw=item.getJSONArray("raw");
                    for(int i=0;i<indices.length();i++)for(int channel=0;channel<7;channel++)
                        assertEquals(expectedRaw.getJSONArray(i).getDouble(channel),raw[channel][indices.getInt(i)],channel<4?.3:.003);
                    List<YoloDetector.Detection> boxes=YoloDetector.decode(raw);
                    JSONArray expected=item.getJSONArray("detections");
                    assertEquals(expected.length(),boxes.size());
                    for(int i=0;i<expected.length();i++){
                        JSONArray e=expected.getJSONArray(i);boolean found=false;
                        for(var d:boxes)if(d.classId()==e.getInt(5)&&Math.abs(d.x1()-e.getDouble(0))<.6&&Math.abs(d.y1()-e.getDouble(1))<.6
                            &&Math.abs(d.x2()-e.getDouble(2))<.6&&Math.abs(d.y2()-e.getDouble(3))<.6&&Math.abs(d.confidence()-e.getDouble(4))<.005)found=true;
                        assertTrue("missing detection "+e,found);
                    }
                    android.util.Log.i("BeastYoloTest","sample="+item.getString("image")+" detections="+boxes.size()+" preprocess_inference_ms="+ms);
                }finally{rgba.release();bitmap.recycle();}
            }
        }
    }
    @Test public void decoderUsesClassAwareNmsAndReversesPadding(){
        assertTrue(OpenCVLoader.initLocal());
        float[][] raw=new float[7][3];
        for(int i=0;i<3;i++){raw[0][i]=100;raw[1][i]=100;raw[2][i]=20;raw[3][i]=40;}
        raw[4][0]=.9f;raw[4][1]=.8f;raw[5][2]=.85f;
        var boxes=YoloDetector.decode(raw);
        assertEquals(2,boxes.size());
        assertEquals(180,boxes.get(0).x1(),.001);assertEquals(136,boxes.get(0).y1(),.001);
        assertEquals(220,boxes.get(0).x2(),.001);assertEquals(216,boxes.get(0).y2(),.001);
        assertEquals(0,boxes.get(0).classId());assertEquals(1,boxes.get(1).classId());
    }
}
