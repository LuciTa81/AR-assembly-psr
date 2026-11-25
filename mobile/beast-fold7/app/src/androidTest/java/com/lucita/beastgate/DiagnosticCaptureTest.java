package com.lucita.beastgate;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.Map;
import org.json.JSONObject;
import org.junit.Test;
import org.opencv.core.Point;
import static org.junit.Assert.*;

public class DiagnosticCaptureTest {
    @Test public void respectsRemainingBudget() throws Exception {
        File root=Files.createTempDirectory(InstrumentationRegistry.getInstrumentation()
            .getTargetContext().getCacheDir().toPath(),"capture-budget-").toFile();
        Bitmap bitmap=Bitmap.createBitmap(8,8,Bitmap.Config.ARGB_8888);
        DiagnosticCapture capture=new DiagnosticCapture(root,2);
        var result=new WorkspaceTracker.Result(false,"no_markers",Map.of(),Map.of(),Map.of(),Double.NaN);
        try {
            assertTrue(capture.save(bitmap,result,1000,1));
            assertTrue(capture.save(bitmap,result,1500,1));
            assertFalse(capture.save(bitmap,result,2000,2));
            assertEquals(2,capture.count());
            for(int invalid:new int[]{0,101}){
                try{new DiagnosticCapture(root,invalid);fail("Accepted invalid limit");}
                catch(IllegalArgumentException expected){}
            }
        }finally{
            bitmap.recycle();
            for(File file:capture.directory.listFiles())assertTrue(file.delete());
            assertTrue(capture.directory.delete());assertTrue(root.delete());
        }
    }
    @Test public void capsPhotosAndKeepsMatchingRejectedFrameMetadata() throws Exception {
        File root=Files.createTempDirectory(InstrumentationRegistry.getInstrumentation()
            .getTargetContext().getCacheDir().toPath(),"capture-test-").toFile();
        Bitmap bitmap=Bitmap.createBitmap(8,8,Bitmap.Config.ARGB_8888);
        Point[] quad={new Point(1,1),new Point(6,1),new Point(6,6),new Point(1,6)};
        var result=new WorkspaceTracker.Result(false,"degenerate_ippe_geometry",
            Map.of(4,quad),Map.of(),Map.of(),Double.NaN);
        DiagnosticCapture capture=new DiagnosticCapture(root);
        try {
            assertTrue(capture.save(bitmap,result,1000,7));
            assertFalse(capture.save(bitmap,result,1499,7));
            for(int i=1;i<100;i++)assertTrue(capture.save(bitmap,result,1000+i*500,7));
            assertFalse(capture.save(bitmap,result,60000,8));
            assertEquals(100,capture.count());
            File[] images=capture.directory.listFiles((d,n)->n.endsWith(".png"));
            assertNotNull(images);assertEquals(100,images.length);
            JSONObject metadata=new JSONObject(new String(Files.readAllBytes(new File(capture.directory,"0001.json").toPath()),java.nio.charset.StandardCharsets.UTF_8));
            assertEquals(1000,metadata.getLong("frame_ms"));
            assertEquals(7,metadata.getInt("session"));
            assertEquals("degenerate_ippe_geometry",metadata.getString("reason"));
            assertTrue(metadata.isNull("rms"));
            assertEquals(4,metadata.getJSONObject("corners").getJSONArray("4").length());
            Bitmap restored=BitmapFactory.decodeFile(new File(capture.directory,"0001.png").getPath());
            assertEquals(8,restored.getWidth());restored.recycle();
        } finally {
            bitmap.recycle();
            File[] files=capture.directory.listFiles();
            if(files!=null)for(File file:files)assertTrue(file.delete());
            assertTrue(capture.directory.delete());assertTrue(root.delete());
        }
    }
}
