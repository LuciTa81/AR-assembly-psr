package com.lucita.beastgate;

/** Tracking-gated instruction time only; does not detect a box or lid. UI thread only. */
final class PreparationGuide {
    static final long BOX_DURATION_MS=7000,LID_DURATION_MS=6000;
    private int stage;
    private long startedAt,lastFrame=-1,elapsedMs;
    private boolean previousValid;

    PreparationGuide(long now){startedAt=now;}
    int stage(){return stage;}
    long elapsedMs(){return elapsedMs;}
    long durationMs(){return stage==0?BOX_DURATION_MS:stage==1?LID_DURATION_MS:0;}
    boolean finished(){return stage==2;}

    boolean onDraw(int drawnStage,long frame,long now,boolean valid){
        if(finished()||drawnStage!=stage)return false;
        if(!valid||frame<startedAt||now<frame||now-frame>500){previousValid=false;return false;}
        if(frame<=lastFrame)return false;
        long gap=frame-lastFrame;
        if(previousValid&&gap<=350)elapsedMs+=gap;
        lastFrame=frame;previousValid=true;
        if(elapsedMs<durationMs())return false;
        stage++;startedAt=now;elapsedMs=0;lastFrame=-1;previousValid=false;
        return true;
    }
}
