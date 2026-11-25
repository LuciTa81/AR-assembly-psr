package com.lucita.beastgate;

import java.nio.ByteBuffer;
import java.io.ByteArrayOutputStream;

final class AvcPacket {
    static final int MAX_BYTES=256*1024;
    static byte[] annexB(byte[] source){
        if(source.length>=4&&source[0]==0&&source[1]==0&&(source[2]==1||(source[2]==0&&source[3]==1)))return source;
        ByteBuffer input=ByteBuffer.wrap(source);ByteArrayOutputStream output=new ByteArrayOutputStream();
        while(input.remaining()>=4){
            int length=input.getInt();if(length<=0||length>input.remaining())throw new IllegalArgumentException("Invalid AVC length");
            output.writeBytes(new byte[]{0,0,0,1});byte[] nal=new byte[length];input.get(nal);output.writeBytes(nal);
        }
        if(input.hasRemaining()||output.size()==0)throw new IllegalArgumentException("Invalid AVC data");
        return output.toByteArray();
    }
    static byte[] encode(long sequence,long timestamp,boolean key,byte[] config,byte[] frame){
        if(sequence<=0||sequence>0xffffffffL||timestamp<0||timestamp>9007199254740991L)throw new IllegalArgumentException("Invalid AVC metadata");
        int prefix=key?config.length:0,size=21+prefix+frame.length;
        if(size>MAX_BYTES||frame.length==0)throw new IllegalArgumentException("AVC frame too large");
        ByteBuffer packet=ByteBuffer.allocate(size);
        packet.put(new byte[]{65,82,86,50}).put((byte)(key?1:0)).putInt((int)sequence).putLong(timestamp).putShort((short)1280).putShort((short)720);
        if(key)packet.put(config);packet.put(frame);return packet.array();
    }
    static void copyPlane(ByteBuffer target,int rowStride,int pixelStride,byte[] source,int offset,int sourceRowStride,int sourcePixelStride,int width,int height){
        int base=target.position();
        for(int y=0;y<height;y++){
            int row=base+y*rowStride,input=offset+y*sourceRowStride;
            if(pixelStride==1&&sourcePixelStride==1){target.position(row);target.put(source,input,width);}
            else for(int x=0;x<width;x++)target.put(row+x*pixelStride,source[input+x*sourcePixelStride]);
        }
    }
}
