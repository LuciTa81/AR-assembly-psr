package com.lucita.beastgate;

import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.os.Bundle;
import android.os.SystemClock;
import java.nio.ByteBuffer;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.function.BooleanSupplier;
import java.util.function.Predicate;
import java.util.function.Consumer;

/** Capture is independent of AR analysis. One input in flight; no image recording. */
final class RemoteVideoEncoder {
    private final ExecutorService worker=Executors.newSingleThreadExecutor(r->new Thread(r,"supervisor-video"));
    private final BooleanSupplier ready;
    private final Predicate<byte[]> send;
    private final Consumer<String> report;
    private long generation,lastFrame=-1000,sequence,retryAfter;
    private boolean busy,closed,needKey=true;
    private MediaCodec codec;
    private byte[] config=new byte[0];
    RemoteVideoEncoder(BooleanSupplier ready,Predicate<byte[]> send,Consumer<String> report){this.ready=ready;this.send=send;this.report=report;}
    synchronized boolean wantsFrame(long captured){return !closed&&!busy&&captured>=retryAfter&&captured-lastFrame>=32&&ready.getAsBoolean();}
    synchronized void offer(byte[] nv21,long captured){
        if(!wantsFrame(captured)||nv21.length!=1280*720*3/2)return;
        busy=true;lastFrame=captured;long token=generation;
        worker.execute(()->{
            try{
                if(!valid(token))return;
                if(codec==null)open();
                drain(token);if(!valid(token))return;
                if(needKey){Bundle parameters=new Bundle();parameters.putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME,0);codec.setParameters(parameters);}
                int index=codec.dequeueInputBuffer(0);if(index<0)return;
                Image image=codec.getInputImage(index);
                if(image==null)throw new IllegalStateException("No flexible YUV input");
                try{
                    Image.Plane[] planes=image.getPlanes();
                    AvcPacket.copyPlane(planes[0].getBuffer(),planes[0].getRowStride(),planes[0].getPixelStride(),nv21,0,1280,1,1280,720);
                    AvcPacket.copyPlane(planes[1].getBuffer(),planes[1].getRowStride(),planes[1].getPixelStride(),nv21,1280*720+1,1280,2,640,360);
                    AvcPacket.copyPlane(planes[2].getBuffer(),planes[2].getRowStride(),planes[2].getPixelStride(),nv21,1280*720,1280,2,640,360);
                }finally{image.close();}
                codec.queueInputBuffer(index,0,nv21.length,captured*1000,0);drain(token);
            }catch(Exception error){
                release();synchronized(this){retryAfter=SystemClock.elapsedRealtime()+5000;}
                report.accept("영상 인코더 연결을 확인해 주세요. 작업 안내는 계속됩니다.");
                android.util.Log.w("RemoteVideo","ENCODER_UNAVAILABLE "+error.getClass().getSimpleName());
            }finally{synchronized(this){busy=false;}}
        });
    }
    private synchronized boolean valid(long token){return !closed&&generation==token&&ready.getAsBoolean();}
    private void open() throws Exception{
        MediaFormat format=MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC,1280,720);
        format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
        format.setInteger(MediaFormat.KEY_BIT_RATE,2000000);format.setInteger(MediaFormat.KEY_FRAME_RATE,30);
        format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL,1);format.setInteger(MediaFormat.KEY_MAX_B_FRAMES,0);
        format.setInteger(MediaFormat.KEY_PROFILE,MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline);
        format.setInteger(MediaFormat.KEY_LEVEL,MediaCodecInfo.CodecProfileLevel.AVCLevel31);
        String name=null;
        for(MediaCodecInfo info:new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()){
            if(!info.isEncoder()||!info.isHardwareAccelerated())continue;
            try{if(info.getCapabilitiesForType(MediaFormat.MIMETYPE_VIDEO_AVC).isFormatSupported(format)){name=info.getName();break;}}catch(IllegalArgumentException ignored){}
        }
        if(name==null)throw new IllegalStateException("Hardware AVC encoder unavailable");
        codec=MediaCodec.createByCodecName(name);codec.configure(format,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE);codec.start();needKey=true;config=new byte[0];
        android.util.Log.i("RemoteVideo","AVC_ENCODER "+name+" 1280x720 target_fps=30 bitrate=2000000");
    }
    private static byte[] bytes(ByteBuffer buffer){byte[] result=new byte[buffer.remaining()];buffer.get(result);return result;}
    private void drain(long token){
        MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
        for(int n=0;n<8;n++){
            int index=codec.dequeueOutputBuffer(info,0);
            if(index==MediaCodec.INFO_TRY_AGAIN_LATER)return;
            if(index==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){
                MediaFormat format=codec.getOutputFormat();ByteArrayOutputStream joined=new ByteArrayOutputStream();
                for(String key:new String[]{"csd-0","csd-1"}){ByteBuffer data=format.getByteBuffer(key);if(data!=null)joined.writeBytes(AvcPacket.annexB(bytes(data.duplicate())));}
                config=joined.toByteArray();continue;
            }
            if(index<0)continue;
            try{
                ByteBuffer data=codec.getOutputBuffer(index);if(data==null||info.size<=0)continue;
                data.position(info.offset);data.limit(info.offset+info.size);byte[] frame=AvcPacket.annexB(bytes(data));
                if((info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)!=0){config=frame;continue;}
                boolean key=(info.flags&MediaCodec.BUFFER_FLAG_KEY_FRAME)!=0;long next=++sequence;
                if(!valid(token)||SystemClock.elapsedRealtime()*1000-info.presentationTimeUs>500000){needKey=true;continue;}
                if(needKey&&!key)continue;
                byte[] packet=AvcPacket.encode(next,info.presentationTimeUs,key,config,frame);
                synchronized(this){if(valid(token)&&send.test(packet))needKey=false;else needKey=true;}
            }finally{codec.releaseOutputBuffer(index,false);}
        }
    }
    private void release(){if(codec!=null){try{codec.stop();}catch(Exception ignored){}try{codec.release();}catch(Exception ignored){}codec=null;}needKey=true;config=new byte[0];}
    synchronized void clear(){generation++;lastFrame=-1000;if(!closed)worker.execute(this::release);}
    synchronized void close(){if(closed)return;generation++;closed=true;worker.execute(this::release);worker.shutdown();}
}
