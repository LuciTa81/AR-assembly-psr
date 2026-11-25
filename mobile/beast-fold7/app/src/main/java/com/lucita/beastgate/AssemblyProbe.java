package com.lucita.beastgate;

/** Bounded timed guidance, not a fastening/torque verifier. All calls use the UI thread. */
final class AssemblyProbe {
    static final long WORKING_CUE_DELAY_MS=4000;
    enum Phase { APPROACH, WORKING, RELEASE }
    private int target;
    private Phase phase=Phase.APPROACH;
    private long lastFrame=-1,lastNear=-1,holdMs,armedAt=-1,greenAt=-1;
    private long startedAt;
    private final int terminalTarget;
    private boolean previousNear;
    private long finishedAt=-1;

    AssemblyProbe(long now){this(now,1);}
    AssemblyProbe(long now,int terminalTarget){
        if(terminalTarget!=1&&terminalTarget!=4)throw new IllegalArgumentException("terminalTarget must be 1 or 4");
        startedAt=now;this.terminalTarget=terminalTarget;
    }
    int target(){return target;}
    Phase phase(){return phase;}
    long holdMs(){return holdMs;}
    long greenAt(){return greenAt;}
    long finishedAt(){return finishedAt;}
    boolean finished(){return target==terminalTarget;}

    void observe(long frame,long now,boolean valid,boolean near){
        if(finished()||frame<startedAt||frame<=lastFrame||now<frame)return;
        lastFrame=frame;
        if(now-frame>800||!valid){previousNear=false;if(armedAt>=0&&greenAt<0)phase=Phase.WORKING;return;}
        if(greenAt>=0)return;
        if(armedAt>=0){
            phase=near&&now-armedAt>=WORKING_CUE_DELAY_MS?Phase.RELEASE:Phase.WORKING;
            return;
        }
        if(!near){holdMs=0;lastNear=-1;previousNear=false;phase=Phase.APPROACH;return;}
        if(lastNear>=0){
            long gap=frame-lastNear;
            if(gap>600)holdMs=0;
            else if(previousNear&&gap<=350)holdMs+=gap;
        }
        lastNear=frame;previousNear=true;phase=Phase.WORKING;
        if(holdMs>=800){holdMs=800;armedAt=now;}
    }

    void acknowledgeGreen(int drawnTarget,long now){
        if(!finished()&&drawnTarget==target&&phase==Phase.RELEASE&&greenAt<0&&now>=armedAt+WORKING_CUE_DELAY_MS)
            greenAt=now;
    }

    boolean tick(long now){
        if(!finished()&&greenAt>=0&&now-greenAt>=3000){
            target++;phase=Phase.APPROACH;
            if(finished())finishedAt=now;
            else{
                startedAt=now;lastFrame=-1;lastNear=-1;holdMs=0;
                armedAt=-1;greenAt=-1;previousNear=false;
            }
            return true;
        }
        return false;
    }
}
