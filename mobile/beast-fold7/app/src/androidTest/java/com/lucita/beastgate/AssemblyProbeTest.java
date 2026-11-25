package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class AssemblyProbeTest {
    @Test public void fullSequenceRequiresNewEvidenceAndGreenForEveryScrew(){
        AssemblyProbe gate=new AssemblyProbe(0,4);
        long start=0;
        for(int target=0;target<4;target++){
            assertEquals(target,gate.target());assertFalse(gate.finished());
            assertEquals(0,gate.holdMs());assertEquals(-1,gate.greenAt());
            gate.observe(start-1,start,true,true);
            assertEquals(0,gate.holdMs());
            for(long t=start;t<=start+800;t+=200)gate.observe(t,t,true,true);
            gate.observe(start+4799,start+4799,true,true);
            assertEquals(AssemblyProbe.Phase.WORKING,gate.phase());
            gate.acknowledgeGreen(target,start+4799);assertEquals(-1,gate.greenAt());
            gate.observe(start+4800,start+4800,true,true);
            assertEquals(AssemblyProbe.Phase.RELEASE,gate.phase());
            gate.acknowledgeGreen(target-1,start+4800);
            assertEquals(-1,gate.greenAt());
            gate.acknowledgeGreen(target,start+4800);
            assertFalse(gate.tick(start+7799));
            assertTrue(gate.tick(start+7800));
            assertFalse(gate.tick(start+7800));
            assertEquals(target+1,gate.target());
            start+=7800;
        }
        assertTrue(gate.finished());assertEquals(start,gate.finishedAt());
        gate.observe(start+1000,start+1000,true,true);
        gate.acknowledgeGreen(3,start+10000);
        assertFalse(gate.tick(start+20000));assertEquals(4,gate.target());
    }
    private AssemblyProbe armed(){
        AssemblyProbe gate=new AssemblyProbe(0);
        for(long time=0;time<=800;time+=200)gate.observe(time,time,true,true);
        assertEquals(AssemblyProbe.Phase.WORKING,gate.phase());
        return gate;
    }
    @Test public void requiresHoldAndActualGreenDrawThenThreeSeconds(){
        AssemblyProbe gate=armed();
        gate.observe(3800,3800,true,true);
        assertEquals(AssemblyProbe.Phase.WORKING,gate.phase());
        gate.observe(4799,4799,true,true);
        assertEquals(AssemblyProbe.Phase.WORKING,gate.phase());
        gate.observe(4800,4800,true,true);
        assertEquals(AssemblyProbe.Phase.RELEASE,gate.phase());
        gate.tick(9000);assertEquals(0,gate.target());
        gate.acknowledgeGreen(1,9000);gate.tick(13000);assertEquals(0,gate.target());
        gate.acknowledgeGreen(0,13000);
        gate.observe(13100,13100,false,false);
        gate.acknowledgeGreen(0,14000);
        gate.tick(15999);assertEquals(0,gate.target());
        assertTrue(gate.tick(16000));assertEquals(1,gate.target());
        gate.observe(15000,16001,true,true);assertTrue(gate.finished());
        gate.tick(30000);assertEquals(1,gate.target());
    }
    @Test public void incompleteGapsDoNotBecomeEvidenceOrLoseShortProgress(){
        AssemblyProbe gate=new AssemblyProbe(0);
        gate.observe(0,0,true,true);gate.observe(200,200,true,true);
        gate.observe(400,400,false,false);gate.observe(700,700,true,true);
        assertEquals(200,gate.holdMs());
        gate.observe(900,900,true,true);gate.observe(1100,1100,true,true);
        assertEquals(600,gate.holdMs());
        gate.observe(1800,1800,true,true);assertEquals(0,gate.holdMs());
    }
    @Test public void staleDuplicateAndWrongTargetNeverArm(){
        AssemblyProbe gate=new AssemblyProbe(1000);
        gate.observe(900,1000,true,true);
        gate.observe(1000,2000,true,true);
        gate.observe(2000,2000,true,true);
        gate.observe(2000,2200,true,true);
        gate.observe(1900,2300,true,true);
        gate.observe(2400,2400,true,false);
        assertEquals(0,gate.holdMs());
        assertEquals(AssemblyProbe.Phase.APPROACH,gate.phase());
        gate.acknowledgeGreen(0,2400);gate.tick(10000);assertEquals(0,gate.target());
    }
    @Test public void completedHoldNeedsFreshNearEvidenceForGreen(){
        AssemblyProbe gate=armed();
        gate.observe(5000,5000,false,false);
        gate.observe(5200,5200,true,false);
        assertEquals(AssemblyProbe.Phase.WORKING,gate.phase());
        gate.observe(5400,5400,true,true);
        assertEquals(AssemblyProbe.Phase.RELEASE,gate.phase());
        AssemblyProbe restarted=new AssemblyProbe(4000);
        restarted.tick(10000);assertEquals(0,restarted.holdMs());
        assertEquals(AssemblyProbe.Phase.APPROACH,restarted.phase());
    }
}
