package com.lucita.beastgate;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class EyeProjectionTest {
    private Context context(){return InstrumentationRegistry.getInstrumentation().getTargetContext();}
    @Test public void probeTargetAcceptsOnlyKnownScrews(){
        for(String target:new String[]{"A","B","C","D"})assertEquals(target,MainActivity.selectProbeTarget(target));
        for(String invalid:new String[]{null,"","AB","E","b"})assertEquals("A",MainActivity.selectProbeTarget(invalid));
    }
    @Test public void matchesEightFrozenUnityReplayPoints() throws Exception {
        EyeProjection projection=new EyeProjection(context());
        JSONObject fixture;
        try(java.io.InputStream in=context().getAssets().open("eye-fixtures.json")){
            fixture=new JSONObject(new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
        JSONArray samples=fixture.getJSONObject("baseline_dlt").getJSONArray("samples");
        JSONArray expected=fixture.getJSONObject("joint").getJSONObject("fit_error_px").getJSONArray("predicted_px");
        assertEquals(8,samples.length());
        for(int i=0;i<samples.length();i++){
            JSONArray xyz=samples.getJSONObject(i).getJSONArray("camera_xyz_mm");
            double[][] pair=projection.project(new double[]{xyz.getDouble(0),xyz.getDouble(1),xyz.getDouble(2)});
            assertNotNull(pair);
            for(int eye=0;eye<2;eye++)for(int axis=0;axis<2;axis++)
                assertEquals(expected.getJSONArray(i).getJSONArray(eye).getDouble(axis),pair[eye][axis],1e-7);
        }
        assertNull(projection.project(null));
        assertNull(projection.project(new double[]{0,0,-1}));
        assertNull(projection.project(new double[]{Double.NaN,0,500}));
        assertNull(projection.project(new double[]{100000,0,500}));
    }
    @Test public void stereoRenderingUsesSeparateHalvesAndRejectsStaleFrames(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            StereoOverlayView view=new StereoOverlayView(context());
            view.layout(0,0,3840,1080);
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);
            try{
                Canvas canvas=new Canvas(bitmap);
                view.update(new double[][]{{400,500},{600,500}},SystemClock.elapsedRealtime());
                view.draw(canvas);
                assertNotEquals(Color.BLACK,bitmap.getPixel(400,500));
                assertNotEquals(Color.BLACK,bitmap.getPixel(1920+600,500));
                assertEquals(Color.BLACK,bitmap.getPixel(600,500));
                assertEquals(Color.BLACK,bitmap.getPixel(1920+400,500));
                view.update(new double[][]{{400,500},{600,500}},SystemClock.elapsedRealtime()-1000);
                view.draw(canvas);
                assertEquals(Color.BLACK,bitmap.getPixel(400,500));
                view.update(new double[][]{{400,500},{600,500}},SystemClock.elapsedRealtime());
                view.layout(0,0,1920,1080);view.draw(canvas);
                assertEquals(Color.BLACK,bitmap.getPixel(400,500));
                view.clear();
            }finally{bitmap.recycle();}
        });
    }
}
