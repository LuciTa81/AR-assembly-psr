package com.lucita.beastgate;

import org.junit.Test;
import static org.junit.Assert.*;

public class PreparationGuideTest {
    @Test public void needsSevenSecondsForBoxAndSixForLid(){
        var guide=new PreparationGuide(0);
        for(int stage=0;stage<2;stage++){
            long start=stage==0?0:7000,duration=stage==0?7000:6000;
            assertEquals(stage,guide.stage());
            assertEquals(duration,guide.durationMs());
            for(long t=start;t<start+duration;t+=200)
                assertFalse(guide.onDraw(stage,t,t,true));
            assertEquals(duration-200,guide.elapsedMs());
            assertTrue(guide.onDraw(stage,start+duration,start+duration,true));
            assertEquals(stage+1,guide.stage());
            assertEquals(0,guide.elapsedMs());
        }
        assertTrue(guide.finished());
        assertFalse(guide.onDraw(2,20000,20000,true));
    }

    @Test public void pausesWithoutCountingLossAndKeepsProgress(){
        var guide=new PreparationGuide(0);
        guide.onDraw(0,0,0,true);guide.onDraw(0,200,200,true);
        guide.onDraw(0,400,400,false);
        guide.onDraw(0,600,600,true);
        assertEquals(200,guide.elapsedMs());
        guide.onDraw(0,800,800,true);assertEquals(400,guide.elapsedMs());
        guide.onDraw(0,2000,2000,true);assertEquals(400,guide.elapsedMs());
        guide.onDraw(0,2200,2200,true);assertEquals(600,guide.elapsedMs());
    }

    @Test public void rejectsDuplicateStaleFutureAndPreviousStageDraws(){
        var guide=new PreparationGuide(1000);
        guide.onDraw(0,999,1000,true);guide.onDraw(0,1200,1100,true);
        guide.onDraw(0,1000,1600,true);assertEquals(0,guide.elapsedMs());
        guide.onDraw(0,2000,2000,true);guide.onDraw(0,2200,2200,true);
        guide.onDraw(0,2200,2250,true);guide.onDraw(0,2100,2300,true);
        assertEquals(200,guide.elapsedMs());
        guide.onDraw(1,2400,2400,true);assertEquals(0,guide.stage());
        var normal=new PreparationGuide(0);
        for(long t=0;t<=7000;t+=200)normal.onDraw(0,t,t,true);
        assertEquals(1,normal.stage());
        normal.onDraw(0,7200,7200,true);
        normal.onDraw(1,6900,7200,true);
        assertEquals(0,normal.elapsedMs());
        var restarted=new PreparationGuide(9000);
        assertEquals(0,restarted.stage());assertEquals(0,restarted.elapsedMs());
    }

    @Test public void preparationDoesNotSupplyScrewEvidence(){
        var prep=new PreparationGuide(0);
        for(long t=0;t<=13000;t+=200)prep.onDraw(prep.stage(),t,t,true);
        assertFalse(prep.finished());
        // The new stage's first frame establishes a baseline; it carries no box time.
        prep.onDraw(1,13200,13200,true);
        assertTrue(prep.finished());
        var assembly=new AssemblyProbe(13200,4);
        assembly.observe(13100,13300,true,true);
        assertEquals(0,assembly.holdMs());
        assertEquals(AssemblyProbe.Phase.APPROACH,assembly.phase());
        assembly.tick(25000);assertEquals(0,assembly.target());
    }
}
