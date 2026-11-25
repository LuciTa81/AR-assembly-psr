package com.lucita.beastgate;

import android.content.Context;
import android.graphics.*;
import android.os.SystemClock;
import android.view.View;
import java.util.Map;
import org.opencv.core.Point;

/** The bitmap and points always originate from the same accepted camera frame. */
final class AnalysisView extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    private Bitmap bitmap;
    private WorkspaceTracker.Result result;
    private java.util.List<YoloDetector.Detection> tools=java.util.List.of();
    private long receivedAt;
    AnalysisView(Context context){super(context);}
    void update(Bitmap bitmap,WorkspaceTracker.Result result,long receivedAt){
        update(bitmap,result,receivedAt,java.util.List.of());
    }
    void update(Bitmap bitmap,WorkspaceTracker.Result result,long receivedAt,java.util.List<YoloDetector.Detection> tools){
        this.tools=java.util.List.copyOf(tools);
        this.bitmap=bitmap;this.result=result;this.receivedAt=receivedAt;invalidate();
    }
    void clear(){bitmap=null;result=null;tools=java.util.List.of();invalidate();}
    @Override protected void onDraw(Canvas canvas){
        canvas.drawColor(Color.BLACK);
        if(bitmap==null)return;
        float scale=Math.min(getWidth()/(float)bitmap.getWidth(),getHeight()/(float)bitmap.getHeight());
        float x=(getWidth()-bitmap.getWidth()*scale)/2, y=(getHeight()-bitmap.getHeight()*scale)/2;
        canvas.save();canvas.translate(x,y);canvas.scale(scale,scale);
        paint.setStyle(Paint.Style.FILL);canvas.drawBitmap(bitmap,0,0,paint);
        if(result!=null&&SystemClock.elapsedRealtime()-receivedAt<=500){
            paint.setStrokeWidth(2/scale);paint.setTextSize(16/scale);
            for(Map.Entry<Integer,Point[]> entry:result.markers.entrySet()){
                Point[] q=entry.getValue();paint.setColor(Color.rgb(255,200,70));
                for(int i=0;i<4;i++)canvas.drawLine((float)q[i].x,(float)q[i].y,(float)q[(i+1)%4].x,(float)q[(i+1)%4].y,paint);
                canvas.drawText(Integer.toString(entry.getKey()),(float)q[0].x,(float)q[0].y-5/scale,paint);
            }
            if(result.valid){
                paint.setColor(Color.rgb(55,230,210));paint.setStrokeWidth(3/scale);
                for(Map.Entry<String,Point> entry:result.targets.entrySet()){
                    Point p=entry.getValue();paint.setStyle(Paint.Style.STROKE);
                    canvas.drawCircle((float)p.x,(float)p.y,12/scale,paint);
                    paint.setStyle(Paint.Style.FILL);canvas.drawText(entry.getKey(),(float)p.x+16/scale,(float)p.y,paint);
                }
            }
            for(var d:tools){
                paint.setColor(d.classId()==0?Color.rgb(255,120,80):d.classId()==1?Color.rgb(100,175,255):Color.rgb(220,140,255));
                paint.setStrokeWidth(3/scale);paint.setStyle(Paint.Style.STROKE);
                canvas.drawRect(d.x1(),d.y1(),d.x2(),d.y2(),paint);
                paint.setStyle(Paint.Style.FILL);
                String name=new String[]{"드라이버","손잡이","나사"}[d.classId()];
                canvas.drawText(name+" "+Math.round(d.confidence()*100)+"%",d.x1(),Math.max(20/scale,d.y1()-6/scale),paint);
            }
        }
        canvas.restore();
        if(result!=null&&SystemClock.elapsedRealtime()-receivedAt<=500)postInvalidateDelayed(100);
    }
}
