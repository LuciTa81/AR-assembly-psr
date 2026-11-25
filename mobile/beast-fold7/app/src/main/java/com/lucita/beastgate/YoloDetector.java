package com.lucita.beastgate;

import android.content.Context;
import ai.onnxruntime.*;
import org.json.JSONObject;
import org.opencv.core.*;
import org.opencv.dnn.Dnn;
import org.opencv.imgproc.Imgproc;
import java.nio.FloatBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Fixed 1280x720 camera -> 640x384 RGB letterbox, matching the frozen desktop model. */
final class YoloDetector implements AutoCloseable {
    static final int WIDTH=640,HEIGHT=384;
    static final String[] LABELS={"driver","handle","screw"};
    private final OrtEnvironment env=OrtEnvironment.getEnvironment();
    private final OrtSession session;
    record Detection(int classId,float confidence,float x1,float y1,float x2,float y2){}

    YoloDetector(Context context)throws Exception{
        byte[] model;
        JSONObject metadata;
        try(var in=context.getAssets().open("driver.onnx")){model=in.readAllBytes();}
        try(var in=context.getAssets().open("driver-model.json")){
            metadata=new JSONObject(new String(in.readAllBytes(),StandardCharsets.UTF_8));
        }
        StringBuilder hash=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(model))hash.append(String.format(Locale.ROOT,"%02x",b&255));
        if(!metadata.getString("onnx_sha256").equals(hash.toString()))throw new IllegalArgumentException("model_hash");
        for(int i=0;i<LABELS.length;i++)if(!metadata.getJSONObject("classes").getString(Integer.toString(i)).equals(LABELS[i]))
            throw new IllegalArgumentException("model_classes");
        try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()){
            options.setIntraOpNumThreads(2);options.setInterOpNumThreads(1);
            session=env.createSession(model,options);
        }
        if(session.getInputInfo().size()!=1||!session.getInputInfo().containsKey("images")
            ||!Arrays.equals(((TensorInfo)session.getInputInfo().get("images").getInfo()).getShape(),new long[]{1,3,HEIGHT,WIDTH})){
            session.close();throw new IllegalArgumentException("model_input_shape");
        }
    }

    static float[] prepare(Mat rgba){
        if(rgba.cols()!=1280||rgba.rows()!=720||rgba.type()!=CvType.CV_8UC4)throw new IllegalArgumentException("expected_1280x720_RGBA");
        Mat rgb=new Mat(),small=new Mat(),padded=new Mat();
        try{
            Imgproc.cvtColor(rgba,rgb,Imgproc.COLOR_RGBA2RGB);
            // Exact 2x area reduction matches desktop linear pixels; ARM linear rounds differently.
            Imgproc.resize(rgb,small,new Size(640,360),0,0,Imgproc.INTER_AREA);
            Core.copyMakeBorder(small,padded,12,12,0,0,Core.BORDER_CONSTANT,new Scalar(114,114,114));
            int pixels=WIDTH*HEIGHT;byte[] bytes=new byte[pixels*3];padded.get(0,0,bytes);
            float[] tensor=new float[pixels*3];
            for(int i=0;i<pixels;i++)for(int c=0;c<3;c++)tensor[c*pixels+i]=(bytes[3*i+c]&255)/255f;
            return tensor;
        }finally{rgb.release();small.release();padded.release();}
    }

    float[][] run(float[] input)throws OrtException{
        if(input.length!=3*WIDTH*HEIGHT)throw new IllegalArgumentException("tensor_length");
        try(OnnxTensor tensor=OnnxTensor.createTensor(env,FloatBuffer.wrap(input),new long[]{1,3,HEIGHT,WIDTH});
            OrtSession.Result result=session.run(Collections.singletonMap("images",tensor))){
            Object output=result.get(0).getValue();
            if(!(output instanceof float[][][] head)||head.length!=1||head[0].length!=7)throw new IllegalArgumentException("model_output_shape");
            return head[0];
        }
    }

    List<Detection> detect(Mat rgba)throws OrtException{return decode(run(prepare(rgba)));}

    static List<Detection> decode(float[][] raw){
        if(raw==null||raw.length!=7)throw new IllegalArgumentException("head_channels");
        int count=raw[0].length;
        for(float[] channel:raw)if(channel.length!=count)throw new IllegalArgumentException("head_length");
        List<Detection> candidates=new ArrayList<>(),kept=new ArrayList<>();
        for(int i=0;i<count;i++){
            boolean finite=true;for(int c=0;c<7;c++)finite&=Float.isFinite(raw[c][i]);
            if(!finite||raw[2][i]<=0||raw[3][i]<=0)continue;
            int cls=0;for(int c=1;c<3;c++)if(raw[4+c][i]>raw[4+cls][i])cls=c;
            float confidence=raw[4+cls][i];if(confidence<=.20f||confidence>1)continue;
            candidates.add(new Detection(cls,confidence,raw[0][i]-raw[2][i]/2,raw[1][i]-raw[3][i]/2,
                raw[0][i]+raw[2][i]/2,raw[1][i]+raw[3][i]/2));
        }
        // NMS is applied in model coordinates before reversing the letterbox, as on desktop.
        for(int cls=0;cls<3;cls++){
            List<Detection> boxes=new ArrayList<>();for(Detection d:candidates)if(d.classId==cls)boxes.add(d);
            if(boxes.isEmpty())continue;
            Rect2d[] rects=new Rect2d[boxes.size()];float[] scores=new float[boxes.size()];
            for(int i=0;i<boxes.size();i++){Detection d=boxes.get(i);rects[i]=new Rect2d(d.x1,d.y1,d.x2-d.x1,d.y2-d.y1);scores[i]=d.confidence;}
            MatOfRect2d rectangles=new MatOfRect2d(rects);MatOfFloat confidences=new MatOfFloat(scores);MatOfInt indices=new MatOfInt();
            try{
                Dnn.NMSBoxes(rectangles,confidences,.20f,.7f,indices);
                for(int i:indices.toArray()){
                    Detection d=boxes.get(i);
                    float x1=clip(d.x1*2,1280),y1=clip((d.y1-12)*2,720),x2=clip(d.x2*2,1280),y2=clip((d.y2-12)*2,720);
                    if(x2>x1&&y2>y1)kept.add(new Detection(d.classId,d.confidence,x1,y1,x2,y2));
                }
            }finally{rectangles.release();confidences.release();indices.release();}
        }
        kept.sort(Comparator.comparingDouble(Detection::confidence).reversed());
        return kept.size()>300?new ArrayList<>(kept.subList(0,300)):kept;
    }
    private static float clip(float value,float max){return Math.max(0,Math.min(max,value));}
    public void close()throws OrtException{session.close();}
}
