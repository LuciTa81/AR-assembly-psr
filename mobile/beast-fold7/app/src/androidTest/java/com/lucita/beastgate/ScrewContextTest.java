package com.lucita.beastgate;

import android.graphics.*;
import android.os.SystemClock;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;

public class ScrewContextTest {
    private static final double[][][] POINTS={
        {{800,400},{700,410}},{{1100,400},{1000,410}},
        {{800,700},{700,710}},{{1100,700},{1000,710}}
    };
    private interface Check { void run(StereoOverlayView view,Bitmap bitmap,Canvas canvas); }
    private void withView(Check check){
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        instrumentation.runOnMainSync(()->{
            var view=new StereoOverlayView(instrumentation.getTargetContext());
            view.setScrewContextEnabled(true);view.layout(0,0,3840,1080);
            var bitmap=Bitmap.createBitmap(3840,1080,Bitmap.Config.ARGB_8888);
            try{check.run(view,bitmap,new Canvas(bitmap));}finally{view.clear();bitmap.recycle();}
        });
    }
    @Test public void fourCentersWithOnlyCurrentTargetColored(){
        withView((view,bitmap,canvas)->{
            int[] acks={0};
            for(int target=0;target<4;target++)for(var phase:AssemblyProbe.Phase.values()){
                long now=SystemClock.elapsedRealtime();
                view.updateScrewContext(POINTS,now);
                view.updateGuide(POINTS[target],now,target,phase,(which,time)->acks[0]++);
                view.draw(canvas);
                for(int eye=0;eye<2;eye++)for(int screw=0;screw<4;screw++){
                    int x=(int)POINTS[screw][eye][0]+eye*1920,y=(int)POINTS[screw][eye][1];
                    int pixel=bitmap.getPixel(x+(screw==target?21:16),y);
                    assertNotEquals(Color.BLACK,pixel);
                    assertEquals(Color.BLACK,bitmap.getPixel(x,y));
                    if(screw!=target){assertEquals(Color.red(pixel),Color.green(pixel));assertEquals(Color.green(pixel),Color.blue(pixel));}
                    else if(phase==AssemblyProbe.Phase.APPROACH)assertTrue(Color.red(pixel)>Color.green(pixel));
                    else if(phase==AssemblyProbe.Phase.WORKING)assertTrue(Color.blue(pixel)>Color.green(pixel));
                    else assertTrue(Color.green(pixel)>Color.blue(pixel));
                }
                assertEquals(Color.BLACK,bitmap.getPixel(950,400));
            }
            assertEquals(4,acks[0]);
        });
    }
    @Test public void contextCannotAcknowledgeGreenOrLeakIntoPreparation(){
        withView((view,bitmap,canvas)->{
            int[] acks={0};long now=SystemClock.elapsedRealtime();
            view.updateScrewContext(POINTS,now);
            view.updateGuide(null,now,0,AssemblyProbe.Phase.RELEASE,(which,time)->acks[0]++);
            view.draw(canvas);assertEquals(0,acks[0]);
            assertNotEquals(Color.BLACK,bitmap.getPixel(1116,400));
            view.updatePreparation(0,now,true,null);view.draw(canvas);
            assertEquals(Color.BLACK,bitmap.getPixel(1116,400));
            view.showInspection();view.draw(canvas);
            assertEquals(Color.BLACK,bitmap.getPixel(1116,400));
            view.updateScrewContext(POINTS,SystemClock.elapsedRealtime());view.draw(canvas);
            for(var pair:POINTS)for(int eye=0;eye<2;eye++){
                int pixel=bitmap.getPixel((int)pair[eye][0]+eye*1920+15,(int)pair[eye][1]);
                assertEquals(Color.rgb(77,133,119),pixel);
            }
        });
    }
    @Test public void staleInvalidAndWrongSurfaceHideContext(){
        withView((view,bitmap,canvas)->{
            view.showInspection();
            for(long time:new long[]{SystemClock.elapsedRealtime()-1000,SystemClock.elapsedRealtime()+10000}){
                view.updateScrewContext(POINTS,time);view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(816,400));
            }
            view.updateScrewContext(null,SystemClock.elapsedRealtime());view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(816,400));
            view.updateScrewContext(POINTS,SystemClock.elapsedRealtime());view.layout(0,0,1920,1080);view.draw(canvas);
            assertEquals(Color.BLACK,bitmap.getPixel(816,400));
            view.layout(0,0,3840,1080);view.clear();view.draw(canvas);assertEquals(Color.BLACK,bitmap.getPixel(816,400));
        });
    }
    @Test public void syntheticSbsProofs() {
        var context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        var directory=new java.io.File(context.getExternalFilesDir(null),"screw-context-qa");
        assertTrue(directory.isDirectory()||directory.mkdirs());
        withView((view,bitmap,canvas)->{
            int target=0;
            for(var phase:AssemblyProbe.Phase.values()){
                long now=SystemClock.elapsedRealtime();view.updateScrewContext(POINTS,now);
                view.updateGuide(POINTS[target],now,target,phase,null);view.draw(canvas);
                try(var stream=new java.io.FileOutputStream(new java.io.File(directory,phase.name()+".png"))){
                    assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,stream));
                }catch(java.io.IOException error){throw new AssertionError(error);}
                target++;
            }
        });
    }
}
