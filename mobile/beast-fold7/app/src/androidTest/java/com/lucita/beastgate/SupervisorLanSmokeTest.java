package com.lucita.beastgate;

import android.content.Intent;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;

public class SupervisorLanSmokeTest {
    private Object value(Object object,String field)throws Exception{
        var f=object.getClass().getDeclaredField(field);f.setAccessible(true);return f.get(object);
    }
    @Test public void optInLanWithoutCamera()throws Exception{
        org.junit.Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("observer_smoke")));
        var instrument=InstrumentationRegistry.getInstrumentation();var context=instrument.getTargetContext();
        MainActivity activity=(MainActivity)instrument.startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
        java.io.File linkFile=new java.io.File(context.getFilesDir(),"observer-test-link.txt");
        java.io.File done=new java.io.File(context.getFilesDir(),"observer-test-done");done.delete();
        try{
            SupervisorLink link=(SupervisorLink)value(activity,"supervisor");
            instrument.runOnMainSync(link::begin);
            SupervisorServer server=null;
            for(int i=0;i<100&&server==null;i++){Thread.sleep(100);instrument.waitForIdleSync();server=(SupervisorServer)value(link,"server");}
            assertNotNull("Wi-Fi observer unavailable",server);assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
            java.nio.file.Files.write(linkFile.toPath(),server.link().getBytes(java.nio.charset.StandardCharsets.UTF_8));
            for(int i=0;i<1200&&!done.exists();i++)Thread.sleep(100);
            assertEquals(false,value(activity,"running"));assertNull(value(activity,"camera"));
            instrument.runOnMainSync(()->{link.close();activity.onStop();activity.onResume();});
            assertNull(value(link,"server"));assertEquals(false,value(activity,"running"));
        }finally{linkFile.delete();done.delete();instrument.runOnMainSync(activity::finish);}
    }
}
