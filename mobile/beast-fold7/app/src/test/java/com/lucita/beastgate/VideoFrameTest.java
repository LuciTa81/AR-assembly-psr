package com.lucita.beastgate;
import org.junit.Test;
import static org.junit.Assert.*;
public class VideoFrameTest {
    @Test public void downsamplingPreservesNv21ChromaPairs(){
        byte[] source=new byte[8*8*3/2];for(int i=0;i<source.length;i++)source[i]=(byte)i;
        byte[] small=VideoFrame.halfNv21(source,8,8);
        assertEquals(24,small.length);assertArrayEquals(new byte[]{0,2,4,6,16,18,20,22,32,34,36,38,48,50,52,54,64,65,68,69,80,81,84,85},small);
        assertEquals(65,source[65]);
    }
    @Test public void invalidDimensionsNeverReadOutsideInput(){
        assertThrows(IllegalArgumentException.class,()->VideoFrame.halfNv21(new byte[8],8,8));
        assertThrows(IllegalArgumentException.class,()->VideoFrame.halfNv21(new byte[6],2,2));
    }
}
