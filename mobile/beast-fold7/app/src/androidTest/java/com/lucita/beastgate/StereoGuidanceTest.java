package com.lucita.beastgate;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;

public class StereoGuidanceTest {
    @Test public void preparationRequiresFullSbsFreshTrackingAndStopsCallbacksWhenCleared(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            var view=new StereoOverlayView(InstrumentationRegistry.getInstrumentation().getTargetContext());
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
            int[] good={0},paused={0};
            StereoOverlayView.PreparationDrawn callback=(stage,frame,now,tracked)->{
                if(tracked)good[0]++;else paused[0]++;
            };
            try{
                view.layout(0,0,1920,1080);
                view.updatePreparation(0,SystemClock.elapsedRealtime(),true,callback);
                view.draw(canvas);assertEquals(0,good[0]);assertEquals(0,paused[0]);
                view.layout(0,0,3840,1080);
                view.updatePreparation(0,SystemClock.elapsedRealtime()-1000,true,callback);
                view.draw(canvas);assertEquals(0,good[0]);assertEquals(1,paused[0]);
                view.updatePreparation(0,SystemClock.elapsedRealtime(),false,callback);
                view.draw(canvas);assertEquals(0,good[0]);assertEquals(2,paused[0]);
                for(int stage=0;stage<2;stage++){
                    view.updatePreparation(stage,SystemClock.elapsedRealtime(),true,callback);
                    view.draw(canvas);
                    for(int eye=0;eye<2;eye++){
                        int pixels=0;
                        for(int y=50;y<110;y++)for(int x=750;x<1170;x++)
                            if(bitmap.getPixel(eye*1920+x,y)!=android.graphics.Color.BLACK)pixels++;
                        assertTrue(pixels>100);
                    }
                    assertEquals(android.graphics.Color.BLACK,bitmap.getPixel(924,400));
                }
                assertEquals(2,good[0]);
                view.updateGuide(null,0,0,AssemblyProbe.Phase.APPROACH,null);
                view.draw(canvas);assertEquals(2,good[0]);assertEquals(2,paused[0]);
                view.updatePreparation(0,SystemClock.elapsedRealtime(),true,callback);
                view.clear();view.draw(canvas);assertEquals(2,good[0]);
            }finally{view.clear();bitmap.recycle();}
        });
    }
    @Test public void allTargetsDrawAndInspectionClearsRingWithoutGreenAck(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            var view=new StereoOverlayView(InstrumentationRegistry.getInstrumentation().getTargetContext());
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
            int[] acks={0};double[][] pair={{900,400},{700,400}};
            try{
                view.layout(0,0,3840,1080);
                for(int target=0;target<4;target++){
                    final int expected=target;
                    for(var phase:AssemblyProbe.Phase.values()){
                        view.updateGuide(pair,SystemClock.elapsedRealtime(),target,phase,(drawn,now)->{
                            assertEquals(expected,(int)drawn);acks[0]++;
                        });
                        view.draw(canvas);
                        assertNotEquals(android.graphics.Color.BLACK,bitmap.getPixel(924,400));
                        assertNotEquals(android.graphics.Color.BLACK,bitmap.getPixel(2644,400));
                    }
                }
                assertEquals(4,acks[0]);
                view.showInspection();view.draw(canvas);
                assertEquals(4,acks[0]);
                assertEquals(android.graphics.Color.BLACK,bitmap.getPixel(924,400));
                assertEquals(android.graphics.Color.BLACK,bitmap.getPixel(2644,400));
                int textPixels=0;
                for(int y=50;y<110;y++)for(int x=800;x<1120;x++)
                    if(bitmap.getPixel(x,y)!=android.graphics.Color.BLACK)textPixels++;
                assertTrue(textPixels>100);
            }finally{view.clear();bitmap.recycle();}
        });
    }
    @Test public void greenRequiresActualFreshFullSbsDraw(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            var view=new StereoOverlayView(InstrumentationRegistry.getInstrumentation().getTargetContext());
            Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
            int[] acks={0};double[][] pair={{900,400},{700,400}};
            try{
                view.layout(0,0,3840,1080);
                view.updateGuide(null,SystemClock.elapsedRealtime(),0,AssemblyProbe.Phase.RELEASE,(target,now)->acks[0]++);
                view.draw(canvas);assertEquals(0,acks[0]);
                view.updateGuide(pair,SystemClock.elapsedRealtime()-1000,0,AssemblyProbe.Phase.RELEASE,(target,now)->acks[0]++);
                view.draw(canvas);assertEquals(0,acks[0]);
                view.layout(0,0,1920,1080);
                view.updateGuide(pair,SystemClock.elapsedRealtime(),0,AssemblyProbe.Phase.RELEASE,(target,now)->acks[0]++);
                view.draw(canvas);assertEquals(0,acks[0]);
                view.layout(0,0,3840,1080);
                view.updateGuide(pair,SystemClock.elapsedRealtime(),0,AssemblyProbe.Phase.RELEASE,(target,now)->acks[0]++);
                view.draw(canvas);assertEquals(1,acks[0]);
                assertNotEquals(android.graphics.Color.BLACK,bitmap.getPixel(924,400));
                assertNotEquals(android.graphics.Color.BLACK,bitmap.getPixel(2644,400));
            }finally{view.clear();bitmap.recycle();}
        });
    }
}
