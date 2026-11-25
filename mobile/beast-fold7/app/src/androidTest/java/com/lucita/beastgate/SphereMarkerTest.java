package com.lucita.beastgate;

import android.graphics.*;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;

public class SphereMarkerTest {
    @Test public void spritesAreTranslucentCenteredAndShaded()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        for(String name:new String[]{"orange","blue","green"}){
            Bitmap image;
            try(var in=context.getAssets().open("markers/"+name+".png")){image=BitmapFactory.decodeStream(in);}
            assertNotNull(image);
            try{
                assertEquals(96,image.getWidth());assertEquals(96,image.getHeight());
                assertEquals(0,Color.alpha(image.getPixel(0,0)));
                int center=image.getPixel(48,48),alpha=Color.alpha(center);
                assertTrue(alpha>100&&alpha<180);
                assertNotEquals(image.getPixel(32,32),image.getPixel(64,64));
                if(name.equals("orange")){assertTrue(Color.red(center)>Color.green(center));assertTrue(Color.green(center)>Color.blue(center));}
                else if(name.equals("blue")){assertTrue(Color.blue(center)>Color.green(center));assertTrue(Color.green(center)>Color.red(center));}
                else {assertTrue(Color.green(center)>Color.blue(center));assertTrue(Color.blue(center)>Color.red(center));}
            }finally{image.recycle();}
        }
    }
    @Test public void calibratedCentersColorsAndGreenAckArePreserved()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        try(SphereMarker marker=new SphereMarker(context)){
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                StereoOverlayView view=new StereoOverlayView(context);view.setSphereMarker(marker);view.layout(0,0,3840,1080);
                Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
                int[] acks={0};double[][] pair={{900,500},{700,500}};
                try{
                    for(int target=0;target<4;target++)for(var phase:AssemblyProbe.Phase.values()){
                        view.updateGuide(pair,SystemClock.elapsedRealtime(),target,phase,(which,time)->acks[0]++);view.draw(canvas);
                        int left=bitmap.getPixel(900,500);assertNotEquals(Color.BLACK,left);assertEquals(left,bitmap.getPixel(2620,500));
                        assertEquals(Color.BLACK,bitmap.getPixel(700,500));assertEquals(Color.BLACK,bitmap.getPixel(2820,500));
                        assertEquals(Color.BLACK,bitmap.getPixel(924,500));
                        if(phase==AssemblyProbe.Phase.APPROACH)assertTrue(Color.red(left)>Color.green(left));
                        if(phase==AssemblyProbe.Phase.WORKING)assertTrue(Color.blue(left)>Color.green(left));
                        if(phase==AssemblyProbe.Phase.RELEASE)assertTrue(Color.green(left)>Color.blue(left));
                    }
                    assertEquals(4,acks[0]);
                    view.showInspection();view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(900,500));assertEquals(4,acks[0]);
                }finally{view.clear();view.setSphereMarker(null);bitmap.recycle();}
            });
        }
    }
    @Test public void invalidStaleWrongDisplayAndClearHideSphereWithoutAcknowledgement()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        try(SphereMarker marker=new SphereMarker(context)){
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                StereoOverlayView view=new StereoOverlayView(context);view.setSphereMarker(marker);view.layout(0,0,3840,1080);
                Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
                double[][] pair={{900,500},{700,500}};int[] acks={0};
                try{
                    for(int mode=0;mode<4;mode++){
                        long now=SystemClock.elapsedRealtime();
                        view.updateGuide(mode==0?null:pair,mode==1?now-1000:mode==2?now+10000:now,0,AssemblyProbe.Phase.RELEASE,(which,time)->acks[0]++);
                        if(mode==3)view.layout(0,0,1920,1080);
                        view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(900,500));assertEquals(0,acks[0]);
                    }
                    view.layout(0,0,3840,1080);view.updateGuide(pair,SystemClock.elapsedRealtime(),0,AssemblyProbe.Phase.RELEASE,(which,time)->acks[0]++);
                    view.clear();view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(900,500));assertEquals(0,acks[0]);
                }finally{view.clear();view.setSphereMarker(null);bitmap.recycle();}
            });
        }
    }
    @Test public void syntheticSbsProofsShowAllThreeStates()throws Exception{
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        java.io.File directory=new java.io.File(context.getExternalFilesDir(null),"sphere-qa");assertTrue(directory.isDirectory()||directory.mkdirs());
        try(SphereMarker marker=new SphereMarker(context)){
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                StereoOverlayView view=new StereoOverlayView(context);view.setSphereMarker(marker);view.layout(0,0,3840,1080);
                Bitmap bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(bitmap);
                try{
                    for(var phase:AssemblyProbe.Phase.values()){
                        view.updateGuide(new double[][]{{900,500},{700,500}},SystemClock.elapsedRealtime(),0,phase,null);view.draw(canvas);
                        try(var stream=new java.io.FileOutputStream(new java.io.File(directory,phase.name()+".png"))){assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,stream));}
                        catch(java.io.IOException error){throw new AssertionError(error);}
                    }
                }finally{view.clear();view.setSphereMarker(null);bitmap.recycle();}
            });
        }
    }
}
