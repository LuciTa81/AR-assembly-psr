package com.lucita.beastgate;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import java.util.List;
import java.util.Map;
import static org.junit.Assert.*;

public class AnalysisViewTest {
    @Test public void toolBoxesUseTheirFrameAgeAndClearWithPreview(){
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        instrumentation.runOnMainSync(()->{
            AnalysisView view=new AnalysisView(instrumentation.getTargetContext());
            view.layout(0,0,1280,720);
            Bitmap frame=Bitmap.createBitmap(1280,720,Bitmap.Config.ARGB_8888);
            frame.eraseColor(Color.BLACK);
            Bitmap rendered=Bitmap.createBitmap(1280,720,Bitmap.Config.ARGB_8888);
            Canvas canvas=new Canvas(rendered);
            var pose=new WorkspaceTracker.Result(false,"no_markers",Map.of(),Map.of(),Map.of(),Double.NaN);
            var detections=List.of(new YoloDetector.Detection(0,.9f,100,100,200,200));
            view.update(frame,pose,SystemClock.elapsedRealtime(),detections);view.draw(canvas);
            assertEquals(Color.rgb(255,120,80),rendered.getPixel(100,150));
            view.update(frame,pose,SystemClock.elapsedRealtime()-501,detections);view.draw(canvas);
            assertEquals(Color.BLACK,rendered.getPixel(100,150));
            view.update(frame,pose,SystemClock.elapsedRealtime(),detections);view.clear();view.draw(canvas);
            assertEquals(Color.BLACK,rendered.getPixel(100,150));
            frame.recycle();rendered.recycle();
        });
    }
}
