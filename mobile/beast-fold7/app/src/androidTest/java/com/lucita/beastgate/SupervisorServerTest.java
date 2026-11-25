package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;
import androidx.test.platform.app.InstrumentationRegistry;

public class SupervisorServerTest {
    @Test public void readOnlyServerIsAvailableWithoutCamera() throws Exception {
        Class<?> type=Class.forName("com.lucita.beastgate.SupervisorServer");
        assertNotNull(type.getDeclaredMethod("publish",String.class));
    }
    private SupervisorServer start()throws Exception{
        SupervisorServer server=new SupervisorServer(InstrumentationRegistry.getInstrumentation().getTargetContext(),"127.0.0.1",0);
        server.start(1000,true);return server;
    }
    private String request(SupervisorServer server,String method,String path,String headers)throws Exception{
        try(var socket=new java.net.Socket("127.0.0.1",server.getListeningPort())){
            socket.setSoTimeout(3000);
            socket.getOutputStream().write((method+" "+path+" HTTP/1.1\r\nHost: 127.0.0.1:"+server.getListeningPort()+"\r\nConnection: close\r\n"+headers+"\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return new String(socket.getInputStream().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
        }
    }
    private String auth(SupervisorServer server){return "Authorization: Bearer "+server.link().split("#key=")[1]+"\r\n";}
    @Test public void requiresTokenAndNeverAcceptsCommandsOrImages()throws Exception{
        SupervisorServer server=start();
        try{
            server.publish("{\"stage\":3}");
            assertTrue(request(server,"GET","/state.json","").contains("401 Unauthorized"));
            String state=request(server,"GET","/state.json",auth(server));
            assertTrue(state,state.contains("200 OK"));assertTrue(state.contains("{\"stage\":3}"));
            assertTrue(state.toLowerCase().contains("cache-control: no-store"));assertFalse(state.toLowerCase().contains("access-control-allow-origin"));
            assertTrue(request(server,"POST","/operator/confirm",auth(server)).contains("405 Method Not Allowed"));
            assertTrue(request(server,"GET","/frame.jpg",auth(server)).contains("404 Not Found"));
            assertTrue(request(server,"GET","/../eye-projection.json",auth(server)).contains("404 Not Found"));
            assertTrue(request(server,"GET","/state.json",auth(server)+"Origin: https://evil.example\r\n").contains("403 Forbidden"));
            assertTrue(request(server,"GET","/","").contains("AR Assembly"));
        }finally{server.stop();}
    }
    @Test public void linkRotatesAndStopClosesSocket()throws Exception{
        SupervisorServer first=start();String old=auth(first);int port=first.getListeningPort();first.stop();
        try(var socket=new java.net.Socket("127.0.0.1",port)){fail("stopped server accepted connection");}
        catch(java.net.ConnectException expected){}
        SupervisorServer next=start();
        try{assertNotEquals(old,auth(next));assertTrue(request(next,"GET","/state.json",old).contains("401 Unauthorized"));}
        finally{next.stop();}
    }
    @Test public void stateUsesRealPreparationAndAssemblyWithoutChangingThem()throws Exception{
        PreparationGuide prep=new PreparationGuide(0);AssemblyProbe assembly=new AssemblyProbe(0,4);
        assertEquals(-1,SupervisorState.stage(false,prep,assembly));assertEquals(0,SupervisorState.stage(true,prep,assembly));
        for(int t=0;t<=7000;t+=100)prep.onDraw(0,t,t,true);
        assertEquals(1,SupervisorState.stage(true,prep,assembly));
        for(int t=7100;t<=13100;t+=100)prep.onDraw(1,t,t,true);
        assertEquals(2,SupervisorState.stage(true,prep,assembly));
        assertEquals("나사 A를 조여주세요",SupervisorState.action(2,AssemblyProbe.Phase.WORKING,true));
        assertEquals("작업대가 보이도록 바라봐주세요",SupervisorState.action(2,AssemblyProbe.Phase.WORKING,false));
        assertEquals("조립 상태를 확인해주세요",SupervisorState.action(6,AssemblyProbe.Phase.APPROACH,false));
        assertEquals(0,assembly.target());assertEquals(0,assembly.holdMs());
        org.json.JSONObject json=new org.json.JSONObject(SupervisorState.json("test",10,0,false,-1,"PREPARATION","작업 대기",false,false,0,Double.NaN,-1,0,"idle",0));
        assertTrue(json.isNull("rms_px"));assertFalse(json.getBoolean("video_available"));assertFalse(json.getBoolean("fastening_verified"));
    }
}
