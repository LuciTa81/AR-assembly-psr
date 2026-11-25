package com.lucita.beastgate;

import android.content.res.Configuration;
import android.view.ContextThemeWrapper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

/** No camera or network required; renders the phone shell with synthetic state. */
public class AssemblyScreenTest {
    private AssemblyScreen screen(float fontScale) {
        var base=InstrumentationRegistry.getInstrumentation().getTargetContext();
        Configuration config=new Configuration(base.getResources().getConfiguration());
        config.fontScale=fontScale;
        return new AssemblyScreen(new ContextThemeWrapper(base.createConfigurationContext(config),R.style.AssemblyTheme));
    }

    @Test public void narrowWideAndLargeTextKeepControlsInsideScreen(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            for(float fontScale:new float[]{1f,1.3f}){
                AssemblyScreen screen=screen(fontScale);
                float density=screen.getResources().getDisplayMetrics().density;
                for(int[] size:new int[][]{{360,800},{690,830},{915,412}}){
                    int width=Math.round(size[0]*density),height=Math.round(size[1]*density);
                    screen.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));
                    screen.layout(0,0,width,height);
                    for(View control:new View[]{screen.start,screen.stop,screen.refresh}){
                        assertTrue(control.getHeight()>=48*density);
                        android.graphics.Rect bounds=new android.graphics.Rect(0,0,control.getWidth(),control.getHeight());
                        screen.offsetDescendantRectToMyCoords(control,bounds);
                        assertTrue(bounds.left>=0&&bounds.top>=0&&bounds.right<=width&&bounds.bottom<=height);
                    }
                    assertTrue(screen.preview.getMeasuredHeight()>=120*density);
                    capture(screen,size[0]+"x"+size[1]+"-font-"+fontScale);
                    screen.selectPage(1);
                    assertEquals(View.VISIBLE,screen.stop.getVisibility());
                    screen.selectPage(0);
                }
            }
        });
    }

    @Test public void stageAndIdleStatesDoNotChangeUnderlyingSnapshot(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            try{
                AssemblyScreen screen=screen(1f);
                JSONObject state=new JSONObject("{\"running\":true,\"stage\":2,\"phase\":\"WORKING\",\"overlay_visible\":true,\"tracked\":true,\"markers\":5,\"action\":\"A 나사를 조여주세요\",\"elapsed_ms\":65000}");
                String original=state.toString();screen.present(state,false,true);
                assertEquals("나사 A",screen.taskStatus.getText().toString());
                assertEquals(View.VISIBLE,screen.preview.getVisibility());
                assertNotNull(find(screen,"01:05"));
                screen.selectPage(1);screen.selectPage(0);
                assertEquals(original,state.toString());
                assertEquals("나사 A",screen.taskStatus.getText().toString());
                screen.present(new JSONObject(),true,true);
                assertEquals("다음 작업 준비",screen.taskStatus.getText().toString());
                assertEquals(View.INVISIBLE,screen.preview.getVisibility());
            }catch(Exception e){throw new AssertionError(e);}
        });
    }

    @Test public void idleCameraCaptionIsCenteredAndRoutineNoticeHidden(){
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
            AssemblyScreen screen=screen(1f);
            TextView caption=find(screen,"카메라 대기");assertNotNull(caption);
            assertEquals(android.view.Gravity.CENTER_HORIZONTAL,caption.getGravity()&android.view.Gravity.HORIZONTAL_GRAVITY_MASK);
            screen.showNotice("인식 준비 완료");
            TextView routine=find(screen,"인식 준비 완료");
            assertTrue(routine==null||routine.getVisibility()!=View.VISIBLE);
        });
    }

    private TextView find(View view,String text){
        if(view instanceof TextView label&&text.contentEquals(label.getText()))return label;
        if(view instanceof ViewGroup group)for(int i=0;i<group.getChildCount();i++){
            TextView result=find(group.getChildAt(i),text);if(result!=null)return result;
        }
        return null;
    }

    private void capture(View view,String name){
        var directory=new java.io.File(view.getContext().getExternalFilesDir(null),"product-ui-qa");
        assertTrue(directory.isDirectory()||directory.mkdirs());
        var bitmap=android.graphics.Bitmap.createBitmap(view.getWidth(),view.getHeight(),android.graphics.Bitmap.Config.ARGB_8888);
        try(var out=new java.io.FileOutputStream(new java.io.File(directory,name+".png"))){
            view.draw(new android.graphics.Canvas(bitmap));assertTrue(bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out));
        }catch(java.io.IOException error){throw new AssertionError(error);}
        finally{bitmap.recycle();}
    }
}
