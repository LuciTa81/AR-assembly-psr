package com.lucita.beastgate;

import android.content.Intent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;

public class StandaloneLaunchTest {
    private Object value(MainActivity activity,String name)throws Exception{
        var field=MainActivity.class.getDeclaredField(name);field.setAccessible(true);return field.get(activity);
    }
    private MainActivity launch(Intent intent){
        var instrumentation=InstrumentationRegistry.getInstrumentation();
        intent.setClass(instrumentation.getTargetContext(),MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK);
        return (MainActivity)instrumentation.startActivitySync(intent);
    }
    private void finish(MainActivity activity){InstrumentationRegistry.getInstrumentation().runOnMainSync(activity::finish);}
    private Button button(View view,String text){
        if(view instanceof Button b&&b.getText().toString().contains(text))return b;
        if(view instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++){
            Button found=button(group.getChildAt(i),text);if(found!=null)return found;
        }
        return null;
    }
    @Test public void launcherDefaultsToFullV1WithoutStartingCamera()throws Exception{
        MainActivity activity=launch(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER));
        try{
            assertEquals(true,value(activity,"preparationProbe"));assertEquals(true,value(activity,"assemblyFull"));
            assertEquals(true,value(activity,"screwContextEnabled"));assertEquals(true,value(activity,"boxOutlineEnabled"));
            assertEquals(true,value(activity,"partPreviewEnabled"));assertEquals(true,value(activity,"toolProbe"));
            assertEquals(false,value(activity,"captureProbe"));assertEquals(false,value(activity,"targetSphereEnabled"));
            assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
        }finally{finish(activity);}
    }
    @Test public void explicitDiagnosticStillSelectsOnlyB()throws Exception{
        MainActivity activity=launch(new Intent().putExtra("probe_target","B"));
        try{
            assertEquals("B",value(activity,"probeTarget"));assertEquals(false,value(activity,"assemblyProbe"));
            assertEquals(false,value(activity,"screwContextEnabled"));assertEquals(false,value(activity,"running"));
        }finally{finish(activity);}
    }
    @Test public void stopLeavesAppOpenAndReadyForFreshStart()throws Exception{
        MainActivity activity=launch(new Intent());
        try{
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                try{
                    var running=MainActivity.class.getDeclaredField("running");running.setAccessible(true);running.set(activity,true);
                    Button stop=button(activity.getWindow().getDecorView(),"종료");assertNotNull(stop);stop.setEnabled(true);stop.performClick();
                    assertFalse(activity.isFinishing());assertEquals(false,value(activity,"running"));
                    assertNull(value(activity,"camera"));assertNull(value(activity,"assembly"));
                    assertNotNull(button(activity.getWindow().getDecorView(),"다시 시작"));assertFalse(stop.isEnabled());
                }catch(Exception e){throw new AssertionError(e);}
            });
        }finally{finish(activity);}
    }
    @Test public void deniedPermissionNeverStartsCamera()throws Exception{
        MainActivity activity=launch(new Intent());
        try{
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->activity.onRequestPermissionsResult(1,
                new String[]{android.Manifest.permission.CAMERA},new int[]{android.content.pm.PackageManager.PERMISSION_DENIED}));
            assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
        }finally{finish(activity);}
    }
    @Test public void diagnosticExtrasAreExplicitAndUnrelatedExtrasKeepDefault(){
        assertTrue(MainActivity.isStandalone(new Intent().putExtra("notification_id",7)));
        for(String key:new String[]{"probe_target","tool_probe","pose_probe","capture_probe","screw_context",
            "target_sphere","box_outline","part_preview","preparation_probe","assembly_full","assembly_probe"})
            assertFalse(key,MainActivity.isStandalone(new Intent().putExtra(key,false)));
    }
    @Test public void stopAndResumeNeverRestartCaptureAutomatically()throws Exception{
        MainActivity activity=launch(new Intent());
        try{
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                try{
                    var running=MainActivity.class.getDeclaredField("running");running.setAccessible(true);running.set(activity,true);
                    activity.onStop();activity.onResume();
                    assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
                    assertNull(value(activity,"assembly"));assertEquals(false,value(activity,"pendingCameraPermission"));
                    activity.onRequestPermissionsResult(1,new String[]{android.Manifest.permission.CAMERA},
                        new int[]{android.content.pm.PackageManager.PERMISSION_GRANTED});
                    assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
                }catch(Exception e){throw new AssertionError(e);}
            });
        }finally{finish(activity);}
    }
    @Test public void phoneLayoutsHaveVisibleControlsAndPreview()throws Exception{
        MainActivity activity=launch(new Intent());
        try{
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                float density=activity.getResources().getDisplayMetrics().density;
                ViewGroup content=activity.findViewById(android.R.id.content);View root=content.getChildAt(0);
                var directory=new java.io.File(activity.getExternalFilesDir(null),"standalone-ui-qa");
                assertTrue(directory.isDirectory()||directory.mkdirs());
                for(int[] size:new int[][]{{360,800},{690,830},{915,412}}){
                    int width=(int)(size[0]*density),height=(int)(size[1]*density);
                    root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));
                    root.layout(0,0,width,height);
                    for(String text:new String[]{"작업 시작","종료"}){
                        Button button=button(root,text);assertNotNull(button);
                        assertTrue(button.getWidth()>70*density);assertTrue(button.getHeight()>=48*density);
                        assertTrue(button.getPaint().measureText(button.getText().toString())<=button.getWidth()-button.getPaddingLeft()-button.getPaddingRight());
                    }
                    try{
                        View preview=(View)value(activity,"preview");assertTrue("preview height "+size[0]+" = "+preview.getHeight()/density,preview.getHeight()>=48*density);
                        assertTrue(preview.getBottom()<=height-root.getPaddingBottom());
                        var bitmap=android.graphics.Bitmap.createBitmap(width,height,android.graphics.Bitmap.Config.ARGB_8888);
                        try(var out=new java.io.FileOutputStream(new java.io.File(directory,size[0]+"x"+size[1]+".png"))){
                            root.draw(new android.graphics.Canvas(bitmap));assertTrue(bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out));
                        }finally{bitmap.recycle();}
                    }catch(Exception e){throw new AssertionError(e);}
                }
            });
        }finally{finish(activity);}
    }
}
