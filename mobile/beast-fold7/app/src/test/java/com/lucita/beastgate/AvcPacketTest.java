package com.lucita.beastgate;
import java.nio.ByteBuffer;
import org.junit.Test;
import static org.junit.Assert.*;

public class AvcPacketTest {
    @Test public void annexBAndLengthPrefixedAreNormalized(){
        byte[] frame={0,0,0,1,101,22};assertSame(frame,AvcPacket.annexB(frame));
        assertArrayEquals(frame,AvcPacket.annexB(new byte[]{0,0,0,2,101,22}));
        assertThrows(IllegalArgumentException.class,()->AvcPacket.annexB(new byte[]{0,0,0,5,101}));
    }
    @Test public void packetHasBoundsMetadataAndConfigOnlyOnKeys(){
        byte[] config={0,0,0,1,103},frame={0,0,0,1,101};
        byte[] key=AvcPacket.encode(1,33333,true,config,frame);ByteBuffer p=ByteBuffer.wrap(key);
        assertEquals(0x41525632,p.getInt());assertEquals(1,p.get());assertEquals(1,p.getInt());assertEquals(33333,p.getLong());
        assertEquals(1280,p.getShort());assertEquals(720,p.getShort());assertEquals(31,key.length);
        assertEquals(26,AvcPacket.encode(2,66666,false,config,frame).length);
        assertThrows(IllegalArgumentException.class,()->AvcPacket.encode(0,1,true,config,frame));
        assertThrows(IllegalArgumentException.class,()->AvcPacket.encode(1,1,true,config,new byte[AvcPacket.MAX_BYTES]));
    }
    @Test public void nv21ChromaRespectsInputPlaneStrideAndOffset(){
        byte[] source={10,20,11,21,12,22,13,23};ByteBuffer u=ByteBuffer.allocate(16);u.position(1);
        AvcPacket.copyPlane(u,6,2,source,1,4,2,2,2);
        assertEquals(20,u.get(1));assertEquals(21,u.get(3));assertEquals(22,u.get(7));assertEquals(23,u.get(9));
        ByteBuffer y=ByteBuffer.allocate(8);AvcPacket.copyPlane(y,4,1,source,0,4,1,2,2);
        assertEquals(10,y.get(0));assertEquals(20,y.get(1));assertEquals(12,y.get(4));assertEquals(22,y.get(5));
    }
}
