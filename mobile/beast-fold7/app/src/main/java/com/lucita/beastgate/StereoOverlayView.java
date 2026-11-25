package com.lucita.beastgate;

import android.content.Context;
import android.graphics.*;
import android.os.SystemClock;
import android.view.View;

/** No scaling: calibrated eye-local pixels map 1:1 onto the 3840x1080 SBS surface. */
final class StereoOverlayView extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private double[][] pair;
    private long receivedAt;
    private int guideTarget=-1;
    private AssemblyProbe.Phase guidePhase;
    private java.util.function.BiConsumer<Integer,Long> greenDrawn;
    interface PreparationDrawn { void accept(int stage,long frame,long now,boolean tracked); }
    private int preparationStage=-1;
    private boolean preparationTracked;
    private PreparationDrawn preparationDrawn;
    private BoxOutline.ProjectedStroke[] outline;
    private long outlineAt;
    private SphereMarker sphereMarker;
    private boolean screwContextEnabled;
    private double[][][] screwContext;
    private long screwContextAt;
    StereoOverlayView(Context context){super(context);}
    void setScrewContextEnabled(boolean enabled){screwContextEnabled=enabled;screwContext=null;invalidate();}
    void updateScrewContext(double[][][] points,long frame){screwContext=points;screwContextAt=frame;invalidate();}
    void setSphereMarker(SphereMarker marker){sphereMarker=marker;invalidate();}
    void updateOutline(BoxOutline.ProjectedStroke[] strokes,long frame){outline=strokes;outlineAt=frame;invalidate();}
    void update(double[][] pair,long receivedAt){preparationStage=-1;preparationDrawn=null;this.pair=pair;this.receivedAt=receivedAt;invalidate();}
    void updateGuide(double[][] pair,long receivedAt,int target,AssemblyProbe.Phase phase,
        java.util.function.BiConsumer<Integer,Long> greenDrawn){
        preparationStage=-1;preparationDrawn=null;
        this.pair=pair;this.receivedAt=receivedAt;guideTarget=target;guidePhase=phase;this.greenDrawn=greenDrawn;invalidate();
    }
    void updatePreparation(int stage,long receivedAt,boolean tracked,PreparationDrawn drawn){
        if(stage<0||stage>1)throw new IllegalArgumentException("preparation stage");
        screwContext=null;pair=null;guideTarget=-1;greenDrawn=null;preparationStage=stage;
        this.receivedAt=receivedAt;preparationTracked=tracked;preparationDrawn=drawn;invalidate();
    }
    void clear(){screwContext=null;outline=null;pair=null;guideTarget=-1;greenDrawn=null;preparationStage=-1;preparationDrawn=null;invalidate();}
    void showInspection(){updateGuide(null,0,4,AssemblyProbe.Phase.APPROACH,null);}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){android.util.Log.i("BeastGate","STEREO_SURFACE "+w+"x"+h);}
    @Override protected void onDraw(Canvas canvas){
        canvas.drawColor(Color.BLACK);
        long now=SystemClock.elapsedRealtime(),age=now-receivedAt;
        if(getWidth()!=3840||getHeight()!=1080)return;
        drawOutline(canvas,now);
        if(preparationStage>=0){
            boolean tracked=preparationTracked&&age>=0&&age<=500;
            for(int eye=0;eye<2;eye++){
                canvas.save();canvas.clipRect(eye*1920,0,(eye+1)*1920,1080);canvas.translate(eye*1920,0);
                paint.setColor(Color.rgb(255,184,65));paint.setStyle(Paint.Style.FILL);
                paint.setTextAlign(Paint.Align.CENTER);paint.setTypeface(Typeface.DEFAULT_BOLD);
                paint.setTextSize(48);canvas.drawText(preparationStage==0?"상자 배치":"뚜껑 닫기",960,100,paint);
                paint.setTextSize(44);canvas.drawText(!tracked?"작업대가 보이도록 바라봐주세요":preparationStage==0?"상자를 놓아주세요":"뚜껑을 닫아주세요",960,960,paint);
                canvas.restore();
            }
            if(preparationDrawn!=null)preparationDrawn.accept(preparationStage,receivedAt,now,tracked);
            postInvalidateDelayed(33);return;
        }
        boolean visible=pair!=null&&age>=0&&age<=500;
        if(!visible&&guideTarget<0)return;
        int color=guideTarget<0?Color.rgb(89,255,191):guidePhase==AssemblyProbe.Phase.RELEASE?Color.rgb(89,255,191)
            :guidePhase==AssemblyProbe.Phase.WORKING?Color.rgb(89,217,255):Color.rgb(255,184,65);
        for(int eye=0;eye<2;eye++){
            canvas.save();canvas.clipRect(eye*1920,0,(eye+1)*1920,1080);canvas.translate(eye*1920,0);
            drawScrewContext(canvas,eye,now);
            paint.setColor(color);paint.setStrokeWidth(guideTarget<0?2:3);paint.setStyle(Paint.Style.STROKE);
            if(visible){
                float x=(float)pair[eye][0],y=(float)pair[eye][1];
                if(screwContextEnabled){
                    paint.setStrokeWidth(2.625f);canvas.drawCircle(x,y,21,paint);
                }
                else if(sphereMarker!=null)sphereMarker.draw(canvas,x,y,guideTarget<0?null:guidePhase);
                else {
                    canvas.drawCircle(x,y,24,paint);
                    canvas.drawLine(x-5,y,x+5,y,paint);canvas.drawLine(x,y-5,x,y+5,paint);
                }
            }
            if(guideTarget>=0){
                String letter=guideTarget==4?"":"ABCD".substring(guideTarget,guideTarget+1);
                String action=guideTarget==4?"조립 상태를 확인해주세요":!visible?"작업대가 보이도록 바라봐주세요"
                    :guidePhase==AssemblyProbe.Phase.RELEASE?"드라이버를 떼어주세요"
                    :guidePhase==AssemblyProbe.Phase.WORKING?"나사 "+letter+"를 조여주세요":"드라이버 끝을 나사 "+letter+"에 맞춰주세요";
                paint.setStyle(Paint.Style.FILL);paint.setTextAlign(Paint.Align.CENTER);paint.setTypeface(Typeface.DEFAULT_BOLD);
                paint.setTextSize(48);canvas.drawText(guideTarget==4?"최종 확인":"나사 "+letter+" · "+(guideTarget+1)+"/4",960,100,paint);
                paint.setTextSize(44);canvas.drawText(action,960,960,paint);
            }
            canvas.restore();
        }
        if(visible&&guideTarget>=0&&guidePhase==AssemblyProbe.Phase.RELEASE&&greenDrawn!=null)
            greenDrawn.accept(guideTarget,SystemClock.elapsedRealtime());
        postInvalidateDelayed(33);
    }
    private void drawScrewContext(Canvas canvas,int eye,long now){
        if(!screwContextEnabled||screwContext==null||now<screwContextAt||now-screwContextAt>500)return;
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2.53f);
        paint.setColor(guideTarget==4?Color.rgb(77,133,119):Color.argb(153,210,210,210));
        // Same ring dimensions as the laptop's 36px reference texture; centers stay calibrated.
        for(int i=0;i<screwContext.length;i++){
            if(i==guideTarget||screwContext[i]==null)continue;
            canvas.drawCircle((float)screwContext[i][eye][0],(float)screwContext[i][eye][1],15.75f,paint);
        }
    }
    private void drawOutline(Canvas canvas,long now){
        if(outline==null||now<outlineAt||now-outlineAt>500)return;
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
        for(int eye=0;eye<2;eye++){
            canvas.save();canvas.clipRect(eye*1920,0,(eye+1)*1920,1080);canvas.translate(eye*1920,0);
            for(var stroke:outline){
                boolean emphasized=stroke.level()==3;
                paint.setColor(emphasized?Color.rgb(112,194,173):Color.rgb(77,133,119));
                paint.setStrokeWidth(emphasized?4:3);
                double[][] points=stroke.eyes()[eye];Path path=new Path();
                path.moveTo((float)points[0][0],(float)points[0][1]);
                for(int i=1;i<points.length;i++)path.lineTo((float)points[i][0],(float)points[i][1]);
                canvas.drawPath(path,paint);
            }
            canvas.restore();
        }
        paint.setStrokeCap(Paint.Cap.BUTT);paint.setStrokeJoin(Paint.Join.MITER);
    }
}
