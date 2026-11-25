package com.lucita.beastgate;

import org.json.JSONObject;

final class SupervisorState {
    static int stage(boolean running,PreparationGuide prep,AssemblyProbe assembly){
        if(!running||assembly==null)return -1;
        return prep!=null&&!prep.finished()?prep.stage():assembly.target()+2;
    }
    static String action(int stage,AssemblyProbe.Phase phase,boolean visible){
        if(stage<0)return "작업 대기";
        if(stage==6)return "조립 상태를 확인해주세요";
        if(!visible)return "작업대가 보이도록 바라봐주세요";
        if(stage<2)return stage==0?"상자를 놓아주세요":"뚜껑을 닫아주세요";
        String letter="ABCD".substring(stage-2,stage-1);
        return phase==AssemblyProbe.Phase.RELEASE?"드라이버를 떼어주세요":phase==AssemblyProbe.Phase.WORKING?
            "나사 "+letter+"를 조여주세요":"드라이버 끝을 나사 "+letter+"에 맞춰주세요";
    }
    static String json(String session,long now,long elapsed,boolean running,int stage,String phase,String action,
        boolean tracked,boolean visible,int markers,double rms,long poseAge,long frame,String message,long remaining){
        try{
            return new JSONObject().put("schema",1).put("session",session).put("updated_ms",now)
                .put("elapsed_ms",elapsed).put("running",running).put("stage",stage).put("phase",phase)
                .put("action",action).put("tracked",tracked).put("overlay_visible",visible).put("markers",markers)
                .put("rms_px",Double.isFinite(rms)?rms:JSONObject.NULL).put("pose_age_ms",poseAge)
                .put("frame",frame).put("message",message).put("remaining_ms",remaining)
                .put("video_available",false).put("recording",false).put("fastening_verified",false).toString();
        }catch(org.json.JSONException e){throw new IllegalStateException(e);}
    }
}
